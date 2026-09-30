# Interfaz abstracta (Port) que define el contrato de persistencia para Producto.
# El dominio (services) depende SOLO de esta abstraccion, nunca de SQLAlchemy directamente.

from abc import ABC, abstractmethod
from typing import List, Optional


class ProductoRepositoryPort(ABC):

    @abstractmethod
    def crear(self, producto_data: dict):
        pass

    @abstractmethod
    def obtener_por_id(self, producto_id: int):
        pass

    @abstractmethod
    def obtener_por_sku(self, sku: str):
        pass

    @abstractmethod
    def listar(self, categoria: Optional[str] = None) -> List:
        pass

    @abstractmethod
    def actualizar(self, producto_id: int, datos: dict):
        pass

    @abstractmethod
    def desactivar(self, producto_id: int):
        pass
