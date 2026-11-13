# Emision de movimientos de stock (Kafka) y alertas de stock bajo (RabbitMQ direct):
# regla de dominio (cuando se emite y cuando NO), contrato del evento, adaptadores con dobles y fabrica.

import json
import logging
from types import SimpleNamespace as NS

import pika
import pika.exceptions
import pytest
from confluent_kafka import KafkaError, KafkaException

from app.core.config import Settings
from app.domain.ports.movimiento_publisher_port import PublicacionMovimientoError
from app.domain.services.inventario_service import InventarioService
from app.infrastructure.messaging.kafka_movimiento_publisher import (
    KafkaMovimientoPublisher,
    configuracion_productor,
    serializar_evento,
)
from app.infrastructure.messaging.movimiento_publishers import CompositeMovimientoPublisher, construir_publicador
from app.infrastructure.messaging.rabbitmq_alertas_publisher import RabbitMQAlertaStockPublisher
from app.schemas.schema_eventos_movimiento import EventoMovimientoStock
from tests.fake_repository import FakeInventarioRepository


class Registro:
    """Un publicador que solo guarda lo que recibe."""
    def __init__(self, error=None):
        self.eventos, self.error, self.cerrado = [], error, False

    def publicar(self, evento):
        if self.error:
            raise self.error
        self.eventos.append(evento)

    def cerrar(self):
        self.cerrado = True


@pytest.fixture
def pub():
    return Registro()


@pytest.fixture
def service(pub):
    s = InventarioService(FakeInventarioRepository(), pub)
    s.crear_inventario({"sku": "SKU-1", "cantidad_disponible": 10, "umbral_minimo": 5})
    return s


def tipos(pub):
    return [e.tipo for e in pub.eventos]


# ------------------------------------------------------------ regla de dominio

def test_cada_movimiento_emite_su_evento(service, pub):
    service.reservar_stock("SKU-1", 2)
    service.liberar_stock("SKU-1", 1)
    service.reponer_stock("SKU-1", 3)
    assert tipos(pub) == ["reservado", "liberado", "repuesto"]


def test_el_evento_lleva_el_stock_despues_del_movimiento(service, pub):
    service.reservar_stock("SKU-1", 4)
    e = pub.eventos[0]
    assert (e.sku, e.cantidad, e.stock_disponible, e.stock_reservado, e.stock_vendible, e.umbral_minimo) == \
        ("SKU-1", 4, 10, 4, 6, 5)


def test_alerta_stock_bajo_al_cruzar_el_umbral(service, pub):
    service.reservar_stock("SKU-1", 6)          # disponible sigue en 10: reservar no baja el stock fisico
    assert tipos(pub) == ["reservado"]
    service.confirmar_salida("SKU-1", 6)        # disponible 10 -> 4: cruza el umbral (5)
    assert tipos(pub) == ["reservado", "confirmado", "stock_bajo"]
    alerta = pub.eventos[-1]
    assert alerta.cantidad == 0 and alerta.stock_disponible == 4 and alerta.umbral_minimo == 5


def test_no_repite_la_alerta_si_ya_estaba_bajo_el_umbral(service, pub):
    service.reservar_stock("SKU-1", 8)
    service.confirmar_salida("SKU-1", 6)        # 10 -> 4: alerta
    service.confirmar_salida("SKU-1", 2)        # 4 -> 2: ya estaba bajo, sin alerta nueva
    assert tipos(pub).count("stock_bajo") == 1


def test_llegar_justo_al_umbral_cuenta_como_bajo(service, pub):
    service.reservar_stock("SKU-1", 5)
    service.confirmar_salida("SKU-1", 5)        # 10 -> 5 == umbral (misma regla que ?bajo_umbral=true)
    assert "stock_bajo" in tipos(pub)


def test_sin_umbral_configurado_nunca_alerta(pub):
    s = InventarioService(FakeInventarioRepository(), pub)
    s.crear_inventario({"sku": "SKU-2", "cantidad_disponible": 3})
    s.reservar_stock("SKU-2", 3)
    s.confirmar_salida("SKU-2", 3)
    assert "stock_bajo" not in tipos(pub)


def test_movimientos_rechazados_no_emiten_nada(service, pub):
    with pytest.raises(Exception):
        service.reservar_stock("SKU-1", 999)
    with pytest.raises(Exception):
        service.confirmar_salida("SKU-1", 1)    # no hay reservado
    assert pub.eventos == []


