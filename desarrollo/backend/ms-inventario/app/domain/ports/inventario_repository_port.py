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
    def ajustar_cantidades(
        self,
        sku: str,
        delta_disponible: int,
        delta_reservada: int,
        min_vendible: Optional[int] = None,
        min_reservada: Optional[int] = None,
    ):
        """
        Aplica un ajuste ATOMICO (una sola sentencia UPDATE condicional) sobre
        cantidad_disponible y cantidad_reservada; los deltas pueden ser negativos.

        Las guardas se evaluan en la misma sentencia que el ajuste, asi dos peticiones
        concurrentes no pueden pasar ambas la validacion (sin sobreventa):
          - min_vendible:  solo aplica si (disponible - reservada) >= min_vendible
          - min_reservada: solo aplica si reservada >= min_reservada

        Devuelve el registro actualizado, o None si no se aplico (el sku no existe
        o no se cumplio una guarda).
        """
        pass

    @abstractmethod
    def liberar_reserva(self, sku: str, cantidad: int):
        """
        Resta `cantidad` de cantidad_reservada de forma atomica, sin bajar de 0.
        Devuelve el registro actualizado o None si el sku no existe.
        """
        pass

    @abstractmethod
    def actualizar_umbral(self, sku: str, umbral_minimo: int):
        pass
