# Consumidor Kafka probado con un Consumer FALSO (sin cluster): commit manual, reintentos con backoff,
# descarte de invalidos, reconstruccion desde el principio, errores fatales y cierre limpio.

import threading
import time
from types import SimpleNamespace as NS

import pytest
from confluent_kafka import OFFSET_BEGINNING, KafkaError, KafkaException

from app.infrastructure.kafka.kafka_consumer import (
    ConsumerConfig,
    ConsumerManager,
    ConsumerWorker,
    MensajeKafka,
    NonRetryableError,
    calcular_espera,
    procesar_mensaje,
)


def config(**kw):
    base = dict(topico="pedidos.eventos", grupo="analitica-ventas", bootstrap_servers="k1:29092,k2:29092,k3:29092",
                client_id="ms-analitica", concurrencia=3, max_reintentos=2, espera_base=1.0, espera_maxima=10.0,
                reconexion_maxima=5.0, reconstruir_al_iniciar=True, session_timeout_ms=10000, max_poll_interval_ms=300000)
    base.update(kw)
    return ConsumerConfig(**base)


def msg(offset=0, valor=b"{}"):
    return MensajeKafka("pedidos.eventos", 0, offset, b"1", valor)


# ------------------------------------------------------------ propiedades del consumer

def test_propiedades_commit_manual_y_grupo():
    p = config().propiedades(miembro=2)
    assert p["group.id"] == "analitica-ventas" and p["enable.auto.commit"] is False
    assert p["auto.offset.reset"] == "earliest" and p["client.id"] == "ms-analitica-analitica-ventas-2"
    assert p["bootstrap.servers"].count(",") == 2


# ------------------------------------------------------------ procesar_mensaje (reintentos)

def test_ok_no_duerme_ni_cuenta_errores():
    dormidos = []
    assert procesar_mensaje(msg(), lambda m: None, config(), dormidos.append) == "ok"
    assert dormidos == []


def test_invalido_no_reintenta_y_se_cuenta(caplog):
    invalidos, dormidos = [], []

    def handler(m):
        raise NonRetryableError("json roto")
    r = procesar_mensaje(msg(5), handler, config(), dormidos.append, al_invalido=invalidos.append)
    assert r == "invalido" and invalidos == ["pedidos.eventos"] and dormidos == []
    assert "offset=5" in caplog.text and "json roto" in caplog.text


def test_reintenta_con_backoff_y_termina_ok():
    intentos, dormidos = [], []

    def handler(m):
        intentos.append(1)
        if len(intentos) < 3:
            raise ConnectionError("transitorio")
    assert procesar_mensaje(msg(), handler, config(max_reintentos=3), dormidos.append, jitter=False) == "ok"
    assert len(intentos) == 3 and dormidos == [1.0, 2.0]     # base * 2^(intento-1)


def test_agota_reintentos_y_descarta_con_log(caplog):
    fallidos, intentos = [], []

    def handler(m):
        intentos.append(1)
        raise RuntimeError("siempre falla")
    r = procesar_mensaje(msg(), handler, config(max_reintentos=2), lambda s: None, al_fallido=fallidos.append)
    assert r == "fallido" and len(intentos) == 3 and fallidos == ["pedidos.eventos"]
    assert "Reintentos agotados" in caplog.text


def test_backoff_exponencial_con_tope_y_jitter():
    assert [calcular_espera(i, 1.0, 10.0, jitter=False) for i in (1, 2, 3, 4, 5)] == [1.0, 2.0, 4.0, 8.0, 10.0]
    for _ in range(50):
        assert 2.0 <= calcular_espera(3, 1.0, 10.0) <= 4.0


# ------------------------------------------------------------ Consumer falso

