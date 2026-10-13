# Consumidor RabbitMQ (pika): ACK manual, reintentos con backoff exponencial y DLQ.
#
# Flujo por mensaje (ver `procesar_mensaje`):
#   handler OK                         -> basic_ack
#   handler lanza NonRetryableError    -> basic_nack(requeue=False) -> DLQ (sin reintentos: reintentar no lo arregla)
#   handler lanza otra excepcion       -> reintenta hasta RABBITMQ_MAX_RETRIES veces con espera
#                                         base * 2^(intento-1) (tope y jitter) y, si se agotan,
#                                         basic_nack(requeue=False) -> DLQ. Siempre se loguea.
# `requeue=False` es lo que dispara el dead-lettering (x-dead-letter-exchange de la cola de trabajo).
#
# Entrega "al menos una vez": si el proceso o la conexion caen con mensajes sin ACK, el broker los
# vuelve a entregar. Por eso los handlers deben ser IDEMPOTENTES (el evento trae `event_id`).
#
# Concurrencia: pika.BlockingConnection no es thread-safe, asi que cada hilo (ConsumerWorker) abre SU
# conexion y su canal y todos compiten por la misma cola. `prefetch` limita los mensajes sin ACK por
# consumidor (reparto equitativo y tope de memoria).
#
# La espera entre reintentos usa `connection.sleep()` y NO `time.sleep()`: sigue atendiendo los
# heartbeats del broker mientras espera, asi la conexion no se pierde durante el backoff.

import logging
import random
import threading
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

import pika

from app.infrastructure.messaging.rabbitmq_config import (
    construir_topologia,
    declarar_topologia,
    parametros_conexion,
)

logger = logging.getLogger(__name__)


class NonRetryableError(Exception):
    """Mensaje irrecuperable (JSON invalido, contrato roto...): va directo a la DLQ sin reintentos."""


# handler(cuerpo, propiedades, metodo) -> None. Debe lanzar excepcion si NO pudo procesar el mensaje.
Handler = Callable[[bytes, "pika.BasicProperties", "pika.spec.Basic.Deliver"], None]


@dataclass(frozen=True)
class ConsumerConfig:
    cola: str
    prefetch: int
    concurrencia: int
    max_reintentos: int          # reintentos DESPUES del primer intento
    espera_base: float           # segundos
    espera_maxima: float         # tope de la espera entre reintentos
    reconexion_maxima: float     # tope del backoff al reconectar con el broker

    @classmethod
    def desde_settings(cls, cfg) -> "ConsumerConfig":
        return cls(
            cola=cfg.RABBITMQ_QUEUE_PEDIDOS,
            prefetch=cfg.RABBITMQ_CONSUMER_PREFETCH,
            concurrencia=cfg.RABBITMQ_CONSUMER_CONCURRENCY,
            max_reintentos=cfg.RABBITMQ_MAX_RETRIES,
            espera_base=cfg.RABBITMQ_RETRY_BASE_SECONDS,
            espera_maxima=cfg.RABBITMQ_RETRY_MAX_SECONDS,
            reconexion_maxima=cfg.RABBITMQ_RECONNECT_MAX_SECONDS,
        )


def calcular_espera(intento: int, base: float, maximo: float, jitter: bool = True) -> float:
    """
    Backoff exponencial: base * 2^(intento-1), con tope `maximo`.
    Con jitter ("equal jitter") la espera cae en [mitad, total]: evita que varios consumidores
    reintenten todos en el mismo instante.
    """
    espera = min(maximo, base * (2 ** (intento - 1)))
    if jitter:
        espera = espera / 2 + random.uniform(0, espera / 2)
    return espera


def procesar_mensaje(
    canal,
    metodo,
    propiedades,
    cuerpo: bytes,
    handler: Handler,
    config: ConsumerConfig,
    dormir: Callable[[float], None],
    jitter: bool = True,
) -> None:
    """Ejecuta el handler con reintentos y resuelve el mensaje: ACK, o NACK sin requeue (-> DLQ)."""
    tag = metodo.delivery_tag
    contexto = f"message_id={getattr(propiedades, 'message_id', None)} routing_key={metodo.routing_key}"

    intento = 0
    while True:
        intento += 1
        try:
            handler(cuerpo, propiedades, metodo)
        except NonRetryableError as e:
            logger.error("Mensaje irrecuperable, se envia a la DLQ sin reintentos [%s]: %s", contexto, e)
            canal.basic_nack(delivery_tag=tag, requeue=False)
            return
        except Exception as e:  # cualquier fallo del handler es potencialmente transitorio
            if intento > config.max_reintentos:
                logger.exception(
                    "Reintentos agotados tras %d intento(s), se envia a la DLQ [%s]", intento, contexto
                )
                canal.basic_nack(delivery_tag=tag, requeue=False)
                return
            espera = calcular_espera(intento, config.espera_base, config.espera_maxima, jitter)
            logger.warning(
                "Fallo procesando [%s] (intento %d de %d): %r. Reintento en %.1fs",
                contexto, intento, config.max_reintentos + 1, e, espera,
            )
            dormir(espera)
            continue

        canal.basic_ack(delivery_tag=tag)
        return


