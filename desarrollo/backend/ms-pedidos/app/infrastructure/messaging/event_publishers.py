# Fabrica del publicador de eventos de pedido: decide a QUE brokers se publica segun la configuracion.
#
#   RABBITMQ_ENABLED  KAFKA_ENABLED   resultado
#   false             false           NullEventPublisher (no se publica en ninguno)
#   true              false           solo RabbitMQ (comportamiento de la evaluacion 2)
#   false             true            solo Kafka
#   true              true            RabbitMQ + Kafka (cada broker cumple su rol, ver README)
#
# El dominio (PedidoService) no cambia: sigue dependiendo del Port. Que Kafka se sume a RabbitMQ
# NO altera las integraciones previas: si Kafka falla, RabbitMQ igual recibe el evento, y viceversa.

import logging
import threading
from typing import List, Optional

from app.core.config import settings
from app.domain.ports.evento_publisher_port import (
    NullEventPublisher,
    PedidoEventPublisherPort,
    PublicacionEventoError,
)
from app.schemas.schema_eventos import EventoPedidoSchema

logger = logging.getLogger(__name__)


class CompositeEventPublisher(PedidoEventPublisherPort):
    """Publica el mismo evento en varios destinos; el fallo de uno NO impide los demas."""

    def __init__(self, publicadores: List[PedidoEventPublisherPort]) -> None:
        self._publicadores = publicadores

    def publicar(self, evento: EventoPedidoSchema) -> None:
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
            raise PublicacionEventoError(f"Fallaron {len(errores)} destinos: {errores!r}")

    def cerrar(self) -> None:
        for publicador in self._publicadores:
            cerrar = getattr(publicador, "cerrar", None)
            if cerrar:
                try:
                    cerrar()
                except Exception:
                    logger.exception("Error cerrando %s", type(publicador).__name__)


def construir_publicador(cfg=settings) -> PedidoEventPublisherPort:
    # Imports aqui dentro: asi un entorno sin broker no carga pika ni confluent-kafka para nada.
    publicadores: List[PedidoEventPublisherPort] = []
    if cfg.RABBITMQ_ENABLED:
        from app.infrastructure.messaging.rabbitmq_publisher import RabbitMQPedidoEventPublisher
        publicadores.append(RabbitMQPedidoEventPublisher())
    if cfg.KAFKA_ENABLED:
        from app.infrastructure.messaging.kafka_publisher import KafkaPedidoEventPublisher
        publicadores.append(KafkaPedidoEventPublisher())
    if not publicadores:
        return NullEventPublisher()
    if len(publicadores) == 1:
        return publicadores[0]
    return CompositeEventPublisher(publicadores)


_publisher: Optional[PedidoEventPublisherPort] = None
_lock = threading.Lock()


def obtener_event_publisher() -> PedidoEventPublisherPort:
    """Publicador unico del proceso (las conexiones a los brokers se reutilizan)."""
    global _publisher
    with _lock:
        if _publisher is None:
            _publisher = construir_publicador()
        return _publisher


def cerrar_event_publisher() -> None:
    """Cierra las conexiones (apagado de la app)."""
    global _publisher
    with _lock:
        cerrar = getattr(_publisher, "cerrar", None)
        if cerrar:
            cerrar()
        _publisher = None
