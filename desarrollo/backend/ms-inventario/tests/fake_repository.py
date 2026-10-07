# Implementacion en memoria del InventarioRepositoryPort, usada SOLO en tests.

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.domain.ports.inventario_repository_port import InventarioRepositoryPort


@dataclass
class FakeInventario:
    id: int
    sku: str
    cantidad_disponible: int = 0
    cantidad_reservada: int = 0
    umbral_minimo: Optional[int] = None
    fecha_creacion: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    fecha_actualizacion: Optional[datetime] = None


class FakeInventarioRepository(InventarioRepositoryPort):
    def __init__(self):
        self._data: Dict[str, FakeInventario] = {}
        self._next_id = 1

    def crear(self, datos: dict) -> FakeInventario:
        registro = FakeInventario(id=self._next_id, **datos)
        self._data[registro.sku] = registro
        self._next_id += 1
        return registro

    def obtener_por_sku(self, sku: str) -> Optional[FakeInventario]:
        return self._data.get(sku)

    def listar(self, solo_bajo_umbral: bool = False) -> List[FakeInventario]:
        registros = list(self._data.values())
        if solo_bajo_umbral:
            registros = [
                r for r in registros
                if r.umbral_minimo is not None and r.cantidad_disponible <= r.umbral_minimo
            ]
        return registros

    def ajustar_cantidades(self, sku: str, delta_disponible: int, delta_reservada: int,
                           min_vendible: Optional[int] = None, min_reservada: Optional[int] = None):
        registro = self._data.get(sku)
        if not registro:
            return None
        if min_vendible is not None and (registro.cantidad_disponible - registro.cantidad_reservada) < min_vendible:
            return None
        if min_reservada is not None and registro.cantidad_reservada < min_reservada:
            return None
        registro.cantidad_disponible += delta_disponible
        registro.cantidad_reservada += delta_reservada
        registro.fecha_actualizacion = datetime.now(timezone.utc)
        return registro

    def liberar_reserva(self, sku: str, cantidad: int):
        registro = self._data.get(sku)
        if not registro:
            return None
        registro.cantidad_reservada = max(0, registro.cantidad_reservada - cantidad)
        registro.fecha_actualizacion = datetime.now(timezone.utc)
        return registro

    def actualizar_umbral(self, sku: str, umbral_minimo: int):
        registro = self._data.get(sku)
        if not registro:
            return None
        registro.umbral_minimo = umbral_minimo
        return registro
