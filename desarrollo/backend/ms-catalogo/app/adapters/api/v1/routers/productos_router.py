# Adaptador de entrada (Inbound Adapter): endpoints HTTP del Catalogo de Productos

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.producto_repository import ProductoRepository
from app.domain.services.producto_service import (
    ProductoService,
    ProductoNoEncontradoError,
    SkuDuplicadoError,
)
from app.schemas.schema_producto import (
    CrearProductoSchema,
    ActualizarProductoSchema,
    ProductoResponseSchema,
)
from app.core.security import validar_jwt, requerir_rol

router = APIRouter(prefix="/productos", tags=["Catalogo de Productos"])


def get_service(db: Session = Depends(get_db)) -> ProductoService:
    repository = ProductoRepository(db)
    return ProductoService(repository)


# --- Lectura: publica para cualquier usuario autenticado (rol minimo) ---

@router.get("", response_model=List[ProductoResponseSchema], include_in_schema=False)
@router.get("/", response_model=List[ProductoResponseSchema])
def listar_productos(
    categoria: Optional[str] = None,
    service: ProductoService = Depends(get_service),
    _claims: dict = Depends(validar_jwt),
):
    return service.listar_productos(categoria=categoria)


# Consulta por SKU: la usa ms-pedidos para tomar el PRECIO REAL del catalogo (el precio
# nunca debe venir del cliente). Devuelve tambien productos inactivos (campo "activo")
# para que el llamador decida; ms-pedidos los rechaza.
@router.get("/sku/{sku}", response_model=ProductoResponseSchema)
def obtener_producto_por_sku(
    sku: str,
    service: ProductoService = Depends(get_service),
    _claims: dict = Depends(validar_jwt),
):
    try:
        return service.obtener_producto_por_sku(sku)
    except ProductoNoEncontradoError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{producto_id}", response_model=ProductoResponseSchema)
def obtener_producto(
    producto_id: int,
    service: ProductoService = Depends(get_service),
    _claims: dict = Depends(validar_jwt),
):
    try:
        return service.obtener_producto(producto_id)
    except ProductoNoEncontradoError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# --- Escritura: requiere rol ADMIN (mantencion del catalogo) ---

@router.post("", response_model=ProductoResponseSchema, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", response_model=ProductoResponseSchema, status_code=status.HTTP_201_CREATED)
def crear_producto(
    payload: CrearProductoSchema,
    service: ProductoService = Depends(get_service),
    _claims: dict = Depends(requerir_rol("ADMIN")),
):
    try:
        return service.crear_producto(payload.model_dump())
    except SkuDuplicadoError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.put("/{producto_id}", response_model=ProductoResponseSchema)
def actualizar_producto(
    producto_id: int,
    payload: ActualizarProductoSchema,
    service: ProductoService = Depends(get_service),
    _claims: dict = Depends(requerir_rol("ADMIN")),
):
    try:
        return service.actualizar_producto(producto_id, payload.model_dump(exclude_unset=True))
    except ProductoNoEncontradoError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{producto_id}", response_model=ProductoResponseSchema)
def desactivar_producto(
    producto_id: int,
    service: ProductoService = Depends(get_service),
    _claims: dict = Depends(requerir_rol("ADMIN")),
):
    try:
        return service.desactivar_producto(producto_id)
    except ProductoNoEncontradoError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
