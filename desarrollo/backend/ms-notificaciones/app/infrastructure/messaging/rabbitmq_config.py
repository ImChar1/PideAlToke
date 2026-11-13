# Topologia de RabbitMQ del CONSUMIDOR ms-notificaciones: exchanges, colas, bindings y DLQ.
#
#   pedidos.events (TOPIC, dueno: ms-pedidos)
#        |  bindings "pedido.confirmado" y "pedido.cancelado"
#        v
#   notificaciones.pedidos --(nack requeue=False / TTL / max-length)--> pidealtoke.dlx (DIRECT)
#                                                                          |  binding = nombre de la DLQ
#                                                                          v
#                                                                  notificaciones.pedidos.dlq
#
#   pidealtoke.alertas (DIRECT, dueno: ms-inventario)
#        |  binding "stock.bajo"
#        v
#   alertas.stock ------------------(nack requeue=False)-------------> pidealtoke.dlx --> alertas.stock.dlq
#
# Por que cada tipo de exchange:
#   - TOPIC  (pedidos.events): los eventos de pedido se enrutan por patron; esta cola solo toma
#     los estados finales (confirmado / cancelado) y la de inventario toma `pedido.*`.
#   - DIRECT (pidealtoke.alertas): la alerta tiene un destino exacto por clave (`stock.bajo`).
#   - DIRECT (pidealtoke.dlx): el dead-lettering enruta a UNA DLQ concreta por clave exacta.
#
# Declarar es idempotente SOLO si los argumentos coinciden con los existentes; si cambias los
# argumentos de una cola ya creada, RabbitMQ responde PRECONDITION_FAILED: hay que borrarla
# (DELETE /api/rabbitmq/queues/{name} en ms-mensajeria) y volver a declararla.

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

import pika

from app.core.config import settings


@dataclass(frozen=True)
class ExchangeDef:
    nombre: str
    tipo: str  # "direct" | "topic" | "fanout"
    durable: bool = True


@dataclass(frozen=True)
class ColaDef:
    nombre: str
    durable: bool = True
    argumentos: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BindingDef:
    cola: str
    exchange: str
    routing_key: str


@dataclass(frozen=True)
class Topologia:
    exchanges: Tuple[ExchangeDef, ...]
    colas: Tuple[ColaDef, ...]
    bindings: Tuple[BindingDef, ...]


def _cola_con_dlq(cola: str, dlq: str, dlx: str) -> Tuple[ColaDef, ColaDef]:
    """Cola de trabajo (rechazados -> DLX con la clave de su DLQ) + su DLQ (sin dead-lettering propio)."""
    trabajo = ColaDef(cola, argumentos={"x-dead-letter-exchange": dlx, "x-dead-letter-routing-key": dlq})
    return trabajo, ColaDef(dlq)


def construir_topologia(cfg=settings) -> Topologia:
    """Arma la topologia a partir de la configuracion (`cfg` es inyectable para tests)."""
    notif, notif_dlq = _cola_con_dlq(cfg.RABBITMQ_QUEUE_NOTIF_PEDIDOS, cfg.RABBITMQ_QUEUE_NOTIF_PEDIDOS_DLQ, cfg.RABBITMQ_EXCHANGE_DLX)
    alertas, alertas_dlq = _cola_con_dlq(cfg.RABBITMQ_QUEUE_ALERTAS_STOCK, cfg.RABBITMQ_QUEUE_ALERTAS_STOCK_DLQ, cfg.RABBITMQ_EXCHANGE_DLX)
    return Topologia(
        exchanges=(
            ExchangeDef(cfg.RABBITMQ_EXCHANGE_PEDIDOS, "topic"),
            ExchangeDef(cfg.RABBITMQ_EXCHANGE_ALERTAS, "direct"),
            ExchangeDef(cfg.RABBITMQ_EXCHANGE_DLX, "direct"),
        ),
        colas=(notif, notif_dlq, alertas, alertas_dlq),
        bindings=(
            BindingDef(notif.nombre, cfg.RABBITMQ_EXCHANGE_PEDIDOS, cfg.RABBITMQ_BINDING_PEDIDO_CONFIRMADO),
            BindingDef(notif.nombre, cfg.RABBITMQ_EXCHANGE_PEDIDOS, cfg.RABBITMQ_BINDING_PEDIDO_CANCELADO),
            BindingDef(alertas.nombre, cfg.RABBITMQ_EXCHANGE_ALERTAS, cfg.RABBITMQ_BINDING_STOCK_BAJO),
            # El DLX es DIRECT: la clave del binding debe ser EXACTAMENTE la x-dead-letter-routing-key.
            BindingDef(notif_dlq.nombre, cfg.RABBITMQ_EXCHANGE_DLX, notif_dlq.nombre),
            BindingDef(alertas_dlq.nombre, cfg.RABBITMQ_EXCHANGE_DLX, alertas_dlq.nombre),
        ),
    )


def declarar_topologia(canal, topologia: Topologia) -> None:
    """Aplica la topologia sobre un canal. Orden: exchanges -> colas -> bindings."""
    for ex in topologia.exchanges:
        canal.exchange_declare(exchange=ex.nombre, exchange_type=ex.tipo, durable=ex.durable, auto_delete=False)
    for cola in topologia.colas:
        canal.queue_declare(
            queue=cola.nombre,
            durable=cola.durable,
            exclusive=False,
            auto_delete=False,
            arguments=dict(cola.argumentos) or None,
        )
    for b in topologia.bindings:
        canal.queue_bind(queue=b.cola, exchange=b.exchange, routing_key=b.routing_key)


def parametros_conexion(cfg=settings) -> pika.ConnectionParameters:
    """Parametros de conexion AMQP. El consumidor reintenta al conectar (backoff en el worker)."""
    return pika.ConnectionParameters(
        host=cfg.RABBITMQ_HOST,
        port=cfg.RABBITMQ_PORT,
        virtual_host=cfg.RABBITMQ_VHOST,
        credentials=pika.PlainCredentials(cfg.RABBITMQ_USER, cfg.RABBITMQ_PASSWORD),
        heartbeat=cfg.RABBITMQ_HEARTBEAT,
        blocked_connection_timeout=cfg.RABBITMQ_CONNECTION_TIMEOUT,
        socket_timeout=cfg.RABBITMQ_CONNECTION_TIMEOUT,
        stack_timeout=cfg.RABBITMQ_CONNECTION_TIMEOUT,
        connection_attempts=1,  # el backoff de reconexion lo maneja el worker
        retry_delay=0,
    )
