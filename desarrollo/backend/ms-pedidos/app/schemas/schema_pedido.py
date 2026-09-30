# DTOs con Pydantic

from pydantic import BaseModel, ConfigDict, Field
from typing import List
from datetime import datetime


class ItemPedidoSchema(BaseModel):
    # Se referencia por SKU (no por id interno) porque es la clave de negocio
    # compartida con ms-catalogo y ms-inventario (Database per Servicio, sin FK cruzada).
    sku: str
    cantidad: int = Field(..., gt=0, description="La cantidad debe ser mayor a 0")
    precio_unitario: float = Field(..., gt=0)


class CrearPedidoSchema(BaseModel):
    cliente_id: str
    items: List[ItemPedidoSchema] = Field(..., min_length=1)


class PedidoResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente_id: str
    monto_total: float
    estado: str
    items: List[ItemPedidoSchema]
    fecha_creacion: datetime
