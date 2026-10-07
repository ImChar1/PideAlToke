from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.domain.ports.pedido_repository_port import PedidoRepositoryPort
from app.domain.models.pedido import PedidoModel

class PedidoRepository(PedidoRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    def guardar(self, pedido: PedidoModel) -> PedidoModel:
        try:
            self.db.add(pedido)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(pedido)
        return pedido

    def obtener_por_id(self, pedido_id: int) -> PedidoModel | None:
        stmt = select(PedidoModel).where(PedidoModel.id == pedido_id)
        return self.db.scalars(stmt).first()

    def listar_por_cliente(self, cliente_id: str) -> List[PedidoModel]:
        stmt = (
            select(PedidoModel)
            .where(PedidoModel.cliente_id == cliente_id)
            .order_by(PedidoModel.fecha_creacion.desc(), PedidoModel.id.desc())
        )
        return list(self.db.scalars(stmt).all())

    def listar_todos(self) -> List[PedidoModel]:
        stmt = select(PedidoModel).order_by(PedidoModel.fecha_creacion.desc(), PedidoModel.id.desc())
        return list(self.db.scalars(stmt).all())
