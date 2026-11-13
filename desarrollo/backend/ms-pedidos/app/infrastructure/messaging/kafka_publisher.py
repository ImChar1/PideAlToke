# Adaptador de salida (Outbound Adapter): publica los eventos de pedido en Kafka (confluent-kafka).
#
# Decisiones:
#   * Topico `pedidos.eventos`, KEY = pedido_id: Kafka garantiza orden SOLO dentro de una particion y
#     la key decide la particion (hash). Asi creado -> confirmado -> cancelado de un mismo pedido
#     llegan en orden a los consumidores, y pedidos distintos se reparten entre las 3 particiones.
#   * VALUE = el mismo DTO JSON que viaja por RabbitMQ (EventoPedidoSchema): un solo contrato.
#   * acks=all + enable.idempotence: el broker confirma cuando TODAS las replicas en sincronia lo
#     tienen y los reintentos internos del productor no generan duplicados.
#   * produce() es asincrono: la confirmacion llega por el callback `on_delivery`. Un hilo daemon
#     llama a poll() para que los callbacks (y los logs de fallo) se ejecuten sin esperar al
#     siguiente evento. Publicar es "mejor esfuerzo" igual que con RabbitMQ: nunca rompe el pedido.
#   * Headers (event_id, tipo): permiten filtrar/deduplicar sin deserializar el JSON.

import logging
import threading
from typing import Callable, Optional

from confluent_kafka import KafkaException, Producer

from app.core.config import settings
from app.domain.ports.evento_publisher_port import PedidoEventPublisherPort, PublicacionEventoError
from app.schemas.schema_eventos import EventoPedidoSchema

logger = logging.getLogger(__name__)


def configuracion_productor(cfg=settings) -> dict:
    """Propiedades del productor, construidas desde settings (inyectable en tests)."""
    return {
        "bootstrap.servers": cfg.KAFKA_BOOTSTRAP_SERVERS,
        "client.id": cfg.KAFKA_CLIENT_ID,
        "acks": cfg.KAFKA_ACKS,
        "enable.idempotence": cfg.KAFKA_ENABLE_IDEMPOTENCE,
        "compression.type": cfg.KAFKA_COMPRESSION,
        "linger.ms": cfg.KAFKA_LINGER_MS,
        "delivery.timeout.ms": cfg.KAFKA_DELIVERY_TIMEOUT_MS,
    }


def serializar_evento(evento: EventoPedidoSchema) -> tuple[bytes, bytes, list[tuple[str, bytes]]]:
    """(key, value, headers) de un evento. Funcion pura: facil de probar."""
    key = str(evento.pedido_id).encode("utf-8")
    value = evento.model_dump_json().encode("utf-8")
    headers = [
        ("event_id", evento.event_id.encode("utf-8")),
        ("tipo", evento.tipo.encode("utf-8")),
        ("content-type", b"application/json"),
    ]
    return key, value, headers


class KafkaPedidoEventPublisher(PedidoEventPublisherPort):

    def __init__(self, productor=None, fabrica_productor: Optional[Callable[[dict], object]] = None, cfg=settings) -> None:
        self._cfg = cfg
        # `Producer` se resuelve al construir (no como valor por defecto) para poder sustituirlo en tests.
        self._productor = productor or (fabrica_productor or Producer)(configuracion_productor(cfg))
        self._detener = threading.Event()
        self._hilo = threading.Thread(target=self._atender_callbacks, name="kafka-poll-pedidos", daemon=True)
        self._hilo.start()

    def _atender_callbacks(self) -> None:
        while not self._detener.is_set():
            self._productor.poll(0.5)

    @staticmethod
    def _al_entregar(error, mensaje) -> None:
        """Callback de confirmacion del broker (corre dentro de poll())."""
        if error is not None:
            logger.error(
                "Kafka no confirmo el evento (topico=%s key=%s): %s",
                mensaje.topic(), mensaje.key(), error,
            )
        else:
            logger.debug(
                "Evento confirmado por Kafka: %s[%d]@%d", mensaje.topic(), mensaje.partition(), mensaje.offset()
            )

    def publicar(self, evento: EventoPedidoSchema) -> None:
        key, value, headers = serializar_evento(evento)
        for intento in (1, 2):
            try:
                self._productor.produce(
                    self._cfg.KAFKA_TOPIC_PEDIDOS, key=key, value=value, headers=headers, on_delivery=self._al_entregar
                )
                return
            except BufferError:
                # Cola local llena (el broker no da abasto o esta caido): se le da un respiro y se
                # reintenta UNA vez; si sigue llena, se informa para que quede en el log.
                if intento == 2:
                    raise PublicacionEventoError("Cola local de Kafka llena: no se pudo encolar el evento")
                self._productor.poll(1.0)
            except KafkaException as e:
                raise PublicacionEventoError(f"Kafka rechazo el evento '{evento.tipo}': {e}") from e

    def cerrar(self) -> None:
        """Apagado limpio: espera (con tope) a que los mensajes pendientes lleguen al broker."""
        self._detener.set()
        pendientes = self._productor.flush(self._cfg.KAFKA_FLUSH_TIMEOUT_SECONDS)
        if pendientes:
            logger.warning("Kafka: %d mensaje(s) sin confirmar al cerrar el productor", pendientes)
