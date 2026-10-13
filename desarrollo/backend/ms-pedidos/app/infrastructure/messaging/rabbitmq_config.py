# Configuracion de RabbitMQ del PRODUCTOR (ms-pedidos).
#
# Reparto de responsabilidades de la topologia (ver README de desarrollo/):
#   - ms-pedidos   (este modulo) -> es DUENO del exchange `pedidos.events` y lo declara.
#   - ms-inventario              -> es DUENO de su cola, su DLQ y sus bindings, y los declara.
# Declarar es idempotente siempre que los argumentos sean identicos, por eso ambos servicios
# declaran el exchange con el mismo tipo/durabilidad y NO importa quien arranque primero.
#
# Ningun nombre esta escrito aqui: todo sale de `settings` (pydantic-settings / variables de entorno).

import pika

from app.core.config import settings

# delivery_mode=2 -> el broker persiste el mensaje en disco (sobrevive a un reinicio de RabbitMQ,
# siempre que la cola sea durable).
DELIVERY_MODE_PERSISTENT = 2


def parametros_conexion() -> pika.ConnectionParameters:
    """Parametros de conexion AMQP. Timeouts cortos: se publica dentro de una peticion HTTP."""
    timeout = settings.RABBITMQ_CONNECTION_TIMEOUT
    return pika.ConnectionParameters(
        host=settings.RABBITMQ_HOST,
        port=settings.RABBITMQ_PORT,
        virtual_host=settings.RABBITMQ_VHOST,
        credentials=pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD),
        heartbeat=settings.RABBITMQ_HEARTBEAT,
        blocked_connection_timeout=timeout,
        socket_timeout=timeout,
        stack_timeout=timeout,
        # Un solo intento: si el broker no esta, se falla rapido (el reintento lo decide el publicador).
        connection_attempts=1,
        retry_delay=0,
    )


def routing_key_para(tipo: str) -> str:
    """Traduce el tipo logico del evento ('creado', ...) a la routing key configurada."""
    claves = {
        "creado": settings.RABBITMQ_RK_PEDIDO_CREADO,
        "confirmado": settings.RABBITMQ_RK_PEDIDO_CONFIRMADO,
        "cancelado": settings.RABBITMQ_RK_PEDIDO_CANCELADO,
    }
    return claves[tipo]


def declarar_topologia(canal) -> None:
    """
    Declara lo que el productor necesita: SOLO el exchange.
    TOPIC porque los consumidores filtran por patron (`pedido.*`, `pedido.cancelado`, ...).
    """
    canal.exchange_declare(
        exchange=settings.RABBITMQ_EXCHANGE_PEDIDOS,
        exchange_type="topic",
        durable=True,
        auto_delete=False,
    )
