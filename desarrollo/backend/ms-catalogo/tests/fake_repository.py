# Repositorio en memoria del ProductoRepositoryPort, usado SOLO en tests.

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.domain.ports.producto_repository_port import ProductoRepositoryPort


@dataclass
class FakeProducto:
    id: int
    sku: str
    nombre: str
    precio: float
    descripcion: Optional[str] = None
    categoria: Optional[str] = None
    imagen_url: Optional[str] = None
    activo: bool = True
    fecha_creacion: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    fecha_actualizacion: Optional[datetime] = None


class FakeProductoRepository(ProductoRepositoryPort):
    def __init__(self):
        self._data: Dict[int, FakeProducto] = {}
        self._next_id = 1

    def crear(self, producto_data: dict) -> FakeProducto:
        p = FakeProducto(id=self._next_id, **producto_data)
        self._data[p.id] = p
        self._next_id += 1
        return p

    def obtener_por_id(self, producto_id: int):
        return self._data.get(producto_id)

    def obtener_por_sku(self, sku: str):
        return next((p for p in self._data.values() if p.sku == sku), None)

    def listar(self, categoria: Optional[str] = None) -> List[FakeProducto]:
        return [p for p in self._data.values()
                if p.activo and (categoria is None or p.categoria == categoria)]

    def actualizar(self, producto_id: int, datos: dict):
        p = self._data.get(producto_id)
        if not p:
            return None
        for k, v in datos.items():
            if v is not None:
                setattr(p, k, v)
        return p

    def desactivar(self, producto_id: int):
        p = self._data.get(producto_id)
        if not p:
            return None
        p.activo = False
        return p
