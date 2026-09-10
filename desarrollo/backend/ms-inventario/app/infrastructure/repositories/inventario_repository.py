# Implementacion concreta del InventarioRepositoryPort utilizando SQLAlchemy

from typing import List, Optional
from sqlalchemy.orm import Session

from app.domain.ports.inventario_repository_port import InventarioRepositoryPort
from app.domain.models.inventario import InventarioModel


class InventarioRepository(InventarioRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    def crear(self, datos: dict) -> InventarioModel:
        registro = InventarioModel(**datos)
        self.db.add(registro)
        self.db.commit()
        self.db.refresh(registro)
        return registro

    def obtener_por_sku(self, sku: str) -> Optional[InventarioModel]:
        return self.db.query(InventarioModel).filter(InventarioModel.sku == sku).first()

    def listar(self, solo_bajo_umbral: bool = False) -> List[InventarioModel]:
        query = self.db.query(InventarioModel)
        if solo_bajo_umbral:
            query = query.filter(
                InventarioModel.umbral_minimo.isnot(None),
                InventarioModel.cantidad_disponible <= InventarioModel.umbral_minimo,
            )
        return query.all()

    def ajustar_cantidades(
        self, sku: str, delta_disponible: int, delta_reservada: int
    ) -> Optional[InventarioModel]:
        registro = self.obtener_por_sku(sku)
        if not registro:
            return None
        registro.cantidad_disponible += delta_disponible
        registro.cantidad_reservada += delta_reservada
        self.db.commit()
        self.db.refresh(registro)
        return registro

    def actualizar_umbral(self, sku: str, umbral_minimo: int) -> Optional[InventarioModel]:
        registro = self.obtener_por_sku(sku)
        if not registro:
            return None
        registro.umbral_minimo = umbral_minimo
        self.db.commit()
        self.db.refresh(registro)
        return registro