def test_un_broker_caido_no_rompe_la_operacion(caplog):
    s = InventarioService(FakeInventarioRepository(), Registro(error=OSError("kafka caido")))
    s.crear_inventario({"sku": "SKU-3", "cantidad_disponible": 5})
    with caplog.at_level(logging.ERROR):
        r = s.reservar_stock("SKU-3", 2)
    assert r.cantidad_reservada == 2            # el stock SI cambio
    assert "No se pudo publicar el movimiento" in caplog.text


def test_servicio_sin_publicador_sigue_funcionando():
    s = InventarioService(FakeInventarioRepository())
    s.crear_inventario({"sku": "SKU-4", "cantidad_disponible": 5})
    assert s.reservar_stock("SKU-4", 1).cantidad_reservada == 1


# ------------------------------------------------------------ contrato del evento

def test_contrato_del_evento_json():
    e = EventoMovimientoStock(tipo="reservado", sku="SKU-9", cantidad=1, stock_disponible=5,
                              stock_reservado=1, stock_vendible=4)
    d = json.loads(e.model_dump_json())
    assert set(d) == {"event_id", "tipo", "ocurrido_en", "sku", "cantidad", "stock_disponible",
                      "stock_reservado", "stock_vendible", "umbral_minimo", "pedido_id"}
    assert d["umbral_minimo"] is None and d["pedido_id"] is None


def test_tipo_desconocido_es_invalido():
    with pytest.raises(Exception):
        EventoMovimientoStock(tipo="robado", sku="x", cantidad=1, stock_disponible=1, stock_reservado=0, stock_vendible=1)


# ------------------------------------------------------------ productor Kafka

class ProductorFalso:
    def __init__(self):
        self.producidos, self.errores, self.pendientes, self.flush_con = [], [], 0, None

    def produce(self, topico, key=None, value=None, headers=None, on_delivery=None):
        if self.errores:
            raise self.errores.pop(0)
        self.producidos.append(NS(topico=topico, key=key, value=value, headers=headers))

    def poll(self, timeout=0):
        return 0

    def flush(self, timeout=None):
        self.flush_con = timeout
        return self.pendientes


def _evento(sku="SKU-1", tipo="reservado"):
    return EventoMovimientoStock(tipo=tipo, sku=sku, cantidad=2, stock_disponible=8, stock_reservado=2, stock_vendible=6)


@pytest.fixture
def kafka():
    productor = ProductorFalso()
    p = KafkaMovimientoPublisher(productor=productor)
    yield p, productor
    p._detener.set()


def test_kafka_publica_en_el_topico_con_el_sku_como_key(kafka):
    p, productor = kafka
    p.publicar(_evento("SKU-77"))
    (m,) = productor.producidos
    assert m.topico == "inventario.movimientos" and m.key == b"SKU-77"
    assert json.loads(m.value)["sku"] == "SKU-77" and dict(m.headers)["tipo"] == b"reservado"


def test_misma_key_para_todos_los_movimientos_de_un_sku():
    assert {serializar_evento(_evento("A", t))[0] for t in ("reservado", "confirmado", "stock_bajo")} == {b"A"}


def test_kafka_reintenta_con_cola_llena_y_luego_falla(kafka):
    p, productor = kafka
    productor.errores = [BufferError()]
    p.publicar(_evento())
    assert len(productor.producidos) == 1
    productor.errores = [BufferError(), BufferError()]
    with pytest.raises(PublicacionMovimientoError, match="llena"):
        p.publicar(_evento())


def test_kafka_exception_se_traduce(kafka):
    p, productor = kafka
    productor.errores = [KafkaException(KafkaError(KafkaError.MSG_SIZE_TOO_LARGE))]
    with pytest.raises(PublicacionMovimientoError):
        p.publicar(_evento())


def test_kafka_cerrar_hace_flush(kafka):
    p, productor = kafka
    p.cerrar()
    assert productor.flush_con == 5.0


def test_configuracion_del_productor():
    cfg = configuracion_productor(Settings(DATABASE_URL="sqlite://", AZURE_TENANT_ID="t", AZURE_CLIENT_ID="c",
                                           KAFKA_BOOTSTRAP_SERVERS="k1:29092,k2:29092,k3:29092"))
    assert cfg["acks"] == "all" and cfg["enable.idempotence"] is True
    assert cfg["bootstrap.servers"].count(",") == 2 and cfg["client.id"] == "ms-inventario"


