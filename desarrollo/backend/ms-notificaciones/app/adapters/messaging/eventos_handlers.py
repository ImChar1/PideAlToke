# Adaptadores de ENTRADA por mensajeria, agrupados por DOMINIO FUNCIONAL: uno por cola.
#   - notificaciones.pedidos -> manejar_notificacion_pedido
#   - alertas.stock          -> manejar_alerta_stock
# Reciben el mensaje de RabbitMQ, lo validan y delegan en el dominio (NotificacionService).
# No hay reglas de negocio ni pika aqui: la logica de procesamiento queda separada de la mensajeria.
#
# Contrato con el consumidor (rabbitmq_consumer.py), que es quien hace el ACK / NACK:
#   - el handler retorna            -> el consumidor hace ACK
#   - lanza NonRetryableError       -> NACK sin requeue: va DIRECTO a la DLQ (payload roto, no se arregla)
#   - lanza otra excepcion          -> se reintenta con backoff y, agotados, NACK -> DLQ

import logging

from pydantic import ValidationError

from app.core.container import notificaciones
from app.infrastructure.messaging.rabbitmq_consumer import NonRetryableError
from app.schemas.schema_eventos import EventoAlertaStockRecibido, EventoPedidoRecibido

logger = logging.getLogger(__name__)


def _validar(modelo, cuerpo: bytes):
    try:
        return modelo.model_validate_json(cuerpo)
    except ValidationError as e:
        raise NonRetryableError(f"{modelo.__name__} invalido ({e.error_count()} error(es) de validacion)") from e


def manejar_notificacion_pedido(cuerpo: bytes, propiedades, metodo, service=None) -> None:
    """Handler de la cola `notificaciones.pedidos`."""
    evento = _validar(EventoPedidoRecibido, cuerpo)
    generada = (service or notificaciones).notificar_pedido(evento)
    logger.info(
        "Evento de pedido recibido: tipo=%s pedido_id=%s event_id=%s routing_key=%s notificacion=%s",
        evento.tipo, evento.pedido_id, evento.event_id, metodo.routing_key, "generada" if generada else "omitida",
    )


def manejar_alerta_stock(cuerpo: bytes, propiedades, metodo, service=None) -> None:
    """Handler de la cola `alertas.stock`."""
    evento = _validar(EventoAlertaStockRecibido, cuerpo)
    generada = (service or notificaciones).notificar_stock_bajo(evento)
    logger.info(
        "Alerta de stock recibida: sku=%s disponible=%d event_id=%s notificacion=%s",
        evento.sku, evento.stock_disponible, evento.event_id, "generada" if generada else "duplicada",
    )