def crear_callback(handler: Handler, config: ConsumerConfig, dormir: Callable[[float], None]):
    """Devuelve el callback con la firma que exige pika: (canal, metodo, propiedades, cuerpo)."""
    def callback(canal, metodo, propiedades, cuerpo):
        procesar_mensaje(canal, metodo, propiedades, cuerpo, handler, config, dormir)
    return callback


class ConsumerWorker(threading.Thread):
    """Un hilo = una conexion + un canal + un consumidor. Se reconecta solo si el broker se cae."""

    def __init__(
        self,
        nombre: str,
        config: ConsumerConfig,
        handler: Handler,
        parametros_fn=parametros_conexion,
        topologia_fn=construir_topologia,
        fabrica_conexion=None,
    ) -> None:
        super().__init__(name=nombre, daemon=True)
        self._config = config
        self._handler = handler
        self._parametros_fn = parametros_fn
        self._topologia_fn = topologia_fn
        self._fabrica_conexion = fabrica_conexion
        self._detener = threading.Event()
        self._conexion = None
        self._canal = None
        self._llego_a_consumir = False  # True si la ultima conexion llego a quedar escuchando

    # ------------------------------------------------------------ ciclo de vida

    def run(self) -> None:
        fallos = 0
        while not self._detener.is_set():
            try:
                self._consumir()
                if not self._detener.is_set():
                    # start_consuming() volvio sin que nos pidieran parar: el broker cancelo el
                    # consumo (p. ej. borraron la cola). Se trata como desconexion y se reconecta.
                    raise ConnectionError("el broker cancelo el consumo")
                fallos = 0
            except Exception as e:
                if self._detener.is_set():
                    break
                if self._llego_a_consumir:
                    fallos = 0  # esta conexion estuvo sana: el backoff vuelve a empezar de cero
                fallos += 1
                espera = calcular_espera(fallos, 1.0, self._config.reconexion_maxima)
                logger.warning("Consumidor %s desconectado: %r. Reconectando en %.1fs", self.name, e, espera)
                self._detener.wait(espera)
        logger.info("Consumidor %s detenido", self.name)

    def _consumir(self) -> None:
        self._llego_a_consumir = False
        fabrica = self._fabrica_conexion or pika.BlockingConnection
        conexion = fabrica(self._parametros_fn())
        self._conexion = conexion
        try:
            canal = conexion.channel()
            self._canal = canal
            # Cada consumidor declara la topologia (idempotente): no depende de que otro servicio
            # haya arrancado antes ni de que alguien haya creado las colas a mano.
            declarar_topologia(canal, self._topologia_fn())
            canal.basic_qos(prefetch_count=self._config.prefetch)
            canal.basic_consume(
                queue=self._config.cola,
                on_message_callback=crear_callback(self._handler, self._config, dormir=conexion.sleep),
                auto_ack=False,  # ACK manual: solo se confirma cuando el handler termino bien
            )
            self._llego_a_consumir = True
            logger.info("Consumidor %s escuchando '%s' (prefetch=%d)", self.name, self._config.cola, self._config.prefetch)
            if not self._detener.is_set():
                canal.start_consuming()  # bloquea hasta stop_consuming() o error de conexion
        finally:
            self._canal = None
            try:
                if conexion.is_open:
                    conexion.close()
            except Exception:  # conexion medio rota: se descarta
                pass
            self._conexion = None

    def detener(self) -> None:
        """Pide parar. Es seguro llamarlo desde otro hilo (add_callback_threadsafe es el unico metodo thread-safe)."""
        self._detener.set()
        conexion = self._conexion
        try:
            if conexion is not None and conexion.is_open:
                conexion.add_callback_threadsafe(self._parar_consumo)
        except Exception:  # ya se estaba cerrando
            pass

    def _parar_consumo(self) -> None:
        # Corre DENTRO del hilo del consumidor (lo despacha pika).
        canal = self._canal
        if canal is not None and canal.is_open:
            canal.stop_consuming()


class ConsumerManager:
    """Levanta `concurrencia` workers sobre la misma cola (consumidores competidores)."""

    def __init__(self, config: ConsumerConfig, handler: Handler, **kwargs_worker) -> None:
        self._config = config
        self._handler = handler
        self._kwargs_worker = kwargs_worker
        self._workers: List[ConsumerWorker] = []

    def iniciar(self) -> None:
        for n in range(1, self._config.concurrencia + 1):
            worker = ConsumerWorker(
                f"consumer-{self._config.cola}-{n}", self._config, self._handler, **self._kwargs_worker
            )
            worker.start()
            self._workers.append(worker)

    def detener(self, timeout: float = 10.0) -> None:
        for worker in self._workers:
            worker.detener()
        limite = time.monotonic() + timeout
        for worker in self._workers:
            worker.join(max(0.1, limite - time.monotonic()))
        self._workers.clear()
