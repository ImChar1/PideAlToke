# Contrato (DTO) de los eventos de pedido que viajan por RabbitMQ.
# Es un CONTRATO ENTRE MICROSERVICIOS: ms-inventario tiene su propia copia de solo lectura
# (schema_eventos_pedido.py). Agrega campos nuevos como opcionales para no romper consumidores.

import uuid
from datetime import datetime, timezone
from typing import List, Literal

from pydantic import BaseModel, Field


class ItemEventoSchema(BaseModel):
    sku: str
    cantidad: int
    precio_unitario: float


class EventoPedidoSchema(BaseModel):
    # Id unico del evento: permite a los consumidores descartar duplicados (entrega "al menos una vez").
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tipo: Literal["creado", "confirmado", "cancelado"]
    ocurrido_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pedido_id: int
    cliente_id: str
    estado: str
    monto_total: float
    items: List[ItemEventoSchema]

    @classmethod
    def desde_pedido(cls, tipo: str, pedido) -> "EventoPedidoSchema":
        """Arma el evento desde un PedidoModel ya persistido (duck-typing: no importa el ORM aqui)."""
        return cls(
            tipo=tipo,
            pedido_id=pedido.id,
            cliente_id=pedido.cliente_id,
            estado=pedido.estado,
            monto_total=float(pedido.monto_total),
            # Se copian solo los campos del contrato: los items guardan ademas marcas internas
            # de progreso (stock_liberado / stock_confirmado) que no deben filtrarse.
            items=[
                ItemEventoSchema(
                    sku=i["sku"], cantidad=i["cantidad"], precio_unitario=i["precio_unitario"]
                )
                for i in pedido.items
            ],
        )
