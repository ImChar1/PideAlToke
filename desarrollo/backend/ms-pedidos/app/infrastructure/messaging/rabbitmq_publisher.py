# Adaptador de salida (Outbound Adapter): publica eventos de pedido en RabbitMQ con pika.
#
# Garantias y decisiones:
#   * Publisher Confirms (`confirm_delivery`): basic_publish bloquea hasta que el broker confirma
#     (ack) que tomo el mensaje; un nack lanza NackError. Asi sabemos si el broker lo recibio.
#   * mandatory=True: si ninguna cola recibe el mensaje, el broker lo devuelve y pika lanza
#     UnroutableError (en vez de perderlo en silencio).
#   * Mensajes persistentes (delivery_mode=2) sobre un exchange durable.
#   * pika.BlockingConnection NO es thread-safe y FastAPI atiende peticiones sync en un pool de
#     hilos: toda la conexion/publicacion va bajo un Lock. Una unica conexion se reutiliza.
#   * Si la conexion esta caida (broker reiniciado, heartbeat perdido por inactividad) se
#     reconecta y se reintenta UNA vez; si falla otra vez se abre un "enfriamiento" para que las
#     peticiones siguientes no esperen el timeout completo mientras el broker sigue caido.

import logging
import threading
import time
from typing import Optional

import pika
import pika.exceptions

from app.core.config import settings
from app.domain.ports.evento_publisher_port import (
    EventoNoEnrutableError,
    NullEventPublisher,
    PedidoEventPublisherPort,
    PublicacionEventoError,
)
from app.infrastructure.messaging.rabbitmq_config import (
    DELIVERY_MODE_PERSISTENT,
    declarar_topologia,
    parametros_conexion,
    routing_key_para,
)
from app.schemas.schema_eventos import EventoPedidoSchema

logger = logging.getLogger(__name__)


class RabbitMQPedidoEventPublisher(PedidoEventPublisherPort):

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._conexion: Optional[pika.BlockingConnection] = None
        self._canal = None
        self._bloqueado_hasta = 0.0  # time.monotonic() hasta el que NO se intenta publicar

    # ------------------------------------------------------------ conexion

    def _asegurar_canal(self):
        """Devuelve un canal abierto en modo confirmacion, (re)conectando si hace falta."""
        if (
            self._conexion is None or self._conexion.is_closed
            or self._canal is None or self._canal.is_closed
        ):
            self._cerrar_silencioso()
            self._conexion = pika.BlockingConnection(parametros_conexion())
            self._canal = self._conexion.channel()
            self._canal.confirm_delivery()  # activa Publisher Confirms en este canal
            declarar_topologia(self._canal)
            logger.info("Conectado a RabbitMQ (%s:%s)", settings.RABBITMQ_HOST, settings.RABBITMQ_PORT)
        return self._canal

    def _cerrar_silencioso(self) -> None:
        try:
            if self._conexion is not None and self._conexion.is_open:
                self._conexion.close()
        except Exception:  # la conexion puede estar medio rota: da igual, se descarta
            pass
        self._conexion = None
        self._canal = None

    def cerrar(self) -> None:
        """Cierra la conexion (se llama al apagar la app)."""
        with self._lock:
            self._cerrar_silencioso()

    # ------------------------------------------------------------ publicar

    def publicar(self, evento: EventoPedidoSchema) -> None:
        routing_key = routing_key_para(evento.tipo)
        cuerpo = evento.model_dump_json().encode("utf-8")
        propiedades = pika.BasicProperties(
            content_type="application/json",
            content_encoding="utf-8",
            delivery_mode=DELIVERY_MODE_PERSISTENT,
            message_id=evento.event_id,       # idempotencia en el consumidor
            type=routing_key,
            timestamp=int(time.time()),
            app_id=settings.PROJECT_NAME,
        )

        with self._lock:
            if time.monotonic() < self._bloqueado_hasta:
                raise PublicacionEventoError("RabbitMQ no disponible (en enfriamiento tras un fallo reciente)")

            ultimo_error: Optional[Exception] = None
            for _intento in (1, 2):
                try:
                    canal = self._asegurar_canal()
                    canal.basic_publish(
                        exchange=settings.RABBITMQ_EXCHANGE_PEDIDOS,
                        routing_key=routing_key,
                        body=cuerpo,
                        properties=propiedades,
                        mandatory=True,
                    )
                    return  # el broker confirmo (ack): publicado
                except pika.exceptions.UnroutableError as e:
                    # El broker lo acepto pero ninguna cola lo recibio. No es un problema de
                    # conexion: no se reintenta ni se activa el enfriamiento.
                    raise EventoNoEnrutableError(
                        f"Sin cola destino para '{routing_key}' en '{settings.RABBITMQ_EXCHANGE_PEDIDOS}'"
                    ) from e
                except pika.exceptions.NackError as e:
                    # El broker NO confirmo el mensaje (fallo interno): reintentar no ayuda.
                    raise PublicacionEventoError(f"El broker rechazo (nack) el evento '{routing_key}'") from e
                except (pika.exceptions.AMQPError, OSError) as e:
                    # Conexion/canal caidos: se descarta y se reintenta una vez con conexion nueva.
                    ultimo_error = e
                    logger.warning("Fallo publicando '%s' en RabbitMQ: %r", routing_key, e)
                    self._cerrar_silencioso()

            self._bloqueado_hasta = time.monotonic() + settings.RABBITMQ_PUBLISH_COOLDOWN_SECONDS
            raise PublicacionEventoError(
                f"No se pudo publicar '{routing_key}' en RabbitMQ: {ultimo_error!r}"
            ) from ultimo_error


# ------------------------------------------------------------ fabrica (singleton)

_publisher: Optional[PedidoEventPublisherPort] = None
_publisher_lock = threading.Lock()


def obtener_event_publisher() -> PedidoEventPublisherPort:
    """
    Publicador unico del proceso. Con RABBITMQ_ENABLED=false devuelve uno nulo, asi el resto
    del codigo no necesita `if` ni cambia en tests / desarrollo sin broker.
    """
    global _publisher
    with _publisher_lock:
        if _publisher is None:
            _publisher = RabbitMQPedidoEventPublisher() if settings.RABBITMQ_ENABLED else NullEventPublisher()
        return _publisher


def cerrar_event_publisher() -> None:
    """Cierra la conexion del publicador (apagado de la app)."""
    global _publisher
    with _publisher_lock:
        if isinstance(_publisher, RabbitMQPedidoEventPublisher):
            _publisher.cerrar()
        _publisher = None
