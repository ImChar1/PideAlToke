# Inbound Adapters (Adaptadores de entrada)
# APIRouter (Controllers)

import functools
from typing import List

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.schemas.schema_pedido import CrearPedidoSchema, PedidoResponseSchema
from app.infrastructure.repositories.pedido_repository import PedidoRepository
from app.infrastructure.clients.inventario_client import InventarioHttpClient
from app.infrastructure.clients.catalogo_client import CatalogoHttpClient
from app.domain.services.pedido_service import (
    PedidoService,
    PedidoNoEncontradoError,
    PedidoEstadoInvalidoError,
)
from app.domain.ports.inventario_client_port import (
    StockInsuficienteError,
    InventarioNoDisponibleError,
)
from app.domain.ports.catalogo_client_port import (
    ProductoNoDisponibleError,
    CatalogoNoDisponibleError,
)
from app.core.security import validar_jwt, obtener_token_bearer, requerir_rol

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


def get_service(
    db: Session = Depends(get_db),
    token: str = Depends(obtener_token_bearer),
) -> PedidoService:
    # Inyección manual de dependencias siguiendo la arquitectura hexagonal.
    # El token del usuario se reenvia a los clientes HTTP para que ms-inventario y
    # ms-catalogo puedan validar el JWT igual que en cualquier otra peticion
    # (propagacion de identidad).
    return PedidoService(
        PedidoRepository(db),
        InventarioHttpClient(token=token),
        CatalogoHttpClient(token=token),
    )


def _identidad(claims: dict) -> tuple[str, bool]:
    """Identidad del usuario SIEMPRE desde el JWT validado (nunca desde el body)."""
    cliente_id = claims.get("oid") or claims.get("sub")
    if not cliente_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token no contiene un identificador de usuario valido (oid/sub).",
        )
    return cliente_id, "ADMIN" in (claims.get("roles") or [])


def _manejar_errores_dominio(func):
    """
    Traduce las excepciones de dominio a codigos HTTP en un solo lugar. Cualquier otra
    excepcion NO se captura: sube como 500 y queda en el log (antes un `except Exception`
    la convertia en un 400 enganoso).
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except PedidoNoEncontradoError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except (StockInsuficienteError, PedidoEstadoInvalidoError) as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        except ProductoNoDisponibleError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
        except (InventarioNoDisponibleError, CatalogoNoDisponibleError) as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    return wrapper


@router.post("", response_model=PedidoResponseSchema, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", response_model=PedidoResponseSchema, status_code=status.HTTP_201_CREATED)
@_manejar_errores_dominio
def crear_pedido(
    pedido_data: CrearPedidoSchema,
    service: PedidoService = Depends(get_service),
    claims: dict = Depends(validar_jwt),
):
    cliente_id, _ = _identidad(claims)
    return service.crear_nuevo_pedido(pedido_data, cliente_id)


@router.get("", response_model=List[PedidoResponseSchema], include_in_schema=False)
@router.get("/", response_model=List[PedidoResponseSchema])
@_manejar_errores_dominio
def listar_pedidos(
    todos: bool = False,
    service: PedidoService = Depends(get_service),
    claims: dict = Depends(validar_jwt),
):
    """Mis pedidos. Con ?todos=true (solo ADMIN) lista los de todos los clientes."""
    cliente_id, es_admin = _identidad(claims)
    if todos and not es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un ADMIN puede listar los pedidos de todos los clientes.",
        )
    return service.listar_pedidos(cliente_id, todos=todos)


@router.get("/{pedido_id}", response_model=PedidoResponseSchema)
@_manejar_errores_dominio
def obtener_pedido(
    pedido_id: int,
    service: PedidoService = Depends(get_service),
    claims: dict = Depends(validar_jwt),
):
    cliente_id, es_admin = _identidad(claims)
    return service.obtener_pedido(pedido_id, cliente_id, es_admin)


@router.post("/{pedido_id}/cancelar", response_model=PedidoResponseSchema)
@_manejar_errores_dominio
def cancelar_pedido(
    pedido_id: int,
    service: PedidoService = Depends(get_service),
    claims: dict = Depends(validar_jwt),
):
    """Cancela un pedido PENDIENTE (del propio usuario, o cualquiera si es ADMIN) y libera su stock."""
    cliente_id, es_admin = _identidad(claims)
    return service.cancelar_pedido(pedido_id, cliente_id, es_admin)


@router.post("/{pedido_id}/confirmar", response_model=PedidoResponseSchema)
@_manejar_errores_dominio
def confirmar_pedido(
    pedido_id: int,
    service: PedidoService = Depends(get_service),
    _claims: dict = Depends(requerir_rol("ADMIN")),
):
    """Confirma un pedido PENDIENTE (rol ADMIN): descuenta en firme el stock reservado."""
    return service.confirmar_pedido(pedido_id)
