# Dobles de prueba (fakes) usados SOLO en tests, sin base de datos ni llamadas HTTP reales.

from typing import Dict, Optional

from app.domain.ports.pedido_repository_port import PedidoRepositoryPort
from app.domain.ports.inventario_client_port import (
    InventarioClientPort,
    StockInsuficienteError,
    InventarioNoDisponibleError,
)
from app.domain.models.pedido import PedidoModel


class FakePedidoRepository(PedidoRepositoryPort):
    def __init__(self):
        self._data: Dict[int, PedidoModel] = {}
        self._next_id = 1

    def guardar(self, pedido: PedidoModel) -> PedidoModel:
        pedido.id = self._next_id
        self._data[pedido.id] = pedido
        self._next_id += 1
        return pedido

    def obtener_por_id(self, pedido_id: int) -> Optional[PedidoModel]:
        return self._data.get(pedido_id)


class FakeInventarioClient(InventarioClientPort):
    """
    Simula ms-inventario en memoria. `stock` define cuanto stock vendible
    tiene cada sku de partida; `fallar_sku` fuerza StockInsuficienteError
    para un sku especifico (para probar la compensacion/rollback).
    """

    def __init__(self, stock: Dict[str, int] = None, sku_inexistente: str = None):
        self.stock = dict(stock or {})
        self.reservas: Dict[str, int] = {}
        self.liberaciones: Dict[str, int] = {}
        self.sku_inexistente = sku_inexistente

    def reservar_stock(self, sku: str, cantidad: int) -> dict:
        if sku == self.sku_inexistente:
            raise InventarioNoDisponibleError(f"SKU '{sku}' no existe")

        disponible = self.stock.get(sku, 0)
        if cantidad > disponible:
            raise StockInsuficienteError(f"Stock insuficiente para '{sku}'")

        self.stock[sku] = disponible - cantidad
        self.reservas[sku] = self.reservas.get(sku, 0) + cantidad
        return {"sku": sku, "cantidad_reservada": self.reservas[sku]}

    def liberar_stock(self, sku: str, cantidad: int) -> dict:
        self.stock[sku] = self.stock.get(sku, 0) + cantidad
        self.reservas[sku] = self.reservas.get(sku, 0) - cantidad
        self.liberaciones[sku] = self.liberaciones.get(sku, 0) + cantidad
        return {"sku": sku, "cantidad_reservada": self.reservas[sku]}
