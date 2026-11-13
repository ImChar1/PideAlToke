# Adaptador de entrada (Inbound Adapter): endpoints REST para administrar Kafka.
# Controlador DELGADO: valida (Pydantic), autoriza (rol ADMIN) y delega todo en KafkaAdminService.
#
# Igual que ms-mensajeria, las rutas cuelgan de /api/kafka (sin /v1) y este servicio NO se expone en
# el gateway publico: es de uso operativo. Todas las operaciones exigen JWT valido con rol ADMIN.

import functools
import logging
from typing import Annotated, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.core.security import requerir_rol
from app.domain.ports.kafka_admin_port import (
    GrupoNoEncontradoError,
    KafkaNoDisponibleError,
    OperacionRechazadaError,
    TopicoNoEncontradoError,
    TopicoYaExisteError,
)
from app.domain.services.kafka_admin_service import CONFIGS_PERMITIDAS, KafkaAdminService
from app.infrastructure.kafka.confluent_admin import obtener_admin
from app.schemas.schema_kafka import (
    NOMBRE_MAX,
    NOMBRE_PATRON,
    GrupoDetalleSchema,
    GrupoLagSchema,
    GrupoResumenSchema,
    TopicoCrearSchema,
    TopicoConfigActualizarSchema,
    TopicoDetalleSchema,
    TopicoEliminadoSchema,
    TopicoParticionesActualizarSchema,
    TopicoResumenSchema,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kafka", tags=["Kafka"])

NombreTopico = Annotated[str, Path(min_length=1, max_length=NOMBRE_MAX, pattern=NOMBRE_PATRON)]
IdGrupo = Annotated[str, Path(min_length=1, max_length=NOMBRE_MAX, pattern=NOMBRE_PATRON)]


def get_service() -> KafkaAdminService:
    return KafkaAdminService(obtener_admin())


def _manejar_errores_dominio(func):
    """Traduce las excepciones del servicio a codigos HTTP en un solo lugar."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (TopicoNoEncontradoError, GrupoNoEncontradoError) as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except TopicoYaExisteError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        except OperacionRechazadaError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
        except KafkaNoDisponibleError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    return wrapper


def _auditar(claims: dict, accion: str) -> None:
    """Deja rastro de QUIEN hizo una operacion administrativa (identidad tomada del JWT validado)."""
    logger.info("Admin Kafka: %s por %s", accion, claims.get("oid") or claims.get("sub") or "desconocido")


# ------------------------------------------------------------ topicos

@router.post("/topics", response_model=TopicoDetalleSchema, status_code=status.HTTP_201_CREATED)
@_manejar_errores_dominio
def crear_topico(
    payload: TopicoCrearSchema,
    service: KafkaAdminService = Depends(get_service),
    claims: dict = Depends(requerir_rol("ADMIN")),
):
    """Crea un topico con N particiones, factor de replicacion y configuracion (retention, cleanup...)."""
    _auditar(claims, f"crear topico '{payload.name}' (p={payload.partitions}, r={payload.replication_factor})")
    return service.crear_topico(payload.name, payload.partitions, payload.replication_factor, payload.config)


@router.get("/topics", response_model=List[TopicoResumenSchema])
@_manejar_errores_dominio
def listar_topicos(
    incluir_internos: Annotated[bool, Query(description="Incluir topicos internos (__consumer_offsets...)")] = False,
    service: KafkaAdminService = Depends(get_service),
    _claims: dict = Depends(requerir_rol("ADMIN")),
):
    return service.listar_topicos(incluir_internos)


@router.get("/topics/config-permitida", response_model=List[str])
def configuraciones_permitidas(_claims: dict = Depends(requerir_rol("ADMIN"))):
    """Claves de configuracion de topico que este API acepta modificar."""
    return sorted(CONFIGS_PERMITIDAS)


@router.get("/topics/{name}", response_model=TopicoDetalleSchema)
@_manejar_errores_dominio
def obtener_topico(
    name: NombreTopico,
    service: KafkaAdminService = Depends(get_service),
    _claims: dict = Depends(requerir_rol("ADMIN")),
):
    """Particiones (lider, replicas, ISR) y configuracion del topico."""
    return service.obtener_topico(name)


@router.patch("/topics/{name}/config", response_model=TopicoDetalleSchema)
@_manejar_errores_dominio
def actualizar_config(
    name: NombreTopico,
    payload: TopicoConfigActualizarSchema,
    service: KafkaAdminService = Depends(get_service),
    claims: dict = Depends(requerir_rol("ADMIN")),
):
    """Modifica SOLO las claves enviadas; el resto de la configuracion queda igual."""
    _auditar(claims, f"configurar topico '{name}': {sorted(payload.config)}")
    return service.actualizar_config(name, payload.config)


@router.put("/topics/{name}/partitions", response_model=TopicoDetalleSchema)
@_manejar_errores_dominio
def aumentar_particiones(
    name: NombreTopico,
    payload: TopicoParticionesActualizarSchema,
    service: KafkaAdminService = Depends(get_service),
    claims: dict = Depends(requerir_rol("ADMIN")),
):
    """Aumenta las particiones (nunca se pueden reducir)."""
    _auditar(claims, f"aumentar particiones de '{name}' a {payload.total}")
    return service.aumentar_particiones(name, payload.total)


@router.delete("/topics/{name}", response_model=TopicoEliminadoSchema)
@_manejar_errores_dominio
def eliminar_topico(
    name: NombreTopico,
    service: KafkaAdminService = Depends(get_service),
    claims: dict = Depends(requerir_rol("ADMIN")),
):
    _auditar(claims, f"ELIMINAR topico '{name}'")
    service.eliminar_topico(name)
    return TopicoEliminadoSchema(name=name)


# ------------------------------------------------------------ consumer groups

@router.get("/consumer-groups", response_model=List[GrupoResumenSchema])
@_manejar_errores_dominio
def listar_grupos(
    service: KafkaAdminService = Depends(get_service),
    _claims: dict = Depends(requerir_rol("ADMIN")),
):
    return service.listar_grupos()


@router.get("/consumer-groups/{group_id}", response_model=GrupoDetalleSchema)
@_manejar_errores_dominio
def describir_grupo(
    group_id: IdGrupo,
    service: KafkaAdminService = Depends(get_service),
    _claims: dict = Depends(requerir_rol("ADMIN")),
):
    """Estado, miembros y particiones asignadas a cada miembro."""
    return service.describir_grupo(group_id)


@router.get("/consumer-groups/{group_id}/lag", response_model=GrupoLagSchema)
@_manejar_errores_dominio
def lag_grupo(
    group_id: IdGrupo,
    service: KafkaAdminService = Depends(get_service),
    _claims: dict = Depends(requerir_rol("ADMIN")),
):
    """Offsets y lag por particion: cuanto le falta al grupo para estar al dia."""
    return service.lag_grupo(group_id)
