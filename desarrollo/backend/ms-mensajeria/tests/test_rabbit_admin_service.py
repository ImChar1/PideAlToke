# RabbitAdminService probado con un canal falso (sin broker): argumentos enviados a pika y
# traduccion de errores AMQP a excepciones de dominio.

from contextlib import contextmanager
from types import SimpleNamespace

import pika.exceptions
import pytest

from app.domain.services.rabbit_admin_service import (
    ConflictoRabbitError,
    OperacionRechazadaError,
    RabbitAdminService,
    RabbitNoDisponibleError,
    RecursoNoEncontradoError,
)


class CanalFalso:
    """Registra las llamadas; `errores` = {metodo: excepcion} para simular rechazos del broker."""

    def __init__(self, errores=None):
        self.llamadas = []
        self.errores = errores or {}

    def _llamar(self, metodo, **kw):
        self.llamadas.append((metodo, kw))
        if metodo in self.errores:
            raise self.errores[metodo]

    def queue_declare(self, **kw):
        self._llamar("queue_declare", **kw)
        return SimpleNamespace(method=SimpleNamespace(queue=kw["queue"], message_count=3, consumer_count=1))

    def queue_delete(self, **kw):
        self._llamar("queue_delete", **kw)
        return SimpleNamespace(method=SimpleNamespace(message_count=5))

    def queue_purge(self, **kw):
        self._llamar("queue_purge", **kw)
        return SimpleNamespace(method=SimpleNamespace(message_count=9))

    def exchange_declare(self, **kw):
        self._llamar("exchange_declare", **kw)

    def queue_bind(self, **kw):
        self._llamar("queue_bind", **kw)

    def metodos(self):
        return [m for m, _ in self.llamadas]


def _servicio(canal):
    @contextmanager
    def abrir():
        yield canal

    return RabbitAdminService(abrir_canal_fn=abrir)


def _cola(**kw):
    base = dict(
        name="q", durable=True, auto_delete=False, queue_type="classic",
        message_ttl_ms=None, max_length=None, dead_letter_exchange=None, dead_letter_routing_key=None,
    )
    return SimpleNamespace(**{**base, **kw})


def _no_encontrado(texto="NOT_FOUND - no queue 'x' in vhost '/'"):
    return pika.exceptions.ChannelClosedByBroker(404, texto)


# ------------------------------------------------------------------ crear cola

def test_crear_cola_simple_no_envia_argumentos():
    canal = CanalFalso()
    resultado = _servicio(canal).crear_cola(_cola())

    _, kw = canal.llamadas[0]
    assert kw["queue"] == "q" and kw["durable"] is True and kw["exclusive"] is False
    assert kw["arguments"] is None
    assert resultado == {"name": "q", "messages": 3, "consumers": 1}


def test_crear_cola_con_dlq_ttl_y_longitud_envia_los_argumentos_x():
    canal = CanalFalso()
    _servicio(canal).crear_cola(_cola(
        message_ttl_ms=60000, max_length=100,
        dead_letter_exchange="dlx", dead_letter_routing_key="q.dlq",
    ))

    assert canal.llamadas[0][1]["arguments"] == {
        "x-message-ttl": 60000,
        "x-max-length": 100,
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": "q.dlq",
    }


def test_crear_cola_quorum_envia_x_queue_type():
    canal = CanalFalso()
    _servicio(canal).crear_cola(_cola(queue_type="quorum"))
    assert canal.llamadas[0][1]["arguments"] == {"x-queue-type": "quorum"}


def test_crear_cola_con_argumentos_distintos_a_los_existentes_es_conflicto():
    canal = CanalFalso({"queue_declare": pika.exceptions.ChannelClosedByBroker(
        406, "PRECONDITION_FAILED - inequivalent arg 'x-message-ttl'")})
    with pytest.raises(ConflictoRabbitError):
        _servicio(canal).crear_cola(_cola(message_ttl_ms=1))


# ------------------------------------------------------------------ obtener / eliminar / purgar

def test_obtener_cola_usa_declare_pasivo_y_devuelve_contadores():
    canal = CanalFalso()
    resultado = _servicio(canal).obtener_cola("q")

    assert canal.llamadas == [("queue_declare", {"queue": "q", "passive": True})]
    assert resultado == {"name": "q", "messages": 3, "consumers": 1}


