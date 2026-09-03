#DTOs con Pydantic (Models)
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime

class ItemPedidoSchema(BaseModel):
    producto_id: int
    cantidad: int = Field(..., gt=0, description="La cantidad debe ser mayor a 0")
    precio_unitario: float

class CrearPedidoSchema(BaseModel):
    cliente_id: str
    items: List[ItemPedidoSchema]

class PedidoResponseSchema(BaseModel):
    id: int
    cliente_id: str
    monto_total: float
    estado: str
    fecha_creacion: datetime

class Config:
    from_atributes = True # Permite mapear modelos de SQLAlchemy a Pydantic