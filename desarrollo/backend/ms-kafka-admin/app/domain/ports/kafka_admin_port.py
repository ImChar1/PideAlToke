# Interfaz abstracta (Port) de administracion de Kafka. El dominio depende SOLO de esta abstraccion:
# no sabe que detras hay confluent-kafka. Permite testear el servicio con un Fake sin broker.

from abc import ABC, abstractmethod
from typing import Dict, List


class TopicoNoEncontradoError(Exception):
    pass


class TopicoYaExisteError(Exception):
    pass


class GrupoNoEncontradoError(Exception):
    pass


class OperacionRechazadaError(Exception):
    """El broker (o una regla de negocio) rechazo la operacion: argumentos invalidos."""


class KafkaNoDisponibleError(Exception):
    """El cluster no responde (brokers caidos, timeout, red)."""


class KafkaAdminPort(ABC):

    @abstractmethod
    def cantidad_brokers(self) -> int: ...

    @abstractmethod
    def listar_topicos(self) -> List[dict]:
        """[{name, partitions, replication_factor}] (incluye los internos: el servicio los filtra)."""

    @abstractmethod
    def obtener_topico(self, nombre: str) -> dict:
        """{name, partitions, replication_factor, particiones:[...], config:{...}, config_personalizada:[...]}"""

    @abstractmethod
    def crear_topico(self, nombre: str, particiones: int, factor_replicacion: int, config: Dict[str, str]) -> None: ...

    @abstractmethod
    def actualizar_config(self, nombre: str, config: Dict[str, str]) -> None: ...

    @abstractmethod
    def aumentar_particiones(self, nombre: str, total: int) -> None: ...

    @abstractmethod
    def eliminar_topico(self, nombre: str) -> None: ...

    @abstractmethod
    def listar_grupos(self) -> List[dict]:
        """[{group_id, state}]"""

    @abstractmethod
    def describir_grupo(self, group_id: str) -> dict:
        """{group_id, state, partition_assignor, members:[{member_id, client_id, host, partitions:[...]}]}"""

    @abstractmethod
    def lag_grupo(self, group_id: str) -> dict:
        """{group_id, total_lag, partitions:[{topic, partition, current_offset, log_end_offset, lag}]}"""
