# Fabrica del publicador de movimientos de stock: decide a QUE brokers se publica segun la configuracion.
#
#   KAFKA_ENABLED   RABBITMQ_ENABLED   resultado
#   false           false              NullMovimientoPublisher
#   true            false              solo Kafka (todos los movimientos)
#   false           true               solo RabbitMQ (solo `stock_bajo`)
#   true            true               ambos: Kafka = historial completo, RabbitMQ = alerta accionable
#
# Si uno falla, el otro igual recibe el evento.

import logging
import threading
from typing import List, Optional

from app.core.config import settings
from app.domain.ports.movimiento_publisher_port import (
    MovimientoEventPublisherPort,
    NullMovimientoPublisher,
    PublicacionMovimientoError,
)
from app.schemas.schema_eventos_movimiento import EventoMovimientoStock

logger = logging.getLogger(__name__)


class CompositeMovimientoPublisher(MovimientoEventPublisherPort):

    def __init__(self, publicadores: List[MovimientoEventPublisherPort]) -> None:
        self._publicadores = publicadores

    def publicar(self, evento: EventoMovimientoStock) -> None:
        errores: List[Exception] = []
        for publicador in self._publicadores:
            try:
                publicador.publicar(evento)
            except Exception as e:
                errores.append(e)
                logger.warning("Fallo %s publicando '%s': %r", type(publicador).__name__, evento.tipo, e)
        if len(errores) == 1:
            raise errores[0]
        if errores:
            raise PublicacionMovimientoError(f"Fallaron {len(errores)} destinos: {errores!r}")

    def cerrar(self) -> None:
        for publicador in self._publicadores:
            cerrar = getattr(publicador, "cerrar", None)
            if cerrar:
                try:
                    cerrar()
                except Exception:
                    logger.exception("Error cerrando %s", type(publicador).__name__)


def construir_publicador(cfg=settings) -> MovimientoEventPublisherPort:
    # Imports aqui dentro: un entorno sin broker no carga pika ni confluent-kafka para nada.
    publicadores: List[MovimientoEventPublisherPort] = []
    if cfg.KAFKA_ENABLED:
        from app.infrastructure.messaging.kafka_movimiento_publisher import KafkaMovimientoPublisher
        publicadores.append(KafkaMovimientoPublisher())
    if cfg.RABBITMQ_ENABLED:
        from app.infrastructure.messaging.rabbitmq_alertas_publisher import RabbitMQAlertaStockPublisher
        publicadores.append(RabbitMQAlertaStockPublisher())
    if not publicadores:
        return NullMovimientoPublisher()
    return publicadores[0] if len(publicadores) == 1 else CompositeMovimientoPublisher(publicadores)


_publisher: Optional[MovimientoEventPublisherPort] = None
_lock = threading.Lock()


def obtener_movimiento_publisher() -> MovimientoEventPublisherPort:
    """Publicador unico del proceso (las conexiones a los brokers se reutilizan)."""
    global _publisher
    with _lock:
        if _publisher is None:
            _publisher = construir_publicador()
        return _publisher


def cerrar_movimiento_publisher() -> None:
    global _publisher
    with _lock:
        cerrar = getattr(_publisher, "cerrar", None)
        if cerrar:
            cerrar()
        _publisher = None
