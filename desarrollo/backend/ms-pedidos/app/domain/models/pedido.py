# Mapeo de tabla de pedidos con SQLAlchemy

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from app.infrastructure.db.session import Base
from sqlalchemy.sql import func

class PedidoModel(Base):
    __tablename__ = "pedidos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    cliente_id = Column(String(100), nullable=False)
    monto_total = Column(Float, nullable=False)
    estado = Column(String(50), default="PENDIENTE")

    # Se persisten los items (sku, cantidad, precio_unitario) para poder liberar
    # el stock reservado en Inventario si el pedido se cancela mas adelante.
    items = Column(JSON, nullable=False)

    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())
