# Consumidor RabbitMQ: ACK manual, backoff exponencial, NACK sin requeue (-> DLQ), workers y reconexion.
# Todo con dobles de pika: no hace falta un broker.

import threading
from types import SimpleNamespace

import pika.exceptions

from app.infrastructure.messaging.rabbitmq_config import Topologia
from app.infrastructure.messaging.rabbitmq_consumer import (
    ConsumerConfig,
    ConsumerManager,
    NonRetryableError,
    calcular_espera,
    procesar_mensaje,
)

CONFIG = ConsumerConfig(
    cola="q", prefetch=7, concurrencia=2, max_reintentos=3,
    espera_base=1.0, espera_maxima=5.0, reconexion_maxima=0.05,
)


class CanalFalso:
    """Canal minimo: registra ack/nack y simula start_consuming bloqueante hasta stop_consuming."""

    def __init__(self):
        self.acks, self.nacks = [], []
        self.qos = None
        self.consumo = None
        self.is_open = True
        self.escuchando = threading.Event()
        self._parar = threading.Event()

    def basic_ack(self, delivery_tag, multiple=False):
        self.acks.append(delivery_tag)

    def basic_nack(self, delivery_tag, multiple=False, requeue=True):
        self.nacks.append((delivery_tag, requeue))

    def basic_qos(self, prefetch_count=0, **kw):
        self.qos = prefetch_count

    def basic_consume(self, queue, on_message_callback, auto_ack=False, **kw):
        self.consumo = {"queue": queue, "callback": on_message_callback, "auto_ack": auto_ack}

    def start_consuming(self):
        self.escuchando.set()
        self._parar.wait(5)

    def stop_consuming(self):
        self._parar.set()


class ConexionFalsa:
    def __init__(self, canal):
        self.canal = canal
        self.is_open = True
        self.dormidos = []

    def channel(self):
        return self.canal

    def sleep(self, segundos):
        self.dormidos.append(segundos)

    def add_callback_threadsafe(self, cb):
        cb()  # en pika real se ejecuta en el hilo del consumidor; aqui basta con ejecutarlo

    def close(self):
        self.is_open = False


def _msg(tag=1):
    return SimpleNamespace(delivery_tag=tag, routing_key="pedido.creado"), SimpleNamespace(message_id="m-1")


def _procesar(handler, canal=None):
    canal = canal or CanalFalso()
    metodo, props = _msg()
    esperas = []
    procesar_mensaje(canal, metodo, props, b"{}", handler, CONFIG, esperas.append, jitter=False)
    return canal, esperas


# ------------------------------------------------------------------ backoff

def test_backoff_exponencial_con_tope():
    assert [calcular_espera(i, 1.0, 5.0, jitter=False) for i in (1, 2, 3, 4, 5)] == [1.0, 2.0, 4.0, 5.0, 5.0]


def test_jitter_queda_entre_la_mitad_y_el_total():
    for _ in range(50):
        assert 2.0 <= calcular_espera(3, 1.0, 100.0) <= 4.0  # backoff = 4s -> [2, 4]


# ------------------------------------------------------------------ ACK / NACK / reintentos

def test_handler_ok_hace_ack_sin_reintentos():
    llamadas = []
    canal, esperas = _procesar(lambda *a: llamadas.append(a))
    assert canal.acks == [1] and canal.nacks == [] and esperas == [] and len(llamadas) == 1


def test_mensaje_irrecuperable_va_a_la_dlq_sin_reintentos():
    def handler(*a):
        raise NonRetryableError("json roto")

    canal, esperas = _procesar(handler)
    assert canal.nacks == [(1, False)]  # requeue=False -> dead-letter
    assert canal.acks == [] and esperas == []


def test_reintenta_con_backoff_y_hace_ack_si_luego_funciona():
    intentos = []

    def handler(*a):
        intentos.append(1)
        if len(intentos) < 3:
            raise RuntimeError("fallo transitorio")

    canal, esperas = _procesar(handler)
    assert len(intentos) == 3
    assert esperas == [1.0, 2.0]  # backoff exponencial entre intentos
    assert canal.acks == [1] and canal.nacks == []


