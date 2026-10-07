# Implementacion concreta del InventarioRepositoryPort utilizando SQLAlchemy

from typing import List, Optional
from sqlalchemy import case, update
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
        self,
        sku: str,
        delta_disponible: int,
        delta_reservada: int,
        min_vendible: Optional[int] = None,
        min_reservada: Optional[int] = None,
    ) -> Optional[InventarioModel]:
        # Un solo UPDATE condicional: la guarda y el ajuste ocurren de forma atomica en la
        # base de datos (a diferencia de "leer -> validar en Python -> escribir").
        stmt = update(InventarioModel).where(InventarioModel.sku == sku)
        if min_vendible is not None:
            stmt = stmt.where(
                InventarioModel.cantidad_disponible - InventarioModel.cantidad_reservada >= min_vendible
            )
        if min_reservada is not None:
            stmt = stmt.where(InventarioModel.cantidad_reservada >= min_reservada)

        stmt = stmt.values(
            cantidad_disponible=InventarioModel.cantidad_disponible + delta_disponible,
            cantidad_reservada=InventarioModel.cantidad_reservada + delta_reservada,
        )
        return self._ejecutar_y_recargar(stmt, sku)

    def liberar_reserva(self, sku: str, cantidad: int) -> Optional[InventarioModel]:
        stmt = (
            update(InventarioModel)
            .where(InventarioModel.sku == sku)
            .values(
                cantidad_reservada=case(
                    (InventarioModel.cantidad_reservada >= cantidad,
                     InventarioModel.cantidad_reservada - cantidad),
                    else_=0,
                )
            )
        )
        return self._ejecutar_y_recargar(stmt, sku)

    def _ejecutar_y_recargar(self, stmt, sku: str) -> Optional[InventarioModel]:
        try:
            resultado = self.db.execute(stmt)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        if resultado.rowcount == 0:
            return None
        return self.obtener_por_sku(sku)

    def actualizar_umbral(self, sku: str, umbral_minimo: int) -> Optional[InventarioModel]:
        registro = self.obtener_por_sku(sku)
        if not registro:
            return None
        registro.umbral_minimo = umbral_minimo
        self.db.commit()
        self.db.refresh(registro)
        return registro
