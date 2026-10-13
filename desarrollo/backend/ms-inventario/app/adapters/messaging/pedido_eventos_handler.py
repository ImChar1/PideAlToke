# Adaptador de ENTRADA (Inbound Adapter) por mensajeria: recibe los eventos de pedido de RabbitMQ.
# Es el equivalente a un router HTTP: valida el mensaje y delega en el dominio.
#
# IMPORTANTE (estado actual): hoy solo REGISTRA el evento. NO modifica stock a proposito: ms-pedidos
# ya reserva / libera / confirma el stock por HTTP de forma sincrona, y hacerlo tambien desde el
# evento duplicaria los movimientos (se liberaria dos veces la misma reserva).
# Cuando se migre el flujo de stock a mensajeria (ver README, seccion "Pendiente"), la logica va AQUI,
# llamando a InventarioService, y debe ser idempotente usando `evento.event_id`.

import logging

from pydantic import ValidationError

from app.infrastructure.messaging.rabbitmq_consumer import NonRetryableError
from app.schemas.schema_eventos_pedido import EventoPedidoRecibido

logger = logging.getLogger(__name__)


def manejar_evento_pedido(cuerpo: bytes, propiedades, metodo) -> None:
    """
    Handler del consumidor de la cola `inventario.pedidos`.
    - Mensaje malformado -> NonRetryableError (reintentar no lo arregla): directo a la DLQ.
    - Cualquier otra excepcion que se lance aqui se reintenta con backoff antes de ir a la DLQ.
    """
    try:
        evento = EventoPedidoRecibido.model_validate_json(cuerpo)
    except ValidationError as e:
        raise NonRetryableError(f"Evento de pedido invalido ({e.error_count()} error(es) de validacion)") from e

    logger.info(
        "Evento de pedido recibido: tipo=%s pedido_id=%s event_id=%s items=%d routing_key=%s",
        evento.tipo, evento.pedido_id, evento.event_id, len(evento.items), metodo.routing_key,
    )
