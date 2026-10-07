# Interfaz abstracta (Port) para consultar el Catalogo desde Pedidos.
# El precio de un pedido SIEMPRE se toma del catalogo, nunca del cliente.

from abc import ABC, abstractmethod


class ProductoNoDisponibleError(Exception):
    """El SKU no existe en el catalogo o el producto esta dado de baja (inactivo)."""


class CatalogoNoDisponibleError(Exception):
    """No fue posible consultar ms-catalogo (red, timeout, error 5xx)."""


class CatalogoClientPort(ABC):

    @abstractmethod
    def obtener_producto_por_sku(self, sku: str) -> dict:
        """
        Devuelve al menos {"sku": str, "precio": number} de un producto VENDIBLE.
        Lanza ProductoNoDisponibleError si no existe o esta inactivo, y
        CatalogoNoDisponibleError si el catalogo no responde.
        """
        pass
