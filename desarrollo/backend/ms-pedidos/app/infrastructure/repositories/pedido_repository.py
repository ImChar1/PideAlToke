from sqlalchemy import select
from sqlalchemy.orm import Session
from app.domain.ports.pedido_repository_port import PedidoRepositoryPort
from app.domain.models.pedido import PedidoModel

class PedidoRepository(PedidoRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    def guardar(self, pedido: PedidoModel) -> PedidoModel:
        self.db.add(pedido)
        self.db.commit()
        self.db.refresh(pedido)
        return pedido

    def obtener_por_id(self, pedido_id: int) -> PedidoModel | None:
        stmt = select(PedidoModel).where(PedidoModel.id == pedido_id)
        return self.db.scalars(stmt).first()