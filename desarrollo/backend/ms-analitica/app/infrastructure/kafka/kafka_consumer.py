# Consumidor Kafka (confluent-kafka): COMMIT MANUAL, reintentos con backoff y descarte con log.
#
# Flujo por mensaje (ver `procesar_mensaje`):
#   handler OK                         -> commit del offset
#   handler lanza NonRetryableError    -> se registra, se cuenta como invalido y se hace commit
#                                         (reintentar un JSON roto no lo arregla: se salta)
#   handler lanza otra excepcion       -> reintenta hasta KAFKA_MAX_RETRIES veces con espera
#                                         base * 2^(intento-1) (tope y jitter); si se agotan se
#                                         registra, se cuenta como fallido y se hace commit
# En TODOS los casos el consumo continua: un mensaje defectuoso nunca detiene el sistema.
#
# Semantica "al menos una vez": el commit va DESPUES de procesar. Si el proceso cae entre ambos, el
# mensaje se vuelve a entregar; por eso el estado es idempotente (offsets ya aplicados se ignoran).
#
# Consumer group: cada hilo (ConsumerWorker) es UN miembro del grupo con su propio Consumer. Kafka
# reparte las particiones entre los miembros: con 3 particiones y 3 hilos, una particion por hilo.
# Si un hilo cae, sus particiones pasan a los demas (rebalanceo) y el consumo sigue.
#
# Reconstruccion al arrancar (KAFKA_REBUILD_ON_START): la PRIMERA vez que un hilo recibe una
# particion la lee desde el principio del log, para reconstruir el estado en memoria.

import logging
import random
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from confluent_kafka import OFFSET_BEGINNING, Consumer, KafkaError, KafkaException

logger = logging.getLogger(__name__)

# Fallos de commit que ocurren durante un rebalanceo: el offset no se confirma y el mensaje se vuelve a
# entregar (al menos una vez); el estado es idempotente, asi que basta con seguir. No justifican recrear
# el Consumer.
_COMMIT_RECUPERABLE = {
    KafkaError.REBALANCE_IN_PROGRESS,
    KafkaError.ILLEGAL_GENERATION,
    KafkaError.UNKNOWN_MEMBER_ID,
    KafkaError._NO_OFFSET,
    KafkaError._ASSIGNMENT_LOST,
}


class NonRetryableError(Exception):
    """Mensaje irrecuperable (JSON invalido, contrato roto...): se descarta sin reintentos."""


@dataclass(frozen=True)
class MensajeKafka:
    """Lo que el handler necesita saber del mensaje, sin exponer tipos de confluent-kafka."""
    topico: str
    particion: int
    offset: int
    key: Optional[bytes]
    value: bytes


# handler(mensaje) -> None. Debe lanzar excepcion si NO pudo procesar el mensaje.
Handler = Callable[[MensajeKafka], None]


@dataclass(frozen=True)
class ConsumerConfig:
    topico: str
    grupo: str
    bootstrap_servers: str
    client_id: str
    concurrencia: int
    max_reintentos: int
    espera_base: float
    espera_maxima: float
    reconexion_maxima: float
    reconstruir_al_iniciar: bool
    session_timeout_ms: int
    max_poll_interval_ms: int

    def propiedades(self, miembro: int) -> dict:
        """Propiedades de librdkafka para UN miembro del grupo."""
        return {
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": self.grupo,
            "client.id": f"{self.client_id}-{self.grupo}-{miembro}",
            "enable.auto.commit": False,                # commit manual, solo tras procesar
            "auto.offset.reset": "earliest",            # grupo nuevo: desde el principio, sin perder nada
            "session.timeout.ms": self.session_timeout_ms,
            "max.poll.interval.ms": self.max_poll_interval_ms,
            "partition.assignment.strategy": "cooperative-sticky",  # rebalanceo sin parar todo el grupo
        }


def calcular_espera(intento: int, base: float, maximo: float, jitter: bool = True) -> float:
    """Backoff exponencial: base * 2^(intento-1) con tope; con jitter evita reintentos sincronizados."""
    espera = min(maximo, base * (2 ** (intento - 1)))
    if jitter:
        espera = espera / 2 + random.uniform(0, espera / 2)
    return espera


def procesar_mensaje(
    mensaje: MensajeKafka,
    handler: Handler,
    config: ConsumerConfig,
    dormir: Callable[[float], None],
    al_invalido: Callable[[str], None] = lambda t: None,
    al_fallido: Callable[[str], None] = lambda t: None,
    jitter: bool = True,
) -> str:
    """
    Ejecuta el handler con reintentos. Devuelve el resultado: "ok", "invalido" o "fallido".
    El llamador hace commit en los tres casos (el consumo nunca se detiene).
    """
    contexto = f"topico={mensaje.topico} particion={mensaje.particion} offset={mensaje.offset} key={mensaje.key!r}"
    intento = 0
    while True:
        intento += 1
        try:
            handler(mensaje)
            return "ok"
        except NonRetryableError as e:
            logger.error("Mensaje invalido, se descarta sin reintentos [%s]: %s", contexto, e)
            al_invalido(mensaje.topico)
            return "invalido"
        except Exception as e:  # cualquier fallo del handler es potencialmente transitorio
            if intento > config.max_reintentos:
                logger.exception("Reintentos agotados tras %d intento(s), se descarta el mensaje [%s]", intento, contexto)
                al_fallido(mensaje.topico)
                return "fallido"
            espera = calcular_espera(intento, config.espera_base, config.espera_maxima, jitter)
            logger.warning(
                "Fallo procesando [%s] (intento %d de %d): %r. Reintento en %.1fs",
                contexto, intento, config.max_reintentos + 1, e, espera,
            )
            dormir(espera)


