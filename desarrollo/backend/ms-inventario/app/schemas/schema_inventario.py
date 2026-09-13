from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime

class CrearInventarioSchema(BaseModel):
    sku: str = Field(..., max_length=50, description="SKU único del producto")
    cantidad_disponible: int = Field(0, ge=0)
    umbral_minimo: Optional[int] = Field(None, ge=0)

class MovimientoStockSchema(BaseModel):
    cantidad: int = Field(..., gt=0, description="La cantidad debe ser mayor a 0")

class ActualizarUmbralSchema(BaseModel):
    umbral_minimo: int = Field(..., ge=0)

class InventarioResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    cantidad_disponible: int
    cantidad_reservada: int
    umbral_minimo: Optional[int]
    fecha_creacion: datetime
    fecha_actualizacion: Optional[datetime] = None