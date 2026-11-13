# Productor Kafka probado con un Producer FALSO (sin cluster): key/value/headers, reintento ante
# cola llena, callbacks de entrega, cierre limpio y la fabrica que combina RabbitMQ + Kafka.

import json
import logging
from types import SimpleNamespace as NS

import pytest
from confluent_kafka import KafkaError, KafkaException

import app.infrastructure.messaging.event_publishers as fabrica
from app.core.config import Settings
from app.domain.ports.evento_publisher_port import (
    EventoNoEnrutableError,
    NullEventPublisher,
    PublicacionEventoError,
)
from app.infrastructure.messaging.event_publishers import CompositeEventPublisher, construir_publicador
from app.infrastructure.messaging.kafka_publisher import (
    KafkaPedidoEventPublisher,
    configuracion_productor,
    serializar_evento,
)
from app.schemas.schema_eventos import EventoPedidoSchema, ItemEventoSchema


def _evento(tipo="creado", pedido_id=101) -> EventoPedidoSchema:
    return EventoPedidoSchema(
        tipo=tipo, pedido_id=pedido_id, cliente_id="cli-1", estado="PENDIENTE", monto_total=15990.0,
        items=[ItemEventoSchema(sku="SKU-001", cantidad=2, precio_unitario=7995.0)],
    )


class ProductorFalso:
    def __init__(self):
        self.producidos = []
        self.errores = []        # excepciones a lanzar, una por llamada a produce()
        self.pendientes = 0
        self.flush_llamado_con = None
        self.polls = 0

    def produce(self, topico, key=None, value=None, headers=None, on_delivery=None):
        if self.errores:
            raise self.errores.pop(0)
        self.producidos.append(NS(topico=topico, key=key, value=value, headers=headers, on_delivery=on_delivery))

    def poll(self, timeout=0):
        self.polls += 1
        return 0

    def flush(self, timeout=None):
        self.flush_llamado_con = timeout
        return self.pendientes


@pytest.fixture
def productor():
    return ProductorFalso()


@pytest.fixture
def publicador(productor):
    p = KafkaPedidoEventPublisher(productor=productor)
    yield p
    p._detener.set()


# ------------------------------------------------------------ serializacion

def test_serializar_usa_pedido_id_como_key_y_json_como_value():
    key, value, headers = serializar_evento(_evento("confirmado", pedido_id=7))
    assert key == b"7"
    cuerpo = json.loads(value)
    assert cuerpo["tipo"] == "confirmado" and cuerpo["pedido_id"] == 7
    assert cuerpo["items"] == [{"sku": "SKU-001", "cantidad": 2, "precio_unitario": 7995.0}]
    assert dict(headers)["tipo"] == b"confirmado"
    assert dict(headers)["event_id"] == cuerpo["event_id"].encode()


def test_mismo_pedido_misma_key_para_todos_sus_eventos():
    llaves = {serializar_evento(_evento(t, pedido_id=5))[0] for t in ("creado", "confirmado", "cancelado")}
    assert llaves == {b"5"}


# ------------------------------------------------------------ configuracion

def test_configuracion_del_productor_es_durable_e_idempotente():
    cfg = configuracion_productor(Settings(
        DATABASE_URL="sqlite://", AZURE_TENANT_ID="t", AZURE_CLIENT_ID="c",
        KAFKA_BOOTSTRAP_SERVERS="kafka1:29092,kafka2:29092,kafka3:29092",
    ))
    assert cfg["bootstrap.servers"] == "kafka1:29092,kafka2:29092,kafka3:29092"
    assert cfg["acks"] == "all" and cfg["enable.idempotence"] is True
    assert cfg["client.id"] == "ms-pedidos"


# ------------------------------------------------------------ publicar

def test_publica_en_el_topico_de_pedidos(publicador, productor):
    publicador.publicar(_evento())
    (m,) = productor.producidos
    assert m.topico == "pedidos.eventos"
    assert m.key == b"101"
    assert json.loads(m.value)["pedido_id"] == 101
    assert m.on_delivery is not None


def test_reintenta_una_vez_si_la_cola_local_esta_llena(publicador, productor):
    productor.errores = [BufferError("llena")]
    publicador.publicar(_evento())
    assert len(productor.producidos) == 1


def test_si_la_cola_sigue_llena_falla_con_error_de_dominio(publicador, productor):
    productor.errores = [BufferError("llena"), BufferError("llena")]
    with pytest.raises(PublicacionEventoError, match="llena"):
        publicador.publicar(_evento())


def test_kafka_exception_se_traduce(publicador, productor):
    productor.errores = [KafkaException(KafkaError(KafkaError.MSG_SIZE_TOO_LARGE))]
    with pytest.raises(PublicacionEventoError):
        publicador.publicar(_evento())


def test_callback_de_entrega_con_error_queda_en_el_log(caplog):
    mensaje = NS(topic=lambda: "pedidos.eventos", key=lambda: b"101")
    with caplog.at_level(logging.ERROR):
        KafkaPedidoEventPublisher._al_entregar(KafkaError(KafkaError._MSG_TIMED_OUT), mensaje)
    assert "no confirmo" in caplog.text and "pedidos.eventos" in caplog.text


def test_callback_de_entrega_exitosa_no_loguea_error(caplog):
    mensaje = NS(topic=lambda: "t", key=lambda: b"1", partition=lambda: 0, offset=lambda: 5)
    with caplog.at_level(logging.ERROR):
        KafkaPedidoEventPublisher._al_entregar(None, mensaje)
    assert caplog.text == ""


def test_cerrar_hace_flush_con_el_timeout_configurado(publicador, productor):
    publicador.cerrar()
    assert productor.flush_llamado_con == 5.0


def test_cerrar_avisa_si_quedan_pendientes(publicador, productor, caplog):
    productor.pendientes = 3
    with caplog.at_level(logging.WARNING):
        publicador.cerrar()
    assert "3 mensaje" in caplog.text


# ------------------------------------------------------------ composite y fabrica

class Destino:
    def __init__(self, error=None):
        self.eventos, self.error, self.cerrado = [], error, False

    def publicar(self, evento):
        if self.error:
            raise self.error
        self.eventos.append(evento)

    def cerrar(self):
        self.cerrado = True


def test_composite_publica_en_todos():
    a, b = Destino(), Destino()
    CompositeEventPublisher([a, b]).publicar(_evento())
    assert len(a.eventos) == len(b.eventos) == 1


def test_si_rabbit_falla_kafka_igual_recibe_el_evento():
    rabbit, kafka = Destino(error=EventoNoEnrutableError("sin cola")), Destino()
    with pytest.raises(EventoNoEnrutableError):
        CompositeEventPublisher([rabbit, kafka]).publicar(_evento())
    assert len(kafka.eventos) == 1


def test_si_fallan_ambos_se_informa_un_error_agregado():
    c = CompositeEventPublisher([Destino(error=OSError("a")), Destino(error=OSError("b"))])
    with pytest.raises(PublicacionEventoError, match="2 destinos"):
        c.publicar(_evento())


def test_composite_cierra_todos_aunque_uno_falle():
    malo = Destino()
    malo.cerrar = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    bueno = Destino()
    CompositeEventPublisher([malo, bueno]).cerrar()
    assert bueno.cerrado


def test_fabrica_sin_brokers_devuelve_publicador_nulo():
    cfg = NS(RABBITMQ_ENABLED=False, KAFKA_ENABLED=False)
    assert isinstance(construir_publicador(cfg), NullEventPublisher)


def test_fabrica_solo_kafka(monkeypatch):
    monkeypatch.setattr("app.infrastructure.messaging.kafka_publisher.Producer", lambda conf: ProductorFalso())
    pub = construir_publicador(NS(RABBITMQ_ENABLED=False, KAFKA_ENABLED=True))
    assert isinstance(pub, KafkaPedidoEventPublisher)
    pub.cerrar()


def test_fabrica_con_ambos_brokers_usa_composite(monkeypatch):
    monkeypatch.setattr("app.infrastructure.messaging.kafka_publisher.Producer", lambda conf: ProductorFalso())
    monkeypatch.setattr(
        "app.infrastructure.messaging.rabbitmq_publisher.RabbitMQPedidoEventPublisher", lambda: Destino()
    )
    pub = construir_publicador(NS(RABBITMQ_ENABLED=True, KAFKA_ENABLED=True))
    assert isinstance(pub, CompositeEventPublisher)
    pub.cerrar()


def test_singleton_y_cierre(monkeypatch):
    destino = Destino()
    monkeypatch.setattr(fabrica, "construir_publicador", lambda: destino)
    monkeypatch.setattr(fabrica, "_publisher", None)
    assert fabrica.obtener_event_publisher() is destino
    assert fabrica.obtener_event_publisher() is destino
    fabrica.cerrar_event_publisher()
    assert destino.cerrado and fabrica._publisher is None
