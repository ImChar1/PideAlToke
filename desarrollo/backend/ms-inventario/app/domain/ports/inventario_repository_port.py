# Interfaz abstracta (Port) que define el contrato de persistencia para Inventario.
# El dominio (services) depende SOLO de esta abstraccion, nunca de SQLAlchemy directamente.
#
# Se trabaja por "sku" (clave de negocio) y no por "id" interno, porque es lo que
# usaran otros microservicios (ms-catalogo, ms-pedidos) para referenciar el producto.

from abc import ABC, abstractmethod
from typing import List, Optional


class InventarioRepositoryPort(ABC):

    @abstractmethod
    def crear(self, datos: dict):
        pass

    @abstractmethod
    def obtener_por_sku(self, sku: str):
        pass

    @abstractmethod
    def listar(self, solo_bajo_umbral: bool = False) -> List:
        pass

    @abstractmethod
    def ajustar_cantidades(self, sku: str, delta_disponible: int, delta_reservada: int):
        """
        Aplica un ajuste atomico sobre cantidad_disponible y cantidad_reservada
        (los deltas pueden ser negativos). Devuelve el registro actualizado o
        None si el sku no existe.
        """
        pass

    @abstractmethod
    def actualizar_umbral(self, sku: str, umbral_minimo: int):
        pass
