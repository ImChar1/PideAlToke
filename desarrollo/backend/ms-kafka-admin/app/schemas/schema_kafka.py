# Contratos (DTO) del API de administracion de Kafka: lo que entra y lo que sale.

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

# Mismo criterio que Kafka: letras, numeros, punto, guion y guion bajo. Se rechaza vacio y "."/"..".
NOMBRE_MAX = 249
NOMBRE_PATRON = r"^[a-zA-Z0-9._-]+$"


class TopicoCrearSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=NOMBRE_MAX, pattern=NOMBRE_PATRON)
    partitions: int = Field(3, ge=1, le=50, description="Numero de particiones (paralelismo maximo del consumo)")
    replication_factor: int = Field(3, ge=1, le=5, description="Copias de cada particion (<= brokers disponibles)")
    config: Dict[str, str] = Field(
        default_factory=dict,
        description="Configuracion del topico, p. ej. retention.ms, cleanup.policy, min.insync.replicas",
    )


class TopicoConfigActualizarSchema(BaseModel):
    config: Dict[str, str] = Field(..., min_length=1, description="Claves a modificar (SET incremental)")


class TopicoParticionesActualizarSchema(BaseModel):
    total: int = Field(..., ge=1, le=50, description="Nuevo total de particiones (solo se puede aumentar)")


class ParticionInfoSchema(BaseModel):
    id: int
    leader: int
    replicas: List[int]
    isr: List[int]  # replicas sincronizadas (in-sync replicas)


class TopicoResumenSchema(BaseModel):
    name: str
    partitions: int
    replication_factor: int


class TopicoDetalleSchema(TopicoResumenSchema):
    particiones: List[ParticionInfoSchema]
    config: Dict[str, Optional[str]]
    config_personalizada: List[str]  # claves que se salen del valor por defecto del broker


class TopicoEliminadoSchema(BaseModel):
    name: str
    deleted: bool = True


class GrupoResumenSchema(BaseModel):
    group_id: str
    state: str


class MiembroGrupoSchema(BaseModel):
    member_id: str
    client_id: str
    host: str
    partitions: List[str]  # "topico-particion"


class GrupoDetalleSchema(GrupoResumenSchema):
    partition_assignor: str
    members: List[MiembroGrupoSchema]


class LagParticionSchema(BaseModel):
    topic: str
    partition: int
    current_offset: int
    log_end_offset: int
    lag: int


class GrupoLagSchema(BaseModel):
    group_id: str
    total_lag: int
    partitions: List[LagParticionSchema]