class ConsumerFalso:
    def __init__(self, mensajes=(), error_al_poll=None):
        self.cola = list(mensajes)
        self.commits, self.cerrado, self.suscrito = [], False, None
        self.asignadas = []
        self.error_al_poll = error_al_poll
        self.on_assign = None

    def subscribe(self, topicos, on_assign=None, on_revoke=None, on_lost=None):
        self.suscrito = topicos
        self.on_assign = on_assign

    def poll(self, timeout):
        if self.error_al_poll:
            e, self.error_al_poll = self.error_al_poll, None
            raise e
        if self.cola:
            return self.cola.pop(0)
        time.sleep(0.01)
        return None

    def commit(self, message=None, asynchronous=False):
        self.commits.append(message.offset())

    def incremental_assign(self, tps):
        self.asignadas.extend(tps)

    def incremental_unassign(self, tps):
        pass

    def close(self):
        self.cerrado = True


def mensaje_kafka(offset, valor=b"x", error=None):
    return NS(topic=lambda: "pedidos.eventos", partition=lambda: 0, offset=lambda: offset,
              key=lambda: b"1", value=lambda: valor, error=lambda: error)


def correr(consumer, handler, cfg=None, esperar=lambda: False, **kw):
    w = ConsumerWorker("w", 1, cfg or config(), handler, fabrica_consumer=lambda props: consumer, **kw)
    w.start()
    for _ in range(300):
        if esperar():
            break
        time.sleep(0.01)
    w.detener()
    w.join(3)
    assert not w.is_alive()
    return w


def test_consume_y_hace_commit_de_cada_mensaje():
    vistos = []
    c = ConsumerFalso([mensaje_kafka(0, b"a"), mensaje_kafka(1, b"b")])
    correr(c, lambda m: vistos.append((m.offset, m.value)), esperar=lambda: len(c.commits) == 2)
    assert vistos == [(0, b"a"), (1, b"b")] and c.commits == [0, 1]
    assert c.suscrito == ["pedidos.eventos"] and c.cerrado is True


def test_un_mensaje_invalido_se_salta_con_commit_y_el_consumo_sigue():
    vistos, invalidos = [], []

    def handler(m):
        if m.offset == 0:
            raise NonRetryableError("roto")
        vistos.append(m.offset)
    c = ConsumerFalso([mensaje_kafka(0), mensaje_kafka(1)])
    correr(c, handler, esperar=lambda: len(c.commits) == 2, al_invalido=invalidos.append)
    assert vistos == [1] and c.commits == [0, 1] and invalidos == ["pedidos.eventos"]


def test_error_no_fatal_se_ignora():
    c = ConsumerFalso([mensaje_kafka(0, error=KafkaError(KafkaError._TRANSPORT)), mensaje_kafka(1)])
    vistos = []
    correr(c, lambda m: vistos.append(m.offset), esperar=lambda: c.commits == [1])
    assert vistos == [1]


def test_error_fatal_recrea_el_consumer():
    creados = []

    def fabrica(props):
        n = len(creados)
        c = ConsumerFalso([mensaje_kafka(0, error=KafkaError(KafkaError._FATAL, fatal=True))] if n == 0 else [mensaje_kafka(1)])
        creados.append(c)
        return c
    w = ConsumerWorker("w", 1, config(reconexion_maxima=0.05), lambda m: None, fabrica_consumer=fabrica)
    w.start()
    for _ in range(400):
        if len(creados) >= 2 and creados[1].commits:
            break
        time.sleep(0.01)
    w.detener()
    w.join(3)
    assert len(creados) >= 2 and creados[0].cerrado and creados[1].commits == [1]


def test_exception_del_poll_recrea_el_consumer():
    creados = []

    def fabrica(props):
        c = ConsumerFalso([mensaje_kafka(0)], error_al_poll=RuntimeError("boom") if not creados else None)
        creados.append(c)
        return c
    w = ConsumerWorker("w", 1, config(reconexion_maxima=0.05), lambda m: None, fabrica_consumer=fabrica)
    w.start()
    for _ in range(400):
        if len(creados) >= 2 and creados[1].commits:
            break
        time.sleep(0.01)
    w.detener()
    w.join(3)
    assert len(creados) >= 2 and creados[1].commits == [0]


# ------------------------------------------------------------ rebalanceo / reconstruccion

