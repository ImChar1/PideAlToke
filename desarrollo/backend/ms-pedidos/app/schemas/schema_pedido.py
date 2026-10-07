# DTOs con Pydantic

from pydantic import BaseModel, ConfigDict, Field
from typing import List
from datetime import datetime


class ItemPedidoCrearSchema(BaseModel):
    # Se referencia por SKU (no por id interno) porque es la clave de negocio
    # compartida con ms-catalogo y ms-inventario (Database per Servicio, sin FK cruzada).
    # OJO: el cliente NO envia precio ni cliente_id. El precio sale de ms-catalogo y el
    # cliente sale del JWT. Si el body trae esos campos, simplemente se ignoran.
    sku: str = Field(..., min_length=1, max_length=50)
    cantidad: int = Field(..., gt=0, description="La cantidad debe ser mayor a 0")


class CrearPedidoSchema(BaseModel):
    items: List[ItemPedidoCrearSchema] = Field(..., min_length=1)


class ItemPedidoSchema(BaseModel):
    sku: str
    cantidad: int
    precio_unitario: float


class PedidoResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente_id: str
    monto_total: float
    estado: str
    items: List[ItemPedidoSchema]
    fecha_creacion: datetime
