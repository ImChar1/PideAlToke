# Adaptador de ENTRADA (Inbound Adapter) por mensajeria: ms-pedidos CONSUME de RabbitMQ los eventos
# del ciclo de vida de los pedidos (pedido.creado / confirmado / cancelado) para hacer su
# SEGUIMIENTO de forma asincrona, fuera de la peticion HTTP que los origino.
#
# Es el equivalente a un router HTTP: valida el mensaje y delega. Hoy solo REGISTRA el evento
# (trazabilidad) y descarta duplicados: NO modifica pedidos ni stock a proposito, porque ese flujo ya
# se hace de forma sincrona y repetirlo desde el evento duplicaria efectos. Cuando haga falta una
# accion asincrona nueva (por ejemplo avisar al cliente o recalcular un indicador), la logica va AQUI.
#
# Entrega "al menos una vez": un mismo evento puede llegar dos veces. Por eso el handler es
# IDEMPOTENTE usando `event_id` (memoria acotada: se olvidan los mas antiguos).

import logging
import threading
from collections import OrderedDict

from pydantic import ValidationError

from app.infrastructure.messaging.rabbitmq_consumer import NonRetryableError
from app.schemas.schema_eventos import EventoPedidoSchema

logger = logging.getLogger(__name__)

_MAX_EVENTOS_RECORDADOS = 10_000
_vistos: "OrderedDict[str, None]" = OrderedDict()
_candado = threading.Lock()


def _es_duplicado(event_id: str) -> bool:
    """True si el evento ya se proceso. Si es nuevo lo recuerda (hilo-seguro: hay varios consumidores)."""
    with _candado:
        if event_id in _vistos:
            return True
        _vistos[event_id] = None
        if len(_vistos) > _MAX_EVENTOS_RECORDADOS:
            _vistos.popitem(last=False)
        return False


def manejar_evento_pedido(cuerpo: bytes, propiedades, metodo) -> None:
    """
    Handler del consumidor de la cola `pedidos.seguimiento`.
    - Mensaje malformado -> NonRetryableError (reintentar no lo arregla): directo a la DLQ.
    - Cualquier otra excepcion que se lance aqui se reintenta con backoff antes de ir a la DLQ.
    """
    try:
        evento = EventoPedidoSchema.model_validate_json(cuerpo)
    except ValidationError as e:
        raise NonRetryableError(f"Evento de pedido invalido ({e.error_count()} error(es) de validacion)") from e

    if _es_duplicado(evento.event_id):
        logger.info("Evento de pedido duplicado, se ignora: event_id=%s pedido_id=%s", evento.event_id, evento.pedido_id)
        return

    logger.info(
        "Seguimiento de pedido: tipo=%s pedido_id=%s estado=%s monto=%.2f items=%d event_id=%s routing_key=%s",
        evento.tipo, evento.pedido_id, evento.estado, evento.monto_total, len(evento.items),
        evento.event_id, metodo.routing_key,
    )
