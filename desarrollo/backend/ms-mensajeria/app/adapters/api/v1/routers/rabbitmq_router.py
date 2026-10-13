# Adaptador de entrada (Inbound Adapter): endpoints REST para administrar RabbitMQ.
# Controlador DELGADO: valida (Pydantic), autoriza (rol ADMIN) y delega todo en RabbitAdminService.
#
# OJO con la ruta: por requerimiento los endpoints cuelgan de /api/rabbitmq (sin /v1), a diferencia
# del resto de microservicios (/api/v1/...). Este servicio NO se expone en el gateway local a proposito.
#
# Seguridad: son operaciones destructivas (borrar colas, purgar mensajes), asi que TODAS exigen un
# JWT valido con el rol ADMIN, igual que las demas operaciones administrativas del proyecto.

import functools
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.core.security import requerir_rol
from app.domain.services.rabbit_admin_service import (
    ConflictoRabbitError,
    OperacionRechazadaError,
    RabbitAdminService,
    RabbitNoDisponibleError,
    RecursoNoEncontradoError,
)
from app.schemas.schema_rabbitmq import (
    NOMBRE_MAX,
    NOMBRE_PATRON,
    BindingCrearSchema,
    BindingInfoSchema,
    ColaCrearSchema,
    ColaEliminadaSchema,
    ColaInfoSchema,
    ColaPurgadaSchema,
    ExchangeCrearSchema,
    ExchangeInfoSchema,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rabbitmq", tags=["RabbitMQ"])

# El nombre de la URL se valida igual que en el body: no vacio, sin "/" ni caracteres raros.
NombreCola = Annotated[str, Path(min_length=1, max_length=NOMBRE_MAX, pattern=NOMBRE_PATRON)]


def get_service() -> RabbitAdminService:
    return RabbitAdminService()


def _manejar_errores_dominio(func):
    """Traduce las excepciones del servicio a codigos HTTP en un solo lugar."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RecursoNoEncontradoError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except ConflictoRabbitError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        except OperacionRechazadaError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
        except RabbitNoDisponibleError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    return wrapper


def _auditar(claims: dict, accion: str) -> None:
    """Deja rastro de QUIEN hizo una operacion administrativa (identidad tomada del JWT validado)."""
    logger.info("Admin RabbitMQ: %s por %s", accion, claims.get("oid") or claims.get("sub") or "desconocido")


@router.post("/queues", response_model=ColaInfoSchema, status_code=status.HTTP_201_CREATED)
@_manejar_errores_dominio
def crear_cola(
    payload: ColaCrearSchema,
    service: RabbitAdminService = Depends(get_service),
    claims: dict = Depends(requerir_rol("ADMIN")),
):
    """Declara una cola (con TTL, longitud maxima y dead-lettering opcionales)."""
    _auditar(claims, f"crear cola '{payload.name}'")
    return service.crear_cola(payload)


@router.get("/queues/{name}", response_model=ColaInfoSchema)
@_manejar_errores_dominio
def obtener_cola(
    name: NombreCola,
    service: RabbitAdminService = Depends(get_service),
    _claims: dict = Depends(requerir_rol("ADMIN")),
):
    """Mensajes listos y consumidores de una cola."""
    return service.obtener_cola(name)


@router.delete("/queues/{name}", response_model=ColaEliminadaSchema)
@_manejar_errores_dominio
def eliminar_cola(
    name: NombreCola,
    if_unused: Annotated[bool, Query(description="Solo borrar si no tiene consumidores")] = False,
    if_empty: Annotated[bool, Query(description="Solo borrar si no tiene mensajes")] = False,
    service: RabbitAdminService = Depends(get_service),
    claims: dict = Depends(requerir_rol("ADMIN")),
):
    """Elimina una cola. Usa if_unused / if_empty para evitar borrar algo en uso."""
    _auditar(claims, f"ELIMINAR cola '{name}' (if_unused={if_unused}, if_empty={if_empty})")
    return service.eliminar_cola(name, if_unused=if_unused, if_empty=if_empty)


@router.post("/queues/{name}/purge", response_model=ColaPurgadaSchema)
@_manejar_errores_dominio
def purgar_cola(
    name: NombreCola,
    service: RabbitAdminService = Depends(get_service),
    claims: dict = Depends(requerir_rol("ADMIN")),
):
    """Descarta los mensajes listos de una cola (p. ej. vaciar una DLQ ya revisada)."""
    _auditar(claims, f"PURGAR cola '{name}'")
    return service.purgar_cola(name)


@router.post("/exchanges", response_model=ExchangeInfoSchema, status_code=status.HTTP_201_CREATED)
@_manejar_errores_dominio
def crear_exchange(
    payload: ExchangeCrearSchema,
    service: RabbitAdminService = Depends(get_service),
    claims: dict = Depends(requerir_rol("ADMIN")),
):
    """Declara un exchange (direct, topic, fanout o headers)."""
    _auditar(claims, f"crear exchange '{payload.name}' ({payload.type})")
    return service.crear_exchange(payload)


@router.post("/bindings", response_model=BindingInfoSchema, status_code=status.HTTP_201_CREATED)
@_manejar_errores_dominio
def crear_binding(
    payload: BindingCrearSchema,
    service: RabbitAdminService = Depends(get_service),
    claims: dict = Depends(requerir_rol("ADMIN")),
):
    """Enlaza una cola existente a un exchange existente con una routing key."""
    _auditar(claims, f"crear binding '{payload.exchange}' -> '{payload.queue}' ({payload.routing_key!r})")
    return service.crear_binding(payload)
