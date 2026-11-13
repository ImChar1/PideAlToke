# Topologia de ms-notificaciones: 2 colas de trabajo, cada una con su DLQ, sobre exchanges topic y direct.
# Sin broker: un canal falso registra las llamadas.

from types import SimpleNamespace as NS

from app.core.config import Settings
from app.infrastructure.messaging.rabbitmq_config import construir_topologia, declarar_topologia, parametros_conexion

CFG = Settings(AZURE_TENANT_ID="t", AZURE_CLIENT_ID="c")


class Canal:
    def __init__(self):
        self.llamadas = []

    def exchange_declare(self, **kw):
        self.llamadas.append(("exchange", kw))

    def queue_declare(self, **kw):
        self.llamadas.append(("queue", kw))

    def queue_bind(self, **kw):
        self.llamadas.append(("bind", kw))


def test_exchanges_topic_y_direct():
    t = construir_topologia(CFG)
    assert {(e.nombre, e.tipo) for e in t.exchanges} == {
        ("pedidos.events", "topic"), ("pidealtoke.alertas", "direct"), ("pidealtoke.dlx", "direct"),
    }
    assert all(e.durable for e in t.exchanges)


def test_cada_cola_de_trabajo_tiene_su_dlq():
    t = construir_topologia(CFG)
    colas = {c.nombre: c for c in t.colas}
    assert set(colas) == {"notificaciones.pedidos", "notificaciones.pedidos.dlq", "alertas.stock", "alertas.stock.dlq"}
    for trabajo in ("notificaciones.pedidos", "alertas.stock"):
        assert colas[trabajo].argumentos == {
            "x-dead-letter-exchange": "pidealtoke.dlx", "x-dead-letter-routing-key": f"{trabajo}.dlq",
        }
        assert colas[f"{trabajo}.dlq"].argumentos == {}     # la DLQ no tiene dead-lettering propio
    assert all(c.durable for c in t.colas)


def test_bindings_de_negocio():
    b = {(x.cola, x.exchange, x.routing_key) for x in construir_topologia(CFG).bindings}
    assert ("notificaciones.pedidos", "pedidos.events", "pedido.confirmado") in b
    assert ("notificaciones.pedidos", "pedidos.events", "pedido.cancelado") in b
    assert ("alertas.stock", "pidealtoke.alertas", "stock.bajo") in b


def test_el_binding_de_cada_dlq_coincide_con_su_dead_letter_routing_key():
    t = construir_topologia(CFG)
    for trabajo in (c for c in t.colas if "x-dead-letter-routing-key" in c.argumentos):
        clave = trabajo.argumentos["x-dead-letter-routing-key"]
        assert any(b.cola == clave and b.exchange == "pidealtoke.dlx" and b.routing_key == clave for b in t.bindings)


def test_no_se_bindea_pedido_creado():
    claves = {b.routing_key for b in construir_topologia(CFG).bindings}
    assert "pedido.creado" not in claves and "pedido.*" not in claves


def test_los_nombres_salen_de_la_configuracion():
    cfg = Settings(AZURE_TENANT_ID="t", AZURE_CLIENT_ID="c", RABBITMQ_QUEUE_ALERTAS_STOCK="otra.cola",
                   RABBITMQ_QUEUE_ALERTAS_STOCK_DLQ="otra.cola.dlq")
    assert {c.nombre for c in construir_topologia(cfg).colas} >= {"otra.cola", "otra.cola.dlq"}


def test_declara_en_orden_exchanges_colas_bindings():
    canal = Canal()
    declarar_topologia(canal, construir_topologia(CFG))
    orden = [tipo for tipo, _ in canal.llamadas]
    assert orden == ["exchange"] * 3 + ["queue"] * 4 + ["bind"] * 5
    cola_trabajo = next(kw for tipo, kw in canal.llamadas if tipo == "queue" and kw["queue"] == "alertas.stock")
    assert cola_trabajo["durable"] is True and cola_trabajo["arguments"]["x-dead-letter-exchange"] == "pidealtoke.dlx"
    dlq = next(kw for tipo, kw in canal.llamadas if tipo == "queue" and kw["queue"] == "alertas.stock.dlq")
    assert dlq["arguments"] is None


def test_parametros_de_conexion():
    p = parametros_conexion(NS(RABBITMQ_HOST="rabbit", RABBITMQ_PORT=5673, RABBITMQ_VHOST="/", RABBITMQ_USER="u",
                               RABBITMQ_PASSWORD="p", RABBITMQ_HEARTBEAT=30, RABBITMQ_CONNECTION_TIMEOUT=3.0))
    assert (p.host, p.port, p.heartbeat) == ("rabbit", 5673, 30) and p.connection_attempts == 1
