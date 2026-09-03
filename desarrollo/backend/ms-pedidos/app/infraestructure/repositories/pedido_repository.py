#Implementación de acceso a datos con SQLAlchemy

from typing import Optional
from sqlalchemy.orm import Session
from app.domain.ports.pedido_repository_port import PedidoRepositoryPort
from app.domain.models.pedido import PedidoModel

class PedidoRepositorySQLAlchemy(PedidoRepositoryPort):

    def __init__(self, db: Session):
        self.db = db

    def guardar(self, pedido:PedidoModel) -> PedidoModel:
        self.db.add(pedido)
        self.db.commit()
        self.db.refresh(pedido)
        return pedido

    def obtener_por_id(self, pedido_id: int) -> Optional[PedidoModel]:
        return self.db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()