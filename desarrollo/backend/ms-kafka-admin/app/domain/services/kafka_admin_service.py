# Casos de uso y reglas de la administracion de Kafka (crear / modificar / eliminar topicos,
# configuraciones y consumer groups). Sin FastAPI ni confluent-kafka: solo conoce el Port.

import logging
from typing import Dict, List

from app.domain.ports.kafka_admin_port import KafkaAdminPort, OperacionRechazadaError

logger = logging.getLogger(__name__)

# Configuraciones de topico que este servicio permite tocar. Lista cerrada a proposito: una clave
# rara (o un typo) no debe llegar al broker, y asi la superficie administrativa es acotada.
CONFIGS_ENTERAS = {
    "retention.ms",            # cuanto tiempo se conservan los mensajes (-1 = para siempre)
    "retention.bytes",         # tope de tamano por particion (-1 = sin tope)
    "min.insync.replicas",     # replicas que deben confirmar un write con acks=all
    "segment.ms",
    "segment.bytes",
    "max.message.bytes",
    "delete.retention.ms",
}
CONFIGS_TEXTO = {
    "cleanup.policy": {"delete", "compact", "compact,delete", "delete,compact"},
    "compression.type": {"producer", "uncompressed", "gzip", "snappy", "lz4", "zstd"},
}
CONFIGS_PERMITIDAS = CONFIGS_ENTERAS | set(CONFIGS_TEXTO)


def _es_interno(nombre: str) -> bool:
    return nombre.startswith("__")  # __consumer_offsets, __transaction_state...


def validar_config(config: Dict[str, str]) -> None:
    """Rechaza claves fuera de la lista y valores con formato invalido (error claro, antes del broker)."""
    for clave, valor in config.items():
        if clave not in CONFIGS_PERMITIDAS:
            raise OperacionRechazadaError(
                f"Configuracion no permitida: '{clave}'. Permitidas: {', '.join(sorted(CONFIGS_PERMITIDAS))}"
            )
        if clave in CONFIGS_ENTERAS:
            try:
                numero = int(valor)
            except (TypeError, ValueError):
                raise OperacionRechazadaError(f"'{clave}' debe ser un entero (recibido: {valor!r})")
            if numero < -1 or (clave == "min.insync.replicas" and numero < 1):
                raise OperacionRechazadaError(f"Valor fuera de rango para '{clave}': {numero}")
        elif valor not in CONFIGS_TEXTO[clave]:
            raise OperacionRechazadaError(
                f"Valor invalido para '{clave}': {valor!r}. Validos: {', '.join(sorted(CONFIGS_TEXTO[clave]))}"
            )


class KafkaAdminService:
    def __init__(self, admin: KafkaAdminPort):
        self.admin = admin

    # ------------------------------------------------------------ topicos

    def listar_topicos(self, incluir_internos: bool = False) -> List[dict]:
        topicos = self.admin.listar_topicos()
        if not incluir_internos:
            topicos = [t for t in topicos if not _es_interno(t["name"])]
        return sorted(topicos, key=lambda t: t["name"])

    def obtener_topico(self, nombre: str) -> dict:
        return self.admin.obtener_topico(nombre)

    def crear_topico(self, nombre: str, particiones: int, factor_replicacion: int, config: Dict[str, str]) -> dict:
        if _es_interno(nombre):
            raise OperacionRechazadaError("Los nombres que empiezan con '__' estan reservados para Kafka")
        validar_config(config)

        brokers = self.admin.cantidad_brokers()
        if factor_replicacion > brokers:
            raise OperacionRechazadaError(
                f"replication_factor={factor_replicacion} supera los brokers disponibles ({brokers})"
            )
        min_isr = int(config.get("min.insync.replicas", 1))
        if min_isr > factor_replicacion:
            raise OperacionRechazadaError(
                f"min.insync.replicas ({min_isr}) no puede superar replication_factor ({factor_replicacion})"
            )

        self.admin.crear_topico(nombre, particiones, factor_replicacion, config)
        return self.admin.obtener_topico(nombre)

    def actualizar_config(self, nombre: str, config: Dict[str, str]) -> dict:
        validar_config(config)
        topico = self.admin.obtener_topico(nombre)  # 404 si no existe
        if "min.insync.replicas" in config and int(config["min.insync.replicas"]) > topico["replication_factor"]:
            raise OperacionRechazadaError(
                f"min.insync.replicas no puede superar replication_factor ({topico['replication_factor']})"
            )
        self.admin.actualizar_config(nombre, config)
        return self.admin.obtener_topico(nombre)

    def aumentar_particiones(self, nombre: str, total: int) -> dict:
        topico = self.admin.obtener_topico(nombre)  # 404 si no existe
        if total <= topico["partitions"]:
            # Kafka nunca permite reducir particiones, y repetir el mismo numero no hace nada util.
            raise OperacionRechazadaError(
                f"El nuevo total ({total}) debe ser mayor al actual ({topico['partitions']}): "
                "Kafka no permite reducir particiones"
            )
        self.admin.aumentar_particiones(nombre, total)
        return self.admin.obtener_topico(nombre)

    def eliminar_topico(self, nombre: str) -> None:
        if _es_interno(nombre):
            raise OperacionRechazadaError("No se pueden eliminar los topicos internos de Kafka")
        self.admin.obtener_topico(nombre)  # 404 si no existe
        self.admin.eliminar_topico(nombre)

    # ------------------------------------------------------------ consumer groups

    def listar_grupos(self) -> List[dict]:
        return sorted(self.admin.listar_grupos(), key=lambda g: g["group_id"])

    def describir_grupo(self, group_id: str) -> dict:
        return self.admin.describir_grupo(group_id)

    def lag_grupo(self, group_id: str) -> dict:
        return self.admin.lag_grupo(group_id)
