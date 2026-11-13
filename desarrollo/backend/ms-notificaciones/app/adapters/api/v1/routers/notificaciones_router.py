# Adaptador de entrada (Inbound Adapter): endpoints HTTP de lectura de notificaciones.
# Controlador DELGADO: autoriza (rol ADMIN) y delega en NotificacionService.

from typing import Annotated, List, Literal, Optional

from fastapi import APIRouter, Depends, Query

from app.core.container import notificaciones
from app.core.security import requerir_rol
from app.domain.services.notificacion_service import NotificacionService
from app.schemas.schema_notificaciones import NotificacionSchema, ResumenNotificacionesSchema

router = APIRouter(prefix="/notificaciones", tags=["Notificaciones"])


def get_service() -> NotificacionService:
    return notificaciones


@router.get("", response_model=List[NotificacionSchema], include_in_schema=False)
@router.get("/", response_model=List[NotificacionSchema])
def listar_notificaciones(
    tipo: Optional[Literal["pedido_confirmado", "pedido_cancelado", "stock_bajo"]] = None,
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
    service: NotificacionService = Depends(get_service),
    _claims: dict = Depends(requerir_rol("ADMIN")),
):
    """Ultimas notificaciones generadas desde las colas de RabbitMQ (la mas reciente primero)."""
    return service.listar(tipo, limite)


@router.get("/resumen", response_model=ResumenNotificacionesSchema)
def resumen_notificaciones(
    service: NotificacionService = Depends(get_service),
    _claims: dict = Depends(requerir_rol("ADMIN")),
):
    return service.resumen()
