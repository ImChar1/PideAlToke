# Logica de administracion de RabbitMQ, encapsulada fuera del controlador.
#
# Nota de arquitectura: en este microservicio el "dominio" ES la administracion del broker, asi que
# el servicio usa pika directamente (las demas capas de otros servicios abstraen BD / HTTP con Ports).
# La conexion se inyecta (`abrir_canal`) para poder testear con un canal falso, sin broker.
#
# El servicio recibe los DTOs ya validados por Pydantic y devuelve diccionarios; traduce los errores
# de AMQP a excepciones de dominio que el router convierte en codigos HTTP:
#   404 NOT_FOUND -> RecursoNoEncontradoError          (cola / exchange inexistente)
#   405 / 406     -> ConflictoRabbitError              (recurso bloqueado, argumentos distintos, if_unused/if_empty)
#   403 u otros   -> OperacionRechazadaError           (permisos del usuario del broker, nombre reservado...)
#   sin conexion  -> RabbitNoDisponibleError           (broker caido / credenciales incorrectas)

import logging
from typing import Any, Callable, Dict

import pika.exceptions

from app.infrastructure.messaging.rabbitmq_config import abrir_canal

logger = logging.getLogger(__name__)


class RabbitNoDisponibleError(Exception):
    pass


class RecursoNoEncontradoError(Exception):
    pass


class ConflictoRabbitError(Exception):
    pass


class OperacionRechazadaError(Exception):
    pass


class RabbitAdminService:

    def __init__(self, abrir_canal_fn=abrir_canal):
        self._abrir_canal = abrir_canal_fn

    # ------------------------------------------------------------------ colas

    def crear_cola(self, datos) -> Dict[str, Any]:
        """Declara una cola (idempotente si ya existe con los MISMOS argumentos)."""
        argumentos = self._argumentos_cola(datos)

        def operacion(canal):
            r = canal.queue_declare(
                queue=datos.name,
                durable=datos.durable,
                exclusive=False,  # una cola exclusiva muere al cerrar la conexion: aqui no tendria sentido
                auto_delete=datos.auto_delete,
                arguments=argumentos or None,
            )
            return self._info_cola(r)

        return self._ejecutar(operacion)

    def obtener_cola(self, nombre: str) -> Dict[str, Any]:
        """Estado de una cola (mensajes listos y consumidores). declare passive=True no la crea."""
        def operacion(canal):
            return self._info_cola(canal.queue_declare(queue=nombre, passive=True))

        return self._ejecutar(operacion)

    def eliminar_cola(self, nombre: str, if_unused: bool = False, if_empty: bool = False) -> Dict[str, Any]:
        """
        Elimina una cola. `if_unused` / `if_empty` evitan borrarla si tiene consumidores / mensajes
        (el broker responde 406 y se informa como 409).
        """
        def operacion(canal):
            # queue_delete es idempotente en RabbitMQ (no falla si no existe); el chequeo pasivo
            # previo permite responder 404 en vez de un "ok" engañoso.
            canal.queue_declare(queue=nombre, passive=True)
            r = canal.queue_delete(queue=nombre, if_unused=if_unused, if_empty=if_empty)
            return {"name": nombre, "deleted": True, "messages_discarded": r.method.message_count}

        return self._ejecutar(operacion)

    def purgar_cola(self, nombre: str) -> Dict[str, Any]:
        """Descarta todos los mensajes LISTOS de la cola (los pendientes de ACK no se purgan)."""
        def operacion(canal):
            r = canal.queue_purge(queue=nombre)
            return {"name": nombre, "purged_messages": r.method.message_count}

        return self._ejecutar(operacion)

    # ------------------------------------------------------------------ exchanges y bindings

    def crear_exchange(self, datos) -> Dict[str, Any]:
        def operacion(canal):
            canal.exchange_declare(
                exchange=datos.name,
                exchange_type=datos.type,
                durable=datos.durable,
                auto_delete=datos.auto_delete,
                internal=datos.internal,
            )
            return {
                "name": datos.name, "type": datos.type, "durable": datos.durable,
                "auto_delete": datos.auto_delete, "internal": datos.internal,
            }

        return self._ejecutar(operacion)

    def crear_binding(self, datos) -> Dict[str, Any]:
        """Enlaza una cola a un exchange. Ambos deben existir (si no: 404)."""
        def operacion(canal):
            canal.queue_bind(queue=datos.queue, exchange=datos.exchange, routing_key=datos.routing_key)
            return {"queue": datos.queue, "exchange": datos.exchange, "routing_key": datos.routing_key}

        return self._ejecutar(operacion)

    # ------------------------------------------------------------------ internos

    @staticmethod
    def _argumentos_cola(datos) -> Dict[str, Any]:
        """Mapea los campos del DTO a los argumentos x-* de RabbitMQ (solo los informados)."""
        argumentos: Dict[str, Any] = {}
        if datos.queue_type != "classic":
            argumentos["x-queue-type"] = datos.queue_type
        if datos.message_ttl_ms is not None:
            argumentos["x-message-ttl"] = datos.message_ttl_ms
        if datos.max_length is not None:
            argumentos["x-max-length"] = datos.max_length
        if datos.dead_letter_exchange:
            argumentos["x-dead-letter-exchange"] = datos.dead_letter_exchange
        if datos.dead_letter_routing_key:
            argumentos["x-dead-letter-routing-key"] = datos.dead_letter_routing_key
        return argumentos

    @staticmethod
    def _info_cola(frame) -> Dict[str, Any]:
        m = frame.method
        return {"name": m.queue, "messages": m.message_count, "consumers": m.consumer_count}

    def _ejecutar(self, operacion: Callable[[Any], Any]) -> Any:
        """Abre canal, ejecuta la operacion y traduce los errores de pika a excepciones de dominio."""
        try:
            with self._abrir_canal() as canal:
                return operacion(canal)
        except pika.exceptions.ChannelClosed as e:
            raise self._traducir_canal_cerrado(e) from e
        except (pika.exceptions.AMQPError, OSError) as e:
            # Conexion rechazada, credenciales invalidas, timeout, conexion perdida a mitad de operacion...
            logger.error("No se pudo operar contra RabbitMQ: %r", e)
            raise RabbitNoDisponibleError("No se pudo comunicar con RabbitMQ") from e

    @staticmethod
    def _traducir_canal_cerrado(e: "pika.exceptions.ChannelClosed") -> Exception:
        # El broker cierra el canal con un codigo AMQP cuando rechaza la operacion.
        codigo = getattr(e, "reply_code", None)
        texto = getattr(e, "reply_text", str(e))
        if codigo == 404:
            return RecursoNoEncontradoError(texto)
        if codigo in (405, 406):
            return ConflictoRabbitError(texto)
        return OperacionRechazadaError(texto)
