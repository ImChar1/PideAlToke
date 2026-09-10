# DTOs de entrada y salida (Pydantic) para el microservicio de Catalogo
# Alineados 1:1 con las columnas de ProductoModel (domain/models/producto.py)

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ProductoBaseSchema(BaseModel):
    sku: str = Field(..., max_length=50)
    nombre: str = Field(..., max_length=150)
    descripcion: Optional[str] = Field(default=None, max_length=500)
    precio: float = Field(..., gt=0, description="Debe ser mayor a 0")
    categoria: Optional[str] = Field(default=None, max_length=100)
    imagen_url: Optional[str] = Field(default=None, max_length=300)


class CrearProductoSchema(ProductoBaseSchema):
    pass


class ActualizarProductoSchema(BaseModel):
    # Todos opcionales: se usa para actualizaciones parciales (PUT/PATCH)
    nombre: Optional[str] = Field(default=None, max_length=150)
    descripcion: Optional[str] = Field(default=None, max_length=500)
    precio: Optional[float] = Field(default=None, gt=0)
    categoria: Optional[str] = Field(default=None, max_length=100)
    imagen_url: Optional[str] = Field(default=None, max_length=300)
    activo: Optional[bool] = None


class ProductoResponseSchema(ProductoBaseSchema):
    id: int
    activo: bool
    fecha_creacion: datetime
    fecha_actualizacion: Optional[datetime] = None

    class Config:
        from_attributes = True
