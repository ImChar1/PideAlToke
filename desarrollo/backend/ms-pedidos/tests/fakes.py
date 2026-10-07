# Dobles de prueba (fakes) usados SOLO en tests, sin base de datos ni llamadas HTTP reales.

from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from app.domain.ports.pedido_repository_port import PedidoRepositoryPort
from app.domain.ports.inventario_client_port import (
    InventarioClientPort,
    StockInsuficienteError,
    InventarioNoDisponibleError,
)
from app.domain.ports.catalogo_client_port import (
    CatalogoClientPort,
    ProductoNoDisponibleError,
    CatalogoNoDisponibleError,
)
from app.domain.models.pedido import PedidoModel


class FakePedidoRepository(PedidoRepositoryPort):
    def __init__(self, fallar_al_guardar: bool = False):
        self._data: Dict[int, PedidoModel] = {}
        self._next_id = 1
        self.fallar_al_guardar = fallar_al_guardar

    def guardar(self, pedido: PedidoModel) -> PedidoModel:
        if self.fallar_al_guardar:
            raise RuntimeError("la base de datos se cayo")
        if pedido.id is None:
            pedido.id = self._next_id
            self._next_id += 1
        if pedido.fecha_creacion is None:
            pedido.fecha_creacion = datetime.now(timezone.utc)
        self._data[pedido.id] = pedido
        return pedido

    def obtener_por_id(self, pedido_id: int) -> Optional[PedidoModel]:
        return self._data.get(pedido_id)

    def listar_por_cliente(self, cliente_id: str) -> List[PedidoModel]:
        return [p for p in self._data.values() if p.cliente_id == cliente_id]

    def listar_todos(self) -> List[PedidoModel]:
        return list(self._data.values())


class FakeInventarioClient(InventarioClientPort):
    """
    Simula ms-inventario en memoria. `stock` define cuanto stock vendible tiene cada sku de
    partida. Registra reservas, liberaciones y confirmaciones. `sku_inexistente` fuerza
    InventarioNoDisponibleError al reservar ese sku; `fallar_liberar` / `fallar_confirmar`
    simulan una caida de inventario para ciertos skus (para probar reintentos y compensacion).
    """

    def __init__(self, stock: Dict[str, int] = None, sku_inexistente: str = None):
        self.stock = dict(stock or {})
        self.reservas: Dict[str, int] = {}
        self.liberaciones: Dict[str, int] = {}
        self.confirmaciones: Dict[str, int] = {}
        self.sku_inexistente = sku_inexistente
        self.fallar_liberar: Set[str] = set()
        self.fallar_confirmar: Set[str] = set()
        self.error_inesperado_al_reservar: Optional[Exception] = None

    def reservar_stock(self, sku: str, cantidad: int) -> dict:
        if self.error_inesperado_al_reservar:
            raise self.error_inesperado_al_reservar
        if sku == self.sku_inexistente:
            raise InventarioNoDisponibleError(f"SKU '{sku}' no existe")

        disponible = self.stock.get(sku, 0)
        if cantidad > disponible:
            raise StockInsuficienteError(f"Stock insuficiente para '{sku}'")

        self.stock[sku] = disponible - cantidad
        self.reservas[sku] = self.reservas.get(sku, 0) + cantidad
        return {"sku": sku, "cantidad_reservada": self.reservas[sku]}

    def liberar_stock(self, sku: str, cantidad: int) -> dict:
        if sku in self.fallar_liberar:
            raise InventarioNoDisponibleError("inventario caido")
        self.stock[sku] = self.stock.get(sku, 0) + cantidad
        self.reservas[sku] = self.reservas.get(sku, 0) - cantidad
        self.liberaciones[sku] = self.liberaciones.get(sku, 0) + cantidad
        return {"sku": sku, "cantidad_reservada": self.reservas[sku]}

    def confirmar_salida(self, sku: str, cantidad: int) -> dict:
        if sku in self.fallar_confirmar:
            raise InventarioNoDisponibleError("inventario caido")
        self.reservas[sku] = self.reservas.get(sku, 0) - cantidad
        self.confirmaciones[sku] = self.confirmaciones.get(sku, 0) + cantidad
        return {"sku": sku, "cantidad_reservada": self.reservas[sku]}


class FakeCatalogoClient(CatalogoClientPort):
    """Simula ms-catalogo: `precios` = {sku: precio}; `inactivos` = skus dados de baja."""

    def __init__(self, precios: Dict[str, float] = None, inactivos: Set[str] = None, caido: bool = False):
        self.precios = dict(precios or {})
        self.inactivos = set(inactivos or set())
        self.caido = caido
        self.consultas: List[str] = []

    def obtener_producto_por_sku(self, sku: str) -> dict:
        if self.caido:
            raise CatalogoNoDisponibleError("catalogo caido")
        self.consultas.append(sku)
        if sku not in self.precios:
            raise ProductoNoDisponibleError(f"El producto '{sku}' no existe en el catalogo")
        if sku in self.inactivos:
            raise ProductoNoDisponibleError(f"El producto '{sku}' ya no esta disponible")
        return {"sku": sku, "precio": self.precios[sku], "activo": True}
