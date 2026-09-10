# Interfaz abstracta (Port) para la comunicacion saliente con ms-inventario.
# El dominio de Pedidos depende SOLO de esta abstraccion, nunca del cliente HTTP concreto.
# Esto tambien permite testear PedidoService con un Fake, sin llamadas de red reales.

from abc import ABC, abstractmethod


class StockInsuficienteError(Exception):
    pass


class InventarioNoDisponibleError(Exception):
    pass


class InventarioClientPort(ABC):

    @abstractmethod
    def reservar_stock(self, sku: str, cantidad: int) -> dict:
        """Reserva stock en ms-inventario. Lanza StockInsuficienteError si no alcanza."""
        pass

    @abstractmethod
    def liberar_stock(self, sku: str, cantidad: int) -> dict:
        """Libera una reserva previa (usado como compensacion si el pedido falla)."""
        pass
