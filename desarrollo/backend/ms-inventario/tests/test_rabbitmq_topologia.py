# La topologia (exchanges, colas, bindings, DLQ) se construye desde la configuracion y se declara
# en el orden correcto. Sin broker: se usa un canal falso que registra las llamadas.

from types import SimpleNamespace

from app.infrastructure.messaging.rabbitmq_config import (
    construir_topologia,
    declarar_topologia,
    parametros_conexion,
)

CFG = SimpleNamespace(
    RABBITMQ_EXCHANGE_PEDIDOS="pedidos.events",
    RABBITMQ_EXCHANGE_DLX="mi.dlx",
    RABBITMQ_QUEUE_PEDIDOS="mi.cola",
    RABBITMQ_QUEUE_PEDIDOS_DLQ="mi.cola.dlq",
    RABBITMQ_BINDING_PEDIDOS="pedido.*",
    RABBITMQ_HOST="rabbit.local",
    RABBITMQ_PORT=5673,
    RABBITMQ_VHOST="/",
    RABBITMQ_USER="u",
    RABBITMQ_PASSWORD="p",
    RABBITMQ_HEARTBEAT=30,
    RABBITMQ_CONNECTION_TIMEOUT=3.0,
)


class CanalGrabador:
    def __init__(self):
        self.llamadas = []

    def exchange_declare(self, **kw):
        self.llamadas.append(("exchange_declare", kw))

    def queue_declare(self, **kw):
        self.llamadas.append(("queue_declare", kw))

    def queue_bind(self, **kw):
        self.llamadas.append(("queue_bind", kw))


def test_los_nombres_salen_de_la_configuracion():
    t = construir_topologia(CFG)
    assert {(e.nombre, e.tipo) for e in t.exchanges} == {("pedidos.events", "topic"), ("mi.dlx", "direct")}
    assert {c.nombre for c in t.colas} == {"mi.cola", "mi.cola.dlq"}


def test_la_cola_de_trabajo_tiene_dlx_y_dead_letter_routing_key():
    t = construir_topologia(CFG)
    trabajo = next(c for c in t.colas if c.nombre == "mi.cola")
    assert trabajo.argumentos == {
        "x-dead-letter-exchange": "mi.dlx",
        "x-dead-letter-routing-key": "mi.cola.dlq",
    }
    dlq = next(c for c in t.colas if c.nombre == "mi.cola.dlq")
    assert dlq.argumentos == {}  # la DLQ no tiene dead-lettering propio


def test_el_binding_de_la_dlq_coincide_con_la_dead_letter_routing_key():
    # El DLX es DIRECT: si la clave del binding no es exactamente la x-dead-letter-routing-key,
    # los mensajes rechazados se pierden en silencio.
    t = construir_topologia(CFG)
    trabajo = next(c for c in t.colas if c.nombre == "mi.cola")
    binding_dlq = next(b for b in t.bindings if b.cola == "mi.cola.dlq")
    assert binding_dlq.exchange == "mi.dlx"
    assert binding_dlq.routing_key == trabajo.argumentos["x-dead-letter-routing-key"]


def test_la_cola_de_trabajo_se_bindea_al_exchange_de_pedidos_con_el_patron():
    t = construir_topologia(CFG)
    b = next(b for b in t.bindings if b.cola == "mi.cola")
    assert (b.exchange, b.routing_key) == ("pedidos.events", "pedido.*")


def test_declara_exchanges_luego_colas_luego_bindings_y_todo_durable():
    canal = CanalGrabador()
    declarar_topologia(canal, construir_topologia(CFG))

    tipos = [nombre for nombre, _ in canal.llamadas]
    assert tipos == ["exchange_declare"] * 2 + ["queue_declare"] * 2 + ["queue_bind"] * 2
    for nombre, kw in canal.llamadas:
        if nombre != "queue_bind":
            assert kw["durable"] is True
    cola = next(kw for n, kw in canal.llamadas if n == "queue_declare" and kw["queue"] == "mi.cola")
    assert cola["arguments"]["x-dead-letter-exchange"] == "mi.dlx"
    dlq = next(kw for n, kw in canal.llamadas if n == "queue_declare" and kw["queue"] == "mi.cola.dlq")
    assert dlq["arguments"] is None


def test_parametros_de_conexion_usan_la_configuracion():
    p = parametros_conexion(CFG)
    assert (p.host, p.port, p.virtual_host) == ("rabbit.local", 5673, "/")
    assert (p.credentials.username, p.credentials.password) == ("u", "p")
    assert p.heartbeat == 30
