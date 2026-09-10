# Entidad persistente Inventario (mapeo ORM con SQLAlchemy)
# Segun el ADD: "Inventario: Control de stock disponible en tiempo real".
# NO duplica datos del Catalogo (nombre, precio, descripcion): solo referencia el
# producto por su "sku" y controla cantidades. Database per Servicio (sin FK cruzada).

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.infrastructure.db.session import Base

class InventarioModel(Base):
    __tablename__ = "inventario"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Referencia de negocio al producto del Catalogo (ms-catalogo). Un producto tiene
    # exactamente un registro de inventario -> relacion 1 a 1, por eso es unique.
    sku = Column(String(50), unique=True, index=True, nullable=False)

    # Stock realmente disponible para vender ahora mismo.
    cantidad_disponible = Column(Integer, nullable=False, default=0)

    # Stock apartado por pedidos en curso (pagados o en proceso de pago) que aun no
    # se descuenta definitivamente del disponible hasta que el pedido se confirme.
    cantidad_reservada = Column(Integer, nullable=False, default=0)

    # Umbral bajo el cual se debe alertar/reponer stock (ej. sugerir reposicion).
    # Nullable porque no todos los productos necesitan una alerta configurada.
    umbral_minimo = Column(Integer, nullable=True)

    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())
    fecha_actualizacion = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
