# Implementacion concreta del ProductoRepositoryPort utilizando SQLAlchemy

from typing import List, Optional
from sqlalchemy.orm import Session

from app.domain.ports.producto_repository_port import ProductoRepositoryPort
from app.domain.models.producto import ProductoModel


class ProductoRepository(ProductoRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    def crear(self, producto_data: dict) -> ProductoModel:
        producto = ProductoModel(**producto_data)
        self.db.add(producto)
        self.db.commit()
        self.db.refresh(producto)
        return producto

    def obtener_por_id(self, producto_id: int) -> Optional[ProductoModel]:
        return self.db.query(ProductoModel).filter(ProductoModel.id == producto_id).first()

    def obtener_por_sku(self, sku: str) -> Optional[ProductoModel]:
        return self.db.query(ProductoModel).filter(ProductoModel.sku == sku).first()

    def listar(self, categoria: Optional[str] = None) -> List[ProductoModel]:
        query = self.db.query(ProductoModel).filter(ProductoModel.activo == True)  # noqa: E712
        if categoria:
            query = query.filter(ProductoModel.categoria == categoria)
        return query.all()

    def actualizar(self, producto_id: int, datos: dict) -> Optional[ProductoModel]:
        producto = self.obtener_por_id(producto_id)
        if not producto:
            return None
        for campo, valor in datos.items():
            if valor is not None:
                setattr(producto, campo, valor)
        self.db.commit()
        self.db.refresh(producto)
        return producto

    def desactivar(self, producto_id: int) -> Optional[ProductoModel]:
        producto = self.obtener_por_id(producto_id)
        if not producto:
            return None
        producto.activo = False
        self.db.commit()
        self.db.refresh(producto)
        return producto
