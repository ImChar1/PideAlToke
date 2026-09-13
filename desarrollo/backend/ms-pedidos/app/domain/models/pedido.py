from sqlalchemy import Column, Integer, String, Numeric, DateTime, JSON
from sqlalchemy.sql import func
from app.infrastructure.db.session import Base

class PedidoModel(Base):
    __tablename__ = "pedidos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cliente_id = Column(String(100), nullable=False, index=True)
    monto_total = Column(Numeric(10, 2), nullable=False)
    estado = Column(String(50), default="PENDIENTE", nullable=False)
    items = Column(JSON, nullable=False)
    fecha_creacion = Column(DateTime, server_default=func.now(), nullable=False)
