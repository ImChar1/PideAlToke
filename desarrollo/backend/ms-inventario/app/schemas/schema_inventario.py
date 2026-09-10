# DTOs de entrada y salida (Pydantic) para el microservicio de Inventario

from pydantic import BaseModel, ConfigDict, Field, computed_field
from datetime import datetime
from typing import Optional


class CrearInventarioSchema(BaseModel):
    sku: str = Field(..., max_length=50)
    cantidad_disponible: int = Field(default=0, ge=0)
    umbral_minimo: Optional[int] = Field(default=None, ge=0)


class MovimientoStockSchema(BaseModel):
    """Usado para reservar / liberar / confirmar-salida / reponer."""
    cantidad: int = Field(..., gt=0)


class ActualizarUmbralSchema(BaseModel):
    umbral_minimo: int = Field(..., ge=0)


class InventarioResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    cantidad_disponible: int
    cantidad_reservada: int
    umbral_minimo: Optional[int] = None
    fecha_creacion: datetime
    fecha_actualizacion: Optional[datetime] = None

    @computed_field
    @property
    def stock_vendible(self) -> int:
        return self.cantidad_disponible - self.cantidad_reservada