def test_agotados_los_reintentos_hace_nack_sin_requeue(caplog):
    intentos = []

    def handler(*a):
        intentos.append(1)
        raise RuntimeError("siempre falla")

    with caplog.at_level("ERROR"):
        canal, esperas = _procesar(handler)

    assert len(intentos) == 1 + CONFIG.max_reintentos       # intento inicial + reintentos
    assert esperas == [1.0, 2.0, 4.0]
    assert canal.nacks == [(1, False)] and canal.acks == []  # a la DLQ, nunca requeue
    assert any("DLQ" in r.getMessage() for r in caplog.records)  # queda registrado en el log


def test_sin_reintentos_configurados_el_primer_fallo_va_a_la_dlq():
    config = ConsumerConfig("q", 1, 1, 0, 1.0, 5.0, 1.0)
    canal = CanalFalso()
    metodo, props = _msg()

    def handler(*a):
        raise RuntimeError("x")

    procesar_mensaje(canal, metodo, props, b"", handler, config, lambda s: None, jitter=False)
    assert canal.nacks == [(1, False)]


# ------------------------------------------------------------------ workers

def _topologia_vacia():
    return Topologia(exchanges=(), colas=(), bindings=())


def _esperar(condicion, segundos=3.0):
    fin = threading.Event()
    for _ in range(int(segundos / 0.01)):
        if condicion():
            return True
        fin.wait(0.01)
    return False


def test_el_manager_levanta_workers_con_prefetch_ack_manual_y_los_detiene():
    canales = []

    def fabrica(_params):
        canal = CanalFalso()
        canales.append(canal)
        return ConexionFalsa(canal)

    manager = ConsumerManager(
        CONFIG, handler=lambda *a: None,
        parametros_fn=lambda: None, topologia_fn=_topologia_vacia, fabrica_conexion=fabrica,
    )
    manager.iniciar()
    try:
        assert _esperar(lambda: len(canales) == 2 and all(c.escuchando.is_set() for c in canales))
        for canal in canales:                       # concurrencia=2 -> 2 consumidores sobre la misma cola
            assert canal.qos == 7                   # prefetch
            assert canal.consumo["queue"] == "q"
            assert canal.consumo["auto_ack"] is False   # ACK manual
    finally:
        manager.detener(timeout=3)

    assert all(c._parar.is_set() for c in canales)


def test_el_callback_registrado_procesa_mensajes_con_ack():
    canales = []

    def fabrica(_params):
        canal = CanalFalso()
        canales.append(canal)
        return ConexionFalsa(canal)

    config = ConsumerConfig("q", 1, 1, 0, 1.0, 5.0, 0.05)
    manager = ConsumerManager(
        config, handler=lambda *a: None,
        parametros_fn=lambda: None, topologia_fn=_topologia_vacia, fabrica_conexion=fabrica,
    )
    manager.iniciar()
    try:
        assert _esperar(lambda: canales and canales[0].escuchando.is_set())
        metodo, props = _msg(tag=42)
        canales[0].consumo["callback"](canales[0], metodo, props, b"{}")
        assert canales[0].acks == [42]
    finally:
        manager.detener(timeout=3)


def test_el_worker_se_reconecta_tras_un_fallo_de_conexion():
    intentos = []
    canales = []

    def fabrica(_params):
        intentos.append(1)
        if len(intentos) == 1:
            raise pika.exceptions.AMQPConnectionError("broker caido")
        canal = CanalFalso()
        canales.append(canal)
        return ConexionFalsa(canal)

    config = ConsumerConfig("q", 1, 1, 0, 1.0, 5.0, 0.05)
    manager = ConsumerManager(
        config, handler=lambda *a: None,
        parametros_fn=lambda: None, topologia_fn=_topologia_vacia, fabrica_conexion=fabrica,
    )
    manager.iniciar()
    try:
        assert _esperar(lambda: canales and canales[0].escuchando.is_set())
        assert len(intentos) == 2  # el primero fallo, el segundo consumio
    finally:
        manager.detener(timeout=3)
