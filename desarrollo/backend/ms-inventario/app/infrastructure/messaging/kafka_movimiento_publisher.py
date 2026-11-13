# Adaptador de salida: publica los movimientos de stock en Kafka (topico `inventario.movimientos`).
#
#   * KEY = sku: Kafka garantiza orden por particion y la key decide la particion, asi todos los
#     movimientos de un mismo producto (reservado -> confirmado -> stock_bajo...) llegan en orden,
#     y productos distintos se reparten entre las 3 particiones.
#   * acks=all + idempotencia: confirmacion con todas las replicas en sincronia, sin duplicados.
#   * produce() es asincrono (confirmacion por callback); un hilo daemon hace poll() para que los
#     callbacks corran sin esperar al siguiente evento. Publicar es "mejor esfuerzo".

import logging
import threading
from typing import Callable, Optional

from confluent_kafka import KafkaException, Producer

from app.core.config import settings
from app.domain.ports.movimiento_publisher_port import (
    MovimientoEventPublisherPort,
    PublicacionMovimientoError,
)
from app.schemas.schema_eventos_movimiento import EventoMovimientoStock

logger = logging.getLogger(__name__)


def configuracion_productor(cfg=settings) -> dict:
    return {
        "bootstrap.servers": cfg.KAFKA_BOOTSTRAP_SERVERS,
        "client.id": cfg.KAFKA_CLIENT_ID,
        "acks": cfg.KAFKA_ACKS,
        "enable.idempotence": cfg.KAFKA_ENABLE_IDEMPOTENCE,
        "compression.type": cfg.KAFKA_COMPRESSION,
        "linger.ms": cfg.KAFKA_LINGER_MS,
        "delivery.timeout.ms": cfg.KAFKA_DELIVERY_TIMEOUT_MS,
    }


def serializar_evento(evento: EventoMovimientoStock) -> tuple[bytes, bytes, list[tuple[str, bytes]]]:
    """(key, value, headers). Funcion pura: facil de probar."""
    return (
        evento.sku.encode("utf-8"),
        evento.model_dump_json().encode("utf-8"),
        [
            ("event_id", evento.event_id.encode("utf-8")),
            ("tipo", evento.tipo.encode("utf-8")),
            ("content-type", b"application/json"),
        ],
    )


class KafkaMovimientoPublisher(MovimientoEventPublisherPort):

    def __init__(self, productor=None, fabrica_productor: Optional[Callable[[dict], object]] = None, cfg=settings) -> None:
        self._cfg = cfg
        self._productor = productor or (fabrica_productor or Producer)(configuracion_productor(cfg))
        self._detener = threading.Event()
        self._hilo = threading.Thread(target=self._atender_callbacks, name="kafka-poll-movimientos", daemon=True)
        self._hilo.start()

    def _atender_callbacks(self) -> None:
        while not self._detener.is_set():
            self._productor.poll(0.5)

    @staticmethod
    def _al_entregar(error, mensaje) -> None:
        if error is not None:
            logger.error("Kafka no confirmo el movimiento (topico=%s key=%s): %s", mensaje.topic(), mensaje.key(), error)

    def publicar(self, evento: EventoMovimientoStock) -> None:
        key, value, headers = serializar_evento(evento)
        for intento in (1, 2):
            try:
                self._productor.produce(
                    self._cfg.KAFKA_TOPIC_MOVIMIENTOS, key=key, value=value, headers=headers, on_delivery=self._al_entregar
                )
                return
            except BufferError:
                if intento == 2:
                    raise PublicacionMovimientoError("Cola local de Kafka llena: no se pudo encolar el movimiento")
                self._productor.poll(1.0)
            except KafkaException as e:
                raise PublicacionMovimientoError(f"Kafka rechazo el movimiento '{evento.tipo}': {e}") from e

    def cerrar(self) -> None:
        self._detener.set()
        pendientes = self._productor.flush(self._cfg.KAFKA_FLUSH_TIMEOUT_SECONDS)
        if pendientes:
            logger.warning("Kafka: %d mensaje(s) sin confirmar al cerrar el productor", pendientes)