class ConsumerWorker(threading.Thread):
    """Un hilo = un miembro del consumer group. Si el Consumer falla de forma fatal, lo recrea."""

    def __init__(
        self,
        nombre: str,
        miembro: int,
        config: ConsumerConfig,
        handler: Handler,
        al_invalido: Callable[[str], None] = lambda t: None,
        al_fallido: Callable[[str], None] = lambda t: None,
        fabrica_consumer: Callable[[dict], object] = None,
    ) -> None:
        super().__init__(name=nombre, daemon=True)
        self._miembro = miembro
        self._config = config
        self._handler = handler
        self._al_invalido = al_invalido
        self._al_fallido = al_fallido
        self._fabrica = fabrica_consumer
        self._detener = threading.Event()
        self._ya_asignadas: set = set()       # (topico, particion) que este hilo ya leyo alguna vez
        self.llego_a_consumir = False

    # ------------------------------------------------------------ rebalanceo

    def _al_asignar(self, consumer, particiones: List) -> None:
        """Se invoca cuando el grupo le asigna particiones a este miembro."""
        if self._config.reconstruir_al_iniciar:
            for tp in particiones:
                clave = (tp.topic, tp.partition)
                if clave not in self._ya_asignadas:
                    tp.offset = OFFSET_BEGINNING   # primera vez: reconstruir el estado desde el log
                self._ya_asignadas.add(clave)
        # Con el assignor cooperativo se usa incremental_assign (suma, no reemplaza lo que ya tenia).
        consumer.incremental_assign(particiones)
        logger.info(
            "Consumidor %s: particiones asignadas %s",
            self.name, [f"{tp.topic}-{tp.partition}" for tp in particiones],
        )

    def _al_revocar(self, consumer, particiones: List) -> None:
        logger.info("Consumidor %s: particiones revocadas %s", self.name, [f"{tp.topic}-{tp.partition}" for tp in particiones])
        consumer.incremental_unassign(particiones)

    def _al_perder(self, consumer, particiones: List) -> None:
        logger.warning("Consumidor %s: particiones PERDIDAS (sin commit) %s", self.name, [f"{tp.topic}-{tp.partition}" for tp in particiones])
        consumer.incremental_unassign(particiones)

    # ------------------------------------------------------------ ciclo de vida

    def run(self) -> None:
        fallos = 0
        while not self._detener.is_set():
            try:
                self._consumir()
                fallos = 0
            except Exception as e:
                if self._detener.is_set():
                    break
                if self.llego_a_consumir:
                    fallos = 0   # esta sesion estuvo sana: el backoff vuelve a empezar de cero
                fallos += 1
                espera = calcular_espera(fallos, 1.0, self._config.reconexion_maxima)
                logger.warning("Consumidor %s fallo: %r. Se recrea en %.1fs", self.name, e, espera)
                self._detener.wait(espera)
        logger.info("Consumidor %s detenido", self.name)

    def _consumir(self) -> None:
        self.llego_a_consumir = False
        fabrica = self._fabrica or Consumer
        consumer = fabrica(self._config.propiedades(self._miembro))
        try:
            consumer.subscribe(
                [self._config.topico],
                on_assign=self._al_asignar, on_revoke=self._al_revocar, on_lost=self._al_perder,
            )
            logger.info("Consumidor %s suscrito a '%s' (grupo '%s')", self.name, self._config.topico, self._config.grupo)
            while not self._detener.is_set():
                msg = consumer.poll(1.0)
                if msg is None:
                    continue
                self.llego_a_consumir = True
                error = msg.error()
                if error is not None:
                    if error.fatal():
                        raise RuntimeError(f"error fatal de Kafka: {error}")
                    # Errores de red / de metadata: librdkafka se recupera solo, solo se deja rastro.
                    logger.warning("Consumidor %s: error no fatal de Kafka: %s", self.name, error)
                    continue
                mensaje = MensajeKafka(msg.topic(), msg.partition(), msg.offset(), msg.key(), msg.value() or b"")
                procesar_mensaje(
                    mensaje, self._handler, self._config, dormir=self._detener.wait,
                    al_invalido=self._al_invalido, al_fallido=self._al_fallido,
                )
                # Commit SIEMPRE despues de resolver el mensaje (ok / invalido / fallido): no se reentrega.
                self._confirmar(consumer, msg)
        finally:
            try:
                consumer.close()   # sale del grupo limpiamente: el rebalanceo es inmediato
            except Exception:
                pass

    def _confirmar(self, consumer, msg) -> None:
        try:
            consumer.commit(message=msg, asynchronous=False)
        except KafkaException as e:
            error = e.args[0] if e.args and isinstance(e.args[0], KafkaError) else None
            if error is not None and error.code() in _COMMIT_RECUPERABLE:
                logger.warning(
                    "Consumidor %s: commit omitido durante un rebalanceo (%s) [%s-%d@%d]; el mensaje se reentregara",
                    self.name, error.name(), msg.topic(), msg.partition(), msg.offset(),
                )
                return
            raise

    def detener(self) -> None:
        self._detener.set()


class ConsumerManager:
    """Levanta `concurrencia` miembros del mismo consumer group sobre un topico."""

    def __init__(self, config: ConsumerConfig, handler: Handler, **kwargs_worker) -> None:
        self._config = config
        self._handler = handler
        self._kwargs_worker = kwargs_worker
        self._workers: List[ConsumerWorker] = []

    def iniciar(self) -> None:
        for n in range(1, self._config.concurrencia + 1):
            worker = ConsumerWorker(
                f"kafka-{self._config.grupo}-{n}", n, self._config, self._handler, **self._kwargs_worker
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
