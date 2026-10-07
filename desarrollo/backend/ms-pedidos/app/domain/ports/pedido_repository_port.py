# Definimos la interfaz abstracta de la cual el dominio es dependiente

from abc import ABC, abstractmethod
from typing import List, Optional
from app.domain.models.pedido import PedidoModel

class PedidoRepositoryPort(ABC):

    @abstractmethod
    def guardar(self, pedido: PedidoModel) -> PedidoModel:
        """Persiste un pedido en la base de datos"""
        pass

    @abstractmethod
    def obtener_por_id(self, pedido_id: int) -> Optional[PedidoModel]:
        """Recupera un pedido por su ID"""
        pass

    @abstractmethod
    def listar_por_cliente(self, cliente_id: str) -> List[PedidoModel]:
        """Pedidos de un cliente, del mas reciente al mas antiguo"""
        pass

    @abstractmethod
    def listar_todos(self) -> List[PedidoModel]:
        """Todos los pedidos (uso administrativo), del mas reciente al mas antiguo"""
        pass
