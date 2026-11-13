# Interfaz abstracta (Port) para PUBLICAR los movimientos de stock hacia otros microservicios.
# El dominio depende SOLO de esta abstraccion: no sabe que detras hay Kafka ni RabbitMQ.

from abc import ABC, abstractmethod

from app.schemas.schema_eventos_movimiento import EventoMovimientoStock


class PublicacionMovimientoError(Exception):
    """No se pudo publicar el evento (broker caido, cola llena, nack...)."""


class MovimientoEventPublisherPort(ABC):

    @abstractmethod
    def publicar(self, evento: EventoMovimientoStock) -> None:
        """Publica el evento. Lanza PublicacionMovimientoError si no se pudo entregar al broker."""


class NullMovimientoPublisher(MovimientoEventPublisherPort):
    """Implementacion nula: se usa cuando Kafka y RabbitMQ estan apagados."""

    def publicar(self, evento: EventoMovimientoStock) -> None:
        return None
