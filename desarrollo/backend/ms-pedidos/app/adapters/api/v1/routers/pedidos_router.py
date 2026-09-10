# Inbound Adapters (Adaptadores de entrada)
# APIRouter (Controllers)

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.schemas.schema_pedido import CrearPedidoSchema, PedidoResponseSchema
from app.infrastructure.repositories.pedido_repository import PedidoRepositorySQLAlchemy
from app.infrastructure.clients.inventario_client import InventarioHttpClient
from app.domain.services.pedido_service import PedidoService
from app.domain.ports.inventario_client_port import (
    StockInsuficienteError,
    InventarioNoDisponibleError,
)
from app.core.security import validar_jwt, obtener_token_bearer

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


@router.post("/", response_model=PedidoResponseSchema, status_code=status.HTTP_201_CREATED)
def crear_pedido(
    pedido_data: CrearPedidoSchema,
    db: Session = Depends(get_db),
    _claims: dict = Depends(validar_jwt),
    token: str = Depends(obtener_token_bearer),
):
    # Inyección manual de dependencias siguiendo la arquitectura hexagonal.
    # El token del usuario se reenvia al InventarioHttpClient para que ms-inventario
    # pueda validar el JWT igual que en cualquier otra peticion (propagacion de identidad).
    repository = PedidoRepositorySQLAlchemy(db)
    inventario_client = InventarioHttpClient(token=token)
    service = PedidoService(repository, inventario_client)

    try:
        return service.crear_nuevo_pedido(pedido_data)
    except StockInsuficienteError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except InventarioNoDisponibleError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al procesar el pedido: {str(e)}",
        )


@router.get("/{pedido_id}", response_model=PedidoResponseSchema)
def obtener_pedido(
    pedido_id: int,
    db: Session = Depends(get_db),
    _claims: dict = Depends(validar_jwt),
):
    repository = PedidoRepositorySQLAlchemy(db)
    pedido = repository.obtener_por_id(pedido_id)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")
    return pedido
