# DTO de LECTURA de los eventos de pedido publicados por ms-pedidos (contrato entre microservicios).
# Es la copia del consumidor: `extra="ignore"` hace que campos nuevos agregados por el productor
# no rompan a este servicio. Solo se declaran los campos que ms-inventario necesita.

from typing import List, Literal

from pydantic import BaseModel, ConfigDict


class ItemEventoPedido(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sku: str
    cantidad: int


class EventoPedidoRecibido(BaseModel):
    model_config = ConfigDict(extra="ignore")

    event_id: str
    tipo: Literal["creado", "confirmado", "cancelado"]
    pedido_id: int
    cliente_id: str
    estado: str
    items: List[ItemEventoPedido]