def asignar(consumer, worker, particiones):
    worker._al_asignar(consumer, particiones)


def test_primera_asignacion_lee_desde_el_principio_la_segunda_no():
    w = ConsumerWorker("w", 1, config(), lambda m: None)
    c = ConsumerFalso()
    p = NS(topic="pedidos.eventos", partition=0, offset=-1001)
    asignar(c, w, [p])
    assert p.offset == OFFSET_BEGINNING
    p2 = NS(topic="pedidos.eventos", partition=0, offset=-1001)    # rebalanceo: vuelve a recibir la misma
    asignar(c, w, [p2])
    assert p2.offset == -1001                                      # se respeta el offset confirmado
    assert len(c.asignadas) == 2


def test_sin_reconstruccion_no_se_toca_el_offset():
    w = ConsumerWorker("w", 1, config(reconstruir_al_iniciar=False), lambda m: None)
    p = NS(topic="pedidos.eventos", partition=1, offset=-1001)
    asignar(ConsumerFalso(), w, [p])
    assert p.offset == -1001


def test_revocar_y_perder_desasignan():
    w = ConsumerWorker("w", 1, config(), lambda m: None)
    llamadas = []
    c = NS(incremental_unassign=lambda tps: llamadas.append(len(tps)))
    p = NS(topic="t", partition=0)
    w._al_revocar(c, [p])
    w._al_perder(c, [p, p])
    assert llamadas == [1, 2]


# ------------------------------------------------------------ manager

def test_manager_levanta_un_worker_por_miembro_y_los_detiene():
    consumers = []

    def fabrica(props):
        c = ConsumerFalso()
        consumers.append((props["client.id"], c))
        return c
    m = ConsumerManager(config(concurrencia=3), lambda x: None, fabrica_consumer=fabrica)
    m.iniciar()
    for _ in range(300):
        if len(consumers) == 3:
            break
        time.sleep(0.01)
    assert sorted(n for n, _ in consumers) == [f"ms-analitica-analitica-ventas-{i}" for i in (1, 2, 3)]
    m.detener()
    assert all(c.cerrado for _, c in consumers)


# ------------------------------------------------------------ commit durante un rebalanceo

def test_commit_fallido_por_rebalanceo_no_recrea_el_consumer(caplog):
    creados = []

    class ConsumerRebalanceo(ConsumerFalso):
        def commit(self, message=None, asynchronous=False):
            if message.offset() == 0:
                raise KafkaException(KafkaError(KafkaError.REBALANCE_IN_PROGRESS))
            super().commit(message=message, asynchronous=asynchronous)

    def fabrica(props):
        c = ConsumerRebalanceo([mensaje_kafka(0), mensaje_kafka(1)])
        creados.append(c)
        return c
    w = ConsumerWorker("w", 1, config(), lambda m: None, fabrica_consumer=fabrica)
    w.start()
    for _ in range(300):
        if creados and creados[0].commits == [1]:
            break
        time.sleep(0.01)
    w.detener()
    w.join(3)
    assert len(creados) == 1 and creados[0].commits == [1]      # siguio con el mismo Consumer
    assert "commit omitido" in caplog.text


def test_commit_con_error_inesperado_si_recrea_el_consumer():
    creados = []

    class ConsumerRoto(ConsumerFalso):
        def commit(self, message=None, asynchronous=False):
            raise KafkaException(KafkaError(KafkaError.TOPIC_AUTHORIZATION_FAILED))

    def fabrica(props):
        c = ConsumerRoto([mensaje_kafka(0)]) if not creados else ConsumerFalso([mensaje_kafka(1)])
        creados.append(c)
        return c
    w = ConsumerWorker("w", 1, config(reconexion_maxima=0.05), lambda m: None, fabrica_consumer=fabrica)
    w.start()
    for _ in range(400):
        if len(creados) >= 2 and creados[1].commits:
            break
        time.sleep(0.01)
    w.detener()
    w.join(3)
    assert len(creados) >= 2 and creados[1].commits == [1]
