# Adaptador de salida: publica las ALERTAS DE STOCK BAJO en RabbitMQ.
#
#   ms-inventario --(rk "stock.bajo")--> pidealtoke.alertas (DIRECT) --> alertas.stock --> ms-notificaciones
#
# Por que DIRECT: la alerta tiene un unico destino por clave exacta; no hay patrones como en los
# eventos de pedido (topic). Este servicio solo declara el exchange; la cola, su DLQ y el binding
# son del consumidor (ms-notificaciones).
#
# Mismas garantias que el publicador de pedidos: Publisher Confirms, mandatory=True (si ninguna cola
# recibe el mensaje, el broker lo devuelve), mensajes persistentes, un reintento al reconectar y
# "enfriamiento" para no esperar el timeout en cada peticion mientras el broker esta caido.
# Solo reacciona a `stock_bajo`: los demas movimientos van unicamente a Kafka.

import logging
import threading
import time
from typing import Optional

import pika
import pika.exceptions

from app.core.config import settings
from app.domain.ports.movimiento_publisher_port import (
    MovimientoEventPublisherPort,
    PublicacionMovimientoError,
)
from app.infrastructure.messaging.rabbitmq_config import parametros_conexion
from app.schemas.schema_eventos_movimiento import EventoMovimientoStock

logger = logging.getLogger(__name__)

DELIVERY_MODE_PERSISTENT = 2


class RabbitMQAlertaStockPublisher(MovimientoEventPublisherPort):

    def __init__(self, parametros_fn=parametros_conexion, fabrica_conexion=None, cfg=settings) -> None:
        self._cfg = cfg
        self._parametros_fn = parametros_fn
        self._fabrica_conexion = fabrica_conexion or pika.BlockingConnection
        self._lock = threading.Lock()
        self._conexion = None
        self._canal = None
        self._bloqueado_hasta = 0.0

    def _asegurar_canal(self):
        if self._conexion is None or self._conexion.is_closed or self._canal is None or self._canal.is_closed:
            self._cerrar_silencioso()
            self._conexion = self._fabrica_conexion(self._parametros_fn())
            self._canal = self._conexion.channel()
            self._canal.confirm_delivery()
            self._canal.exchange_declare(
                exchange=self._cfg.RABBITMQ_EXCHANGE_ALERTAS, exchange_type="direct", durable=True, auto_delete=False
            )
        return self._canal

    def _cerrar_silencioso(self) -> None:
        try:
            if self._conexion is not None and self._conexion.is_open:
                self._conexion.close()
        except Exception:
            pass
        self._conexion = None
        self._canal = None

    def cerrar(self) -> None:
        with self._lock:
            self._cerrar_silencioso()

    def publicar(self, evento: EventoMovimientoStock) -> None:
        if evento.tipo != "stock_bajo":
            return  # solo las alertas viajan por RabbitMQ
        rk = self._cfg.RABBITMQ_RK_STOCK_BAJO
        propiedades = pika.BasicProperties(
            content_type="application/json",
            content_encoding="utf-8",
            delivery_mode=DELIVERY_MODE_PERSISTENT,
            message_id=evento.event_id,
            type=rk,
            timestamp=int(time.time()),
            app_id=self._cfg.PROJECT_NAME,
        )
        cuerpo = evento.model_dump_json().encode("utf-8")

        with self._lock:
            if time.monotonic() < self._bloqueado_hasta:
                raise PublicacionMovimientoError("RabbitMQ no disponible (en enfriamiento tras un fallo reciente)")
            ultimo_error: Optional[Exception] = None
            for _ in (1, 2):
                try:
                    self._asegurar_canal().basic_publish(
                        exchange=self._cfg.RABBITMQ_EXCHANGE_ALERTAS,
                        routing_key=rk,
                        body=cuerpo,
                        properties=propiedades,
                        mandatory=True,
                    )
                    return
                except pika.exceptions.UnroutableError as e:
                    raise PublicacionMovimientoError(
                        f"Sin cola destino para '{rk}' en '{self._cfg.RABBITMQ_EXCHANGE_ALERTAS}' "
                        "(¿esta levantado ms-notificaciones?)"
                    ) from e
                except pika.exceptions.NackError as e:
                    raise PublicacionMovimientoError(f"El broker rechazo (nack) la alerta '{rk}'") from e
                except (pika.exceptions.AMQPError, OSError) as e:
                    ultimo_error = e
                    logger.warning("Fallo publicando la alerta '%s' en RabbitMQ: %r", rk, e)
                    self._cerrar_silencioso()
            self._bloqueado_hasta = time.monotonic() + self._cfg.RABBITMQ_PUBLISH_COOLDOWN_SECONDS
            raise PublicacionMovimientoError(f"No se pudo publicar la alerta en RabbitMQ: {ultimo_error!r}") from ultimo_error