# ------------------------------------------------------------ alertas por RabbitMQ (exchange direct)

class CanalFalso:
    def __init__(self):
        self.is_closed, self.confirmando, self.exchanges, self.publicados, self.error = False, False, [], [], None

    def confirm_delivery(self):
        self.confirmando = True

    def exchange_declare(self, **kw):
        self.exchanges.append(kw)

    def basic_publish(self, **kw):
        if self.error:
            raise self.error
        self.publicados.append(kw)


class ConexionFalsa:
    def __init__(self, canal):
        self._canal, self.is_closed, self.is_open = canal, False, True

    def channel(self):
        return self._canal

    def close(self):
        self.is_closed, self.is_open = True, False


@pytest.fixture
def rabbit():
    canal = CanalFalso()
    conexiones = []

    def fabrica(_params):
        c = ConexionFalsa(canal)
        conexiones.append(c)
        return c
    p = RabbitMQAlertaStockPublisher(parametros_fn=lambda: None, fabrica_conexion=fabrica)
    return p, canal, conexiones


def test_la_alerta_va_al_exchange_direct_con_routing_key_stock_bajo(rabbit):
    p, canal, _ = rabbit
    p.publicar(_evento(tipo="stock_bajo"))
    (m,) = canal.publicados
    assert m["exchange"] == "pidealtoke.alertas" and m["routing_key"] == "stock.bajo"
    assert m["mandatory"] is True and m["properties"].delivery_mode == 2
    assert canal.confirmando and canal.exchanges[0]["exchange_type"] == "direct"
    assert json.loads(m["body"])["tipo"] == "stock_bajo"


@pytest.mark.parametrize("tipo", ["reservado", "liberado", "confirmado", "repuesto"])
def test_los_demas_movimientos_no_van_a_rabbitmq(rabbit, tipo):
    p, canal, conexiones = rabbit
    p.publicar(_evento(tipo=tipo))
    assert canal.publicados == [] and conexiones == []   # ni siquiera conecta


def test_sin_cola_destino_da_un_error_claro(rabbit):
    p, canal, _ = rabbit
    canal.error = pika.exceptions.UnroutableError([])
    with pytest.raises(PublicacionMovimientoError, match="ms-notificaciones"):
        p.publicar(_evento(tipo="stock_bajo"))


def test_reconecta_una_vez_y_luego_activa_el_enfriamiento(rabbit):
    p, canal, conexiones = rabbit
    canal.error = pika.exceptions.AMQPConnectionError()
    with pytest.raises(PublicacionMovimientoError, match="No se pudo publicar"):
        p.publicar(_evento(tipo="stock_bajo"))
    assert len(conexiones) == 2                          # intento + un reintento con conexion nueva
    with pytest.raises(PublicacionMovimientoError, match="enfriamiento"):
        p.publicar(_evento(tipo="stock_bajo"))
    assert len(conexiones) == 2                          # en enfriamiento no vuelve a conectar


# ------------------------------------------------------------ composite y fabrica

def test_composite_si_uno_falla_el_otro_recibe():
    bueno = Registro()
    with pytest.raises(OSError):
        CompositeMovimientoPublisher([Registro(error=OSError("x")), bueno]).publicar(_evento())
    assert len(bueno.eventos) == 1


def test_fabrica_sin_brokers_es_nula():
    from app.domain.ports.movimiento_publisher_port import NullMovimientoPublisher
    assert isinstance(construir_publicador(NS(KAFKA_ENABLED=False, RABBITMQ_ENABLED=False)), NullMovimientoPublisher)


def test_fabrica_con_ambos_usa_composite(monkeypatch):
    monkeypatch.setattr("app.infrastructure.messaging.kafka_movimiento_publisher.Producer", lambda c: ProductorFalso())
    monkeypatch.setattr("app.infrastructure.messaging.rabbitmq_alertas_publisher.RabbitMQAlertaStockPublisher.__init__",
                        lambda self, *a, **k: None)
    pub = construir_publicador(NS(KAFKA_ENABLED=True, RABBITMQ_ENABLED=True))
    assert isinstance(pub, CompositeMovimientoPublisher)
    pub._publicadores[0]._detener.set()
