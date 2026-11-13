# Adaptadores de ENTRADA por mensajeria: reciben el mensaje de Kafka, lo validan y delegan en el
# dominio (AnaliticaService). Equivalen a un router HTTP: aqui NO hay reglas de negocio ni Kafka,
# solo "bytes -> DTO validado -> caso de uso". Asi la logica de procesamiento queda separada de la
# infraestructura de mensajeria.

import logging
from typing import Callable

from pydantic import ValidationError

from app.domain.services.analitica_service import AnaliticaService
from app.infrastructure.kafka.kafka_consumer import Handler, MensajeKafka, NonRetryableError
from app.schemas.schema_eventos import EventoMovimientoRecibido, EventoPedidoRecibido

logger = logging.getLogger(__name__)


def _validar(modelo, mensaje: MensajeKafka):
    """Valida el payload. Un mensaje malformado no se arregla reintentando: NonRetryableError."""
    try:
        return modelo.model_validate_json(mensaje.value)
    except ValidationError as e:
        raise NonRetryableError(f"payload invalido para {modelo.__name__} ({e.error_count()} error(es)): {e.errors()[0]['msg']}") from e


def crear_handler_pedidos(service: AnaliticaService) -> Handler:
    def manejar(mensaje: MensajeKafka) -> None:
        evento = _validar(EventoPedidoRecibido, mensaje)
        aplicado = service.registrar_pedido(evento, (mensaje.topico, mensaje.particion, mensaje.offset))
        logger.info(
            "Evento de pedido %s: tipo=%s pedido_id=%s monto=%.2f %s",
            "aplicado" if aplicado else "ya aplicado (relectura)", evento.tipo, evento.pedido_id, evento.monto_total,
            f"[{mensaje.topico}-{mensaje.particion}@{mensaje.offset}]",
        )
    return manejar


def crear_handler_movimientos(service: AnaliticaService) -> Handler:
    def manejar(mensaje: MensajeKafka) -> None:
        evento = _validar(EventoMovimientoRecibido, mensaje)
        aplicado = service.registrar_movimiento(evento, (mensaje.topico, mensaje.particion, mensaje.offset))
        logger.info(
            "Movimiento de stock %s: tipo=%s sku=%s disponible=%d %s",
            "aplicado" if aplicado else "ya aplicado (relectura)", evento.tipo, evento.sku, evento.stock_disponible,
            f"[{mensaje.topico}-{mensaje.particion}@{mensaje.offset}]",
        )
    return manejar
