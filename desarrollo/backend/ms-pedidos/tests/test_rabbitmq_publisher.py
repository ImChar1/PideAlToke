# Publicador RabbitMQ (pika) probado con dobles: no hace falta un broker real.
# Verifica Publisher Confirms, mensajes persistentes, reintento de conexion y enfriamiento.

import pika
import pika.exceptions
import pytest

import app.infrastructure.messaging.rabbitmq_publisher as pub_module
from app.core.config import settings
from app.domain.ports.evento_publisher_port import (
    EventoNoEnrutableError,
    NullEventPublisher,
    PublicacionEventoError,
)
from app.schemas.schema_eventos import EventoPedidoSchema


class FakeCanal:
    def __init__(self):
        self.is_closed = False
        self.confirmando = False
        self.exchanges = []
        self.publicados = []
        self.error_al_publicar = None

    def confirm_delivery(self):
        self.confirmando = True

    def exchange_declare(self, **kwargs):
        self.exchanges.append(kwargs)

    def basic_publish(self, **kwargs):
        if self.error_al_publicar:
            raise self.error_al_publicar
        self.publicados.append(kwargs)


class FakeConexion:
    def __init__(self, canal):
        self._canal = canal
        self.is_closed = False
        self.is_open = True

    def channel(self):
        return self._canal

    def close(self):
        self.is_closed = True
        self.is_open = False


class FabricaConexiones:
    """Sustituye a pika.BlockingConnection: devuelve conexiones fake o lanza los errores indicados."""

    def __init__(self, errores_de_conexion=()):
        self.errores = list(errores_de_conexion)
        self.llamadas = 0
        self.canal = FakeCanal()

    def __call__(self, parametros):
        self.llamadas += 1
        if self.errores:
            raise self.errores.pop(0)
        return FakeConexion(self.canal)


def _evento():
    return EventoPedidoSchema(
        tipo="creado", pedido_id=7, cliente_id="c1", estado="PENDIENTE", monto_total=10.0,
        items=[{"sku": "A", "cantidad": 1, "precio_unitario": 10.0}],
    )


def _publicador(monkeypatch, fabrica):
    monkeypatch.setattr(pub_module.pika, "BlockingConnection", fabrica)
    return pub_module.RabbitMQPedidoEventPublisher()


def test_publica_con_confirms_mandatory_y_mensaje_persistente(monkeypatch):
    fabrica = FabricaConexiones()
    publicador = _publicador(monkeypatch, fabrica)
    evento = _evento()

    publicador.publicar(evento)

    canal = fabrica.canal
    assert canal.confirmando is True                       # Publisher Confirms activados
    assert canal.exchanges[0]["exchange_type"] == "topic"  # el exchange se declara al conectar
    assert canal.exchanges[0]["durable"] is True
    enviado = canal.publicados[0]
    assert enviado["exchange"] == settings.RABBITMQ_EXCHANGE_PEDIDOS
    assert enviado["routing_key"] == settings.RABBITMQ_RK_PEDIDO_CREADO
    assert enviado["mandatory"] is True
    assert enviado["properties"].delivery_mode == 2        # persistente
    assert enviado["properties"].message_id == evento.event_id
    assert enviado["properties"].content_type == "application/json"
    assert b'"pedido_id":7' in enviado["body"]


def test_reutiliza_la_conexion_entre_publicaciones(monkeypatch):
    fabrica = FabricaConexiones()
    publicador = _publicador(monkeypatch, fabrica)

    publicador.publicar(_evento())
    publicador.publicar(_evento())

    assert fabrica.llamadas == 1
    assert len(fabrica.canal.publicados) == 2


def test_mensaje_sin_ruta_lanza_evento_no_enrutable_y_no_activa_el_enfriamiento(monkeypatch):
    fabrica = FabricaConexiones()
    publicador = _publicador(monkeypatch, fabrica)
    fabrica.canal.error_al_publicar = pika.exceptions.UnroutableError([])

    with pytest.raises(EventoNoEnrutableError):
        publicador.publicar(_evento())

    fabrica.canal.error_al_publicar = None
    publicador.publicar(_evento())  # sigue disponible: no fue un problema de conexion
    assert len(fabrica.canal.publicados) == 1


def test_nack_del_broker_lanza_error_de_publicacion(monkeypatch):
    fabrica = FabricaConexiones()
    publicador = _publicador(monkeypatch, fabrica)
    fabrica.canal.error_al_publicar = pika.exceptions.NackError([])

    with pytest.raises(PublicacionEventoError):
        publicador.publicar(_evento())


def test_reintenta_una_vez_si_la_primera_conexion_falla(monkeypatch):
    fabrica = FabricaConexiones(errores_de_conexion=[pika.exceptions.AMQPConnectionError("caido")])
    publicador = _publicador(monkeypatch, fabrica)

    publicador.publicar(_evento())

    assert fabrica.llamadas == 2
    assert len(fabrica.canal.publicados) == 1


def test_broker_caido_lanza_error_y_luego_hay_enfriamiento(monkeypatch):
    fabrica = FabricaConexiones(errores_de_conexion=[pika.exceptions.AMQPConnectionError("caido")] * 10)
    publicador = _publicador(monkeypatch, fabrica)

    with pytest.raises(PublicacionEventoError):
        publicador.publicar(_evento())
    intentos = fabrica.llamadas
    assert intentos == 2  # intento inicial + 1 reintento

    with pytest.raises(PublicacionEventoError):
        publicador.publicar(_evento())
    assert fabrica.llamadas == intentos  # en enfriamiento ni siquiera intenta conectar


def test_con_rabbitmq_apagado_el_publicador_es_nulo(monkeypatch):
    monkeypatch.setattr(pub_module, "_publisher", None)
    monkeypatch.setattr(settings, "RABBITMQ_ENABLED", False)

    assert isinstance(pub_module.obtener_event_publisher(), NullEventPublisher)
    pub_module.obtener_event_publisher().publicar(_evento())  # no hace nada ni falla
    monkeypatch.setattr(pub_module, "_publisher", None)
