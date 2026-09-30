# Adaptador de entrada (Inbound Adapter): endpoints HTTP del Inventario

from typing import List
import functools

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.inventario_repository import InventarioRepository
from app.domain.services.inventario_service import (
    InventarioService,
    InventarioNoEncontradoError,
    SkuDuplicadoError,
    StockInsuficienteError,
    CantidadInvalidaError,
)
from app.schemas.schema_inventario import (
    CrearInventarioSchema,
    MovimientoStockSchema,
    ActualizarUmbralSchema,
    InventarioResponseSchema,
)
from app.core.security import validar_jwt, requerir_rol

router = APIRouter(prefix="/inventario", tags=["Inventario"])


def get_service(db: Session = Depends(get_db)) -> InventarioService:
    repository = InventarioRepository(db)
    return InventarioService(repository)


def _manejar_errores_dominio(func):
    """Traduce las excepciones de dominio a codigos HTTP en un solo lugar."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except InventarioNoEncontradoError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except SkuDuplicadoError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        except StockInsuficienteError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        except CantidadInvalidaError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return wrapper


# --- Lectura: cualquier usuario/microservicio autenticado ---

@router.get("/", response_model=List[InventarioResponseSchema])
def listar_inventario(
    bajo_umbral: bool = False,
    service: InventarioService = Depends(get_service),
    _claims: dict = Depends(validar_jwt),
):
    return service.listar_inventario(solo_bajo_umbral=bajo_umbral)


@router.get("/{sku}", response_model=InventarioResponseSchema)
@_manejar_errores_dominio
def obtener_inventario(
    sku: str,
    service: InventarioService = Depends(get_service),
    _claims: dict = Depends(validar_jwt),
):
    return service.obtener_inventario(sku)


# --- Escritura administrativa: alta de inventario y ajuste de umbral (rol ADMIN) ---

@router.post("/", response_model=InventarioResponseSchema, status_code=status.HTTP_201_CREATED)
@_manejar_errores_dominio
def crear_inventario(
    payload: CrearInventarioSchema,
    service: InventarioService = Depends(get_service),
    _claims: dict = Depends(requerir_rol("ADMIN")),
):
    return service.crear_inventario(payload.model_dump())


@router.put("/{sku}/umbral", response_model=InventarioResponseSchema)
@_manejar_errores_dominio
def actualizar_umbral(
    sku: str,
    payload: ActualizarUmbralSchema,
    service: InventarioService = Depends(get_service),
    _claims: dict = Depends(requerir_rol("ADMIN")),
):
    return service.actualizar_umbral(sku, payload.umbral_minimo)


@router.post("/{sku}/reponer", response_model=InventarioResponseSchema)
@_manejar_errores_dominio
def reponer_stock(
    sku: str,
    payload: MovimientoStockSchema,
    service: InventarioService = Depends(get_service),
    _claims: dict = Depends(requerir_rol("ADMIN")),
):
    return service.reponer_stock(sku, payload.cantidad)


# --- Movimientos de stock por flujo de Pedidos: requieren token valido ---
# (en produccion, restringir ademas por resource policy del API Gateway a
# llamadas internas desde ms-pedidos, no exponerlo directo al frontend)

@router.post("/{sku}/reservar", response_model=InventarioResponseSchema)
@_manejar_errores_dominio
def reservar_stock(
    sku: str,
    payload: MovimientoStockSchema,
    service: InventarioService = Depends(get_service),
    _claims: dict = Depends(validar_jwt),
):
    return service.reservar_stock(sku, payload.cantidad)


@router.post("/{sku}/liberar", response_model=InventarioResponseSchema)
@_manejar_errores_dominio
def liberar_stock(
    sku: str,
    payload: MovimientoStockSchema,
    service: InventarioService = Depends(get_service),
    _claims: dict = Depends(validar_jwt),
):
    return service.liberar_stock(sku, payload.cantidad)


@router.post("/{sku}/confirmar-salida", response_model=InventarioResponseSchema)
@_manejar_errores_dominio
def confirmar_salida(
    sku: str,
    payload: MovimientoStockSchema,
    service: InventarioService = Depends(get_service),
    _claims: dict = Depends(validar_jwt),
):
    return service.confirmar_salida(sku, payload.cantidad)
