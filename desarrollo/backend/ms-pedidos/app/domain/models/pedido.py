# Mapeo de talbla de pedidos con SQLAlchemy

from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from app.infrastructure.db.session import Base
from sqlalchemy.sql import func

class PedidoModel(Base):
    __tablename__ = "pedidos"

    id= Column(Integer, primary_key=True, idenx=True, autoincrement=True)
    cleinte_id = Column(String(100), nullable=False)
    monto_total = Column(Float, nullable=False)
    estado = Column(String(50), default="PENDIENTE")
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())