def test_obtener_cola_inexistente_es_404():
    canal = CanalFalso({"queue_declare": _no_encontrado()})
    with pytest.raises(RecursoNoEncontradoError):
        _servicio(canal).obtener_cola("x")


def test_eliminar_cola_verifica_que_exista_y_pasa_las_guardas():
    canal = CanalFalso()
    resultado = _servicio(canal).eliminar_cola("q", if_unused=True, if_empty=True)

    assert canal.metodos() == ["queue_declare", "queue_delete"]
    assert canal.llamadas[1][1] == {"queue": "q", "if_unused": True, "if_empty": True}
    assert resultado == {"name": "q", "deleted": True, "messages_discarded": 5}


def test_eliminar_cola_inexistente_es_404_y_no_llega_a_borrar():
    canal = CanalFalso({"queue_declare": _no_encontrado()})
    with pytest.raises(RecursoNoEncontradoError):
        _servicio(canal).eliminar_cola("x")
    assert "queue_delete" not in canal.metodos()


def test_eliminar_cola_en_uso_con_if_unused_es_conflicto():
    canal = CanalFalso({"queue_delete": pika.exceptions.ChannelClosedByBroker(
        406, "PRECONDITION_FAILED - queue 'q' in use")})
    with pytest.raises(ConflictoRabbitError):
        _servicio(canal).eliminar_cola("q", if_unused=True)


def test_purgar_cola_devuelve_cuantos_mensajes_se_descartaron():
    canal = CanalFalso()
    assert _servicio(canal).purgar_cola("q") == {"name": "q", "purged_messages": 9}
    assert canal.llamadas == [("queue_purge", {"queue": "q"})]


def test_purgar_cola_inexistente_es_404():
    with pytest.raises(RecursoNoEncontradoError):
        _servicio(CanalFalso({"queue_purge": _no_encontrado()})).purgar_cola("x")


# ------------------------------------------------------------------ exchanges y bindings

def test_crear_exchange_envia_tipo_y_banderas():
    canal = CanalFalso()
    datos = SimpleNamespace(name="e", type="topic", durable=True, auto_delete=False, internal=False)
    resultado = _servicio(canal).crear_exchange(datos)

    assert canal.llamadas == [("exchange_declare", {
        "exchange": "e", "exchange_type": "topic", "durable": True, "auto_delete": False, "internal": False,
    })]
    assert resultado["type"] == "topic"


def test_crear_binding_envia_cola_exchange_y_routing_key():
    canal = CanalFalso()
    datos = SimpleNamespace(queue="q", exchange="e", routing_key="pedido.*")
    resultado = _servicio(canal).crear_binding(datos)

    assert canal.llamadas == [("queue_bind", {"queue": "q", "exchange": "e", "routing_key": "pedido.*"})]
    assert resultado == {"queue": "q", "exchange": "e", "routing_key": "pedido.*"}


def test_crear_binding_con_cola_o_exchange_inexistente_es_404():
    canal = CanalFalso({"queue_bind": _no_encontrado("NOT_FOUND - no exchange 'e' in vhost '/'")})
    with pytest.raises(RecursoNoEncontradoError):
        _servicio(canal).crear_binding(SimpleNamespace(queue="q", exchange="e", routing_key=""))


# ------------------------------------------------------------------ errores del broker

def test_acceso_denegado_es_operacion_rechazada():
    canal = CanalFalso({"exchange_declare": pika.exceptions.ChannelClosedByBroker(
        403, "ACCESS_REFUSED - exchange name 'amq.x' contains reserved prefix 'amq.*'")})
    with pytest.raises(OperacionRechazadaError):
        _servicio(canal).crear_exchange(
            SimpleNamespace(name="amq.x", type="direct", durable=True, auto_delete=False, internal=False))


def test_broker_caido_es_rabbit_no_disponible():
    @contextmanager
    def abrir():
        raise pika.exceptions.AMQPConnectionError("conexion rechazada")
        yield  # pragma: no cover

    with pytest.raises(RabbitNoDisponibleError):
        RabbitAdminService(abrir_canal_fn=abrir).obtener_cola("q")


def test_error_de_red_a_nivel_de_socket_tambien_es_no_disponible():
    @contextmanager
    def abrir():
        raise OSError("timeout")
        yield  # pragma: no cover

    with pytest.raises(RabbitNoDisponibleError):
        RabbitAdminService(abrir_canal_fn=abrir).obtener_cola("q")
