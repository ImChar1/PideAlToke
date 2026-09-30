from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.infrastructure.db.session import Base

class UsuarioModel(Base):
    __tablename__ = "usuarios"

    id= Column(Integer, primary_key=True, index=True, autoincrement=True)
    azure_oid = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(150), unique=True, index=False)
    rol = Column(String(50), default="CLIENTE", nullable=False)
    activo = Column(Boolean, default=True)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())