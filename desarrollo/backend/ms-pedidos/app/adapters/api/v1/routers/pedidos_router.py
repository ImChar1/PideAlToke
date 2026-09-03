# Inbound Adapters (Adaptadores de entrada)

# APIRouter (Controllers)

#Instanciamos el service y el repository dentro del endpoint de FastAPI inyectando la session de la db.

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from app.infrastructure.db.session import get_db
from app.schemas.schema_pedido import CrearPedidoSchema, PedidoResponseSchema
from app.infrastructure.repositories.pedido_repository import PedidoRepositorySQLAlchemy
from app.domain.services.pedido_service import PedidoService

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])

@router.post("/", response_model=PedidoResponseSchema, status_code=status.HTTP_201_CREATED)
def crear_pedido(pedido_data: CrearPedidoSchema, db: Session = Depends(get_db)):
    # Inyección manual de dependencias siguiendo la arquitectura
    repository = PedidoRepositorySQLAlchemy(db)
    service = PedidoService(repository)

    try:
        nuevo_pedido = service.crear_nuevo_pedido(pedido_data)
        return nuevo_pedido
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al procesar el pedido: {str(e)}"
        )