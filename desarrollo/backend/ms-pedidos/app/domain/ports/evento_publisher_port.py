# Interfaz abstracta (Port) para PUBLICAR eventos de pedido hacia otros microservicios.
# El dominio depende SOLO de esta abstraccion: no sabe que detras hay RabbitMQ (ni pika).
# Eso permite testear PedidoService con un Fake y apagar la mensajeria sin tocar el dominio.

from abc import ABC, abstractmethod

from app.schemas.schema_eventos import EventoPedidoSchema


class PublicacionEventoError(Exception):
    """No se pudo publicar el evento (broker caido, nack del broker, timeout...)."""


class EventoNoEnrutableError(PublicacionEventoError):
    """El broker acepto el mensaje pero ninguna cola lo recibio (no hay bindings para esa routing key)."""


class PedidoEventPublisherPort(ABC):

    @abstractmethod
    def publicar(self, evento: EventoPedidoSchema) -> None:
        """Publica el evento. Lanza PublicacionEventoError si no se pudo entregar al broker."""
        pass


class NullEventPublisher(PedidoEventPublisherPort):
    """Implementacion nula: se usa cuando RabbitMQ esta apagado (RABBITMQ_ENABLED=false)."""

    def publicar(self, evento: EventoPedidoSchema) -> None:
        return None
