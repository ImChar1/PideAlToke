# Entidad persistente Producto (mapeo ORM con SQLAlchemy)
# Corresponde exclusivamente al dominio "Catalogo de Productos": nombre, descripcion,
# precio y categoria. El STOCK NO vive aqui: segun el ADD, cada microservicio tiene su
# propia base de datos (Database por Servicio) y el control de stock en tiempo real
# es responsabilidad del microservicio de Inventario, no del Catalogo.

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric
from sqlalchemy.sql import func
from app.infrastructure.db.session import Base

class ProductoModel(Base):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # SKU: codigo unico de producto. Es la clave que usaran otros microservicios
    # (Inventario, Pedidos) para referenciar este producto sin usar FK entre bases de datos.
    sku = Column(String(50), unique=True, index=True, nullable=False)

    nombre = Column(String(150), nullable=False, index=True)
    descripcion = Column(String(500), nullable=True)

    # Numeric es mas preciso que Float para montos monetarios (evita errores de redondeo)
    precio = Column(Numeric(10, 2), nullable=False)

    categoria = Column(String(100), nullable=True, index=True)
    imagen_url = Column(String(300), nullable=True)

    # Permite "eliminar" un producto del catalogo sin borrar el registro (soft delete)
    activo = Column(Boolean, default=True, nullable=False)

    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())
    fecha_actualizacion = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
