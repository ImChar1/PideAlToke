# Topologia de RabbitMQ del CONSUMIDOR (ms-inventario): exchanges, colas, bindings y DLQ.
#
# Se declara como DATOS (dataclasses inmutables) construidos desde `settings`, y una funcion
# que los aplica sobre un canal. Ningun nombre esta escrito en el codigo.
#
#   pedidos.events (TOPIC, dueno: ms-pedidos)
#        |  binding "pedido.*"
#        v
#   inventario.pedidos  ---(nack requeue=False / TTL / max-length)--->  pidealtoke.dlx (DIRECT)
#     x-dead-letter-exchange    = pidealtoke.dlx                              |  binding = nombre de la DLQ
#     x-dead-letter-routing-key = inventario.pedidos.dlq                      v
#                                                                    inventario.pedidos.dlq
#
# Por que cada tipo de exchange:
#   - TOPIC  (pedidos.events): los eventos se enrutan por patron (pedido.creado, pedido.*, ...).
#   - DIRECT (pidealtoke.dlx): el dead-lettering necesita enrutar a UNA cola concreta por clave exacta.
#   - FANOUT: no hay caso de uso hoy. Si luego hace falta difundir (p. ej. alertas de stock bajo a
#     varios consumidores), se agrega aqui o desde ms-mensajeria (POST /api/rabbitmq/exchanges).
#
# Declarar es idempotente SOLO si los argumentos coinciden con los existentes; si cambias los
# argumentos de una cola ya creada, RabbitMQ responde PRECONDITION_FAILED: hay que borrar la cola
# (p. ej. DELETE /api/rabbitmq/queues/{name} en ms-mensajeria) y volver a declararla.

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


def construir_topologia(cfg=settings) -> Topologia:
    """Arma la topologia a partir de la configuracion (`cfg` es inyectable para tests)."""
    return Topologia(
        exchanges=(
            ExchangeDef(cfg.RABBITMQ_EXCHANGE_PEDIDOS, "topic"),
            ExchangeDef(cfg.RABBITMQ_EXCHANGE_DLX, "direct"),
        ),
        colas=(
            # Cola de trabajo: lo que se rechaza (basic_nack requeue=False) va al DLX con la
            # routing key de la DLQ.
            ColaDef(
                cfg.RABBITMQ_QUEUE_PEDIDOS,
                argumentos={
                    "x-dead-letter-exchange": cfg.RABBITMQ_EXCHANGE_DLX,
                    "x-dead-letter-routing-key": cfg.RABBITMQ_QUEUE_PEDIDOS_DLQ,
                },
            ),
            # Dead Letter Queue: guarda los mensajes que no se pudieron procesar para revisarlos
            # (o reinyectarlos) a mano. Sin argumentos: nadie debe "dead-letterear" desde aqui.
            ColaDef(cfg.RABBITMQ_QUEUE_PEDIDOS_DLQ),
        ),
        bindings=(
            BindingDef(cfg.RABBITMQ_QUEUE_PEDIDOS, cfg.RABBITMQ_EXCHANGE_PEDIDOS, cfg.RABBITMQ_BINDING_PEDIDOS),
            # El DLX es DIRECT: la clave del binding debe ser EXACTAMENTE la x-dead-letter-routing-key.
            BindingDef(cfg.RABBITMQ_QUEUE_PEDIDOS_DLQ, cfg.RABBITMQ_EXCHANGE_DLX, cfg.RABBITMQ_QUEUE_PEDIDOS_DLQ),
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
    """Parametros de conexion AMQP. A diferencia del productor, el consumidor SI reintenta al conectar."""
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
