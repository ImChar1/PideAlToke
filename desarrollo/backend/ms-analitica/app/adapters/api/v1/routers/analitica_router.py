# Adaptador de entrada (Inbound Adapter): endpoints HTTP de lectura de la analitica en tiempo real.
# Controlador DELGADO: autoriza (rol ADMIN: son cifras de negocio) y delega en AnaliticaService.

from typing import Annotated, List

from fastapi import APIRouter, Depends, Query

from app.core.container import analitica
from app.core.security import requerir_rol
from app.domain.services.analitica_service import AnaliticaService
from app.schemas.schema_analitica import (
    AlertaStockSchema,
    MetricasSchema,
    ProductoTopSchema,
    ResumenVentasSchema,
    StockSkuSchema,
    VentasHoraSchema,
)

router = APIRouter(prefix="/analitica", tags=["Analitica"])


def get_service() -> AnaliticaService:
    return analitica


@router.get("/ventas/resumen", response_model=ResumenVentasSchema)
def resumen_ventas(
    service: AnaliticaService = Depends(get_service),
    _claims: dict = Depends(requerir_rol("ADMIN")),
):
    """Pedidos por estado, ingresos confirmados y ticket promedio (se actualiza con cada evento)."""
    return service.resumen_ventas()


@router.get("/ventas/por-hora", response_model=List[VentasHoraSchema])
def ventas_por_hora(
    service: AnaliticaService = Depends(get_service),
    _claims: dict = Depends(requerir_rol("ADMIN")),
):
    """Ventas confirmadas agrupadas por hora (UTC), ultimas 48 horas con actividad."""
    return service.ventas_por_hora()


@router.get("/productos/top", response_model=List[ProductoTopSchema])
def productos_top(
    limite: Annotated[int, Query(ge=1, le=50)] = 5,
    service: AnaliticaService = Depends(get_service),
    _claims: dict = Depends(requerir_rol("ADMIN")),
):
    """Productos mas vendidos (unidades de pedidos confirmados)."""
    return service.productos_top(limite)


@router.get("/stock/estado", response_model=List[StockSkuSchema])
def estado_stock(
    bajo_umbral: bool = False,
    service: AnaliticaService = Depends(get_service),
    _claims: dict = Depends(requerir_rol("ADMIN")),
):
    """Ultimo stock conocido por SKU, segun los movimientos recibidos."""
    return service.estado_stock(solo_bajo_umbral=bajo_umbral)


@router.get("/stock/alertas", response_model=List[AlertaStockSchema])
def alertas_stock(
    service: AnaliticaService = Depends(get_service),
    _claims: dict = Depends(requerir_rol("ADMIN")),
):
    """Ultimas alertas de stock bajo (la mas reciente primero)."""
    return service.alertas_stock()


@router.get("/metricas", response_model=MetricasSchema)
def metricas(
    service: AnaliticaService = Depends(get_service),
    _claims: dict = Depends(requerir_rol("ADMIN")),
):
    """Salud del consumo: mensajes aplicados / descartados y ultimo offset por particion."""
    return service.metricas()
