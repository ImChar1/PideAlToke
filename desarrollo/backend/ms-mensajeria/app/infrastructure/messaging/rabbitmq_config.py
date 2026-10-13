# Conexion a RabbitMQ del servicio administrador.
#
# A diferencia de ms-pedidos / ms-inventario, este servicio NO declara topologia de negocio: cada
# servicio declara la que le pertenece (ver app/infrastructure/messaging/rabbitmq_config.py en
# ms-pedidos y ms-inventario) y aqui solo se ADMINISTRA a demanda via REST.
#
# Se abre una conexion por operacion: pika.BlockingConnection no es thread-safe y FastAPI atiende
# los endpoints sync en un pool de hilos. Para operaciones administrativas (poco frecuentes) el
# coste de conectar es irrelevante frente a la simplicidad y la seguridad.

from contextlib import contextmanager

import pika

from app.core.config import settings


def parametros_conexion() -> pika.ConnectionParameters:
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
        connection_attempts=1,
        retry_delay=0,
    )


@contextmanager
def abrir_canal():
    """Abre conexion + canal, los entrega y SIEMPRE cierra la conexion al terminar."""
    conexion = pika.BlockingConnection(parametros_conexion())
    try:
        yield conexion.channel()
    finally:
        try:
            if conexion.is_open:
                conexion.close()
        except Exception:  # conexion medio rota: se descarta
            pass
