# Adaptador de salida (Outbound Adapter): implementa KafkaAdminPort con el AdminClient de confluent-kafka.
#
# Todas las operaciones del AdminClient son ASINCRONAS y devuelven futuros: aqui se esperan con
# timeout y se traducen los errores de librdkafka a excepciones de dominio (404 / 409 / 422 / 503),
# asi el router y el servicio nunca ven tipos de confluent-kafka.

import concurrent.futures
import logging
import threading
from typing import Callable, Dict, List, Optional

from confluent_kafka import ConsumerGroupTopicPartitions, KafkaError, KafkaException, TopicPartition
from confluent_kafka.admin import (
    AdminClient,
    AlterConfigOpType,
    ConfigEntry,
    ConfigResource,
    ConfigSource,
    NewPartitions,
    NewTopic,
    OffsetSpec,
    ResourceType,
)

from app.core.config import settings
from app.domain.ports.kafka_admin_port import (
    GrupoNoEncontradoError,
    KafkaAdminPort,
    KafkaNoDisponibleError,
    OperacionRechazadaError,
    TopicoNoEncontradoError,
    TopicoYaExisteError,
)

logger = logging.getLogger(__name__)

# Errores que indican "no hay cluster al otro lado" (red, brokers caidos, timeout del broker).
_ERRORES_DE_CONEXION = {
    KafkaError._TRANSPORT,
    KafkaError._ALL_BROKERS_DOWN,
    KafkaError._TIMED_OUT,
    KafkaError._RESOLVE,
    KafkaError.REQUEST_TIMED_OUT,
    KafkaError.BROKER_NOT_AVAILABLE,
    KafkaError.NETWORK_EXCEPTION,
}
# Errores de argumentos: el broker rechazo lo pedido (no es un fallo del cluster).
_ERRORES_DE_ARGUMENTOS = {
    KafkaError.INVALID_REPLICATION_FACTOR,
    KafkaError.INVALID_PARTITIONS,
    KafkaError.INVALID_CONFIG,
    KafkaError.INVALID_REQUEST,
    KafkaError.TOPIC_EXCEPTION,
    KafkaError.POLICY_VIOLATION,
}


class ConfluentKafkaAdmin(KafkaAdminPort):

    def __init__(self, admin_client, timeout: float) -> None:
        self._admin = admin_client
        self._timeout = timeout

    # ------------------------------------------------------------ utilidades

    def _esperar(self, futuro, contexto: str):
        """Espera un futuro del AdminClient y traduce sus errores a excepciones de dominio."""
        try:
            return futuro.result(self._timeout)
        except concurrent.futures.TimeoutError as e:
            raise KafkaNoDisponibleError(f"Timeout esperando a Kafka ({contexto})") from e
        except KafkaException as e:
            raise self._traducir(e, contexto) from e

    @staticmethod
    def _traducir(e: KafkaException, contexto: str) -> Exception:
        error: Optional[KafkaError] = e.args[0] if e.args and isinstance(e.args[0], KafkaError) else None
        codigo = error.code() if error else None
        detalle = error.str() if error else str(e)
        if codigo == KafkaError.TOPIC_ALREADY_EXISTS:
            return TopicoYaExisteError(f"El topico ya existe ({contexto})")
        if codigo in (KafkaError.UNKNOWN_TOPIC_OR_PART, KafkaError.UNKNOWN_TOPIC_ID):
            return TopicoNoEncontradoError(f"El topico no existe ({contexto})")
        if codigo == KafkaError.GROUP_ID_NOT_FOUND:
            return GrupoNoEncontradoError(f"El consumer group no existe ({contexto})")
        if codigo in _ERRORES_DE_ARGUMENTOS:
            return OperacionRechazadaError(f"Kafka rechazo la operacion ({contexto}): {detalle}")
        if codigo in _ERRORES_DE_CONEXION or codigo is None:
            return KafkaNoDisponibleError(f"No se pudo hablar con Kafka ({contexto}): {detalle}")
        return KafkaNoDisponibleError(f"Error de Kafka ({contexto}): {detalle}")

    def _metadata(self):
        try:
            return self._admin.list_topics(timeout=self._timeout)
        except KafkaException as e:
            raise self._traducir(e, "metadata del cluster") from e

    @staticmethod
    def _resumen(nombre: str, md_topico) -> dict:
        particiones = md_topico.partitions
        factor = len(particiones[min(particiones)].replicas) if particiones else 0
        return {"name": nombre, "partitions": len(particiones), "replication_factor": factor}

    # ------------------------------------------------------------ topicos

    def cantidad_brokers(self) -> int:
        return len(self._metadata().brokers)

    def listar_topicos(self) -> List[dict]:
        return [self._resumen(n, t) for n, t in self._metadata().topics.items() if t.error is None]

    def obtener_topico(self, nombre: str) -> dict:
        md = self._metadata().topics.get(nombre)
        if md is None or (md.error is not None and md.error.code() == KafkaError.UNKNOWN_TOPIC_OR_PART):
            raise TopicoNoEncontradoError(f"El topico '{nombre}' no existe")
        if md.error is not None:
            raise KafkaNoDisponibleError(f"Error al leer el topico '{nombre}': {md.error.str()}")

        recurso = ConfigResource(ResourceType.TOPIC, nombre)
        entradas = self._esperar(self._admin.describe_configs([recurso])[recurso], f"configuracion de '{nombre}'")

        detalle = self._resumen(nombre, md)
        detalle["particiones"] = [
            {"id": p.id, "leader": p.leader, "replicas": list(p.replicas), "isr": list(p.isrs)}
            for _id, p in sorted(md.partitions.items())
        ]
        detalle["config"] = {n: e.value for n, e in sorted(entradas.items())}
        detalle["config_personalizada"] = sorted(
            n for n, e in entradas.items() if e.source == ConfigSource.DYNAMIC_TOPIC_CONFIG
        )
        return detalle

    def crear_topico(self, nombre: str, particiones: int, factor_replicacion: int, config: Dict[str, str]) -> None:
        nuevo = NewTopic(nombre, num_partitions=particiones, replication_factor=factor_replicacion, config=config)
        self._esperar(self._admin.create_topics([nuevo])[nombre], f"crear '{nombre}'")
        logger.info("Topico creado: %s (particiones=%d, replicas=%d)", nombre, particiones, factor_replicacion)

    def actualizar_config(self, nombre: str, config: Dict[str, str]) -> None:
        # incremental_alter_configs (SET) cambia SOLO las claves enviadas. El alter_configs clasico
        # reemplazaria TODA la configuracion y borraria los overrides que no se mencionen.
        entradas = [ConfigEntry(k, v, incremental_operation=AlterConfigOpType.SET) for k, v in config.items()]
        recurso = ConfigResource(ResourceType.TOPIC, nombre, incremental_configs=entradas)
        self._esperar(self._admin.incremental_alter_configs([recurso])[recurso], f"configurar '{nombre}'")
        logger.info("Configuracion de '%s' actualizada: %s", nombre, config)

    def aumentar_particiones(self, nombre: str, total: int) -> None:
        self._esperar(
            self._admin.create_partitions([NewPartitions(nombre, total)])[nombre], f"particiones de '{nombre}'"
        )
        logger.info("Particiones de '%s' aumentadas a %d", nombre, total)

    def eliminar_topico(self, nombre: str) -> None:
        self._esperar(self._admin.delete_topics([nombre])[nombre], f"eliminar '{nombre}'")
        logger.info("Topico eliminado: %s", nombre)

    # ------------------------------------------------------------ consumer groups

    def listar_grupos(self) -> List[dict]:
        resultado = self._esperar(self._admin.list_consumer_groups(request_timeout=self._timeout), "listar grupos")
        return [
            {"group_id": g.group_id, "state": g.state.name if g.state is not None else "UNKNOWN"}
            for g in resultado.valid
        ]

    def describir_grupo(self, group_id: str) -> dict:
        futuro = self._admin.describe_consumer_groups([group_id], request_timeout=self._timeout)[group_id]
        grupo = self._esperar(futuro, f"describir grupo '{group_id}'")
        estado = grupo.state.name if grupo.state is not None else "UNKNOWN"
        if estado == "DEAD":
            # Kafka responde "DEAD" para un group.id que no existe (sin miembros ni offsets).
            raise GrupoNoEncontradoError(f"El consumer group '{group_id}' no existe")
        miembros = []
        for m in grupo.members:
            tps = m.assignment.topic_partitions if m.assignment else []
            miembros.append({
                "member_id": m.member_id,
                "client_id": m.client_id,
                "host": m.host,
                "partitions": [f"{tp.topic}-{tp.partition}" for tp in tps],
            })
        return {
            "group_id": grupo.group_id,
            "state": estado,
            "partition_assignor": grupo.partition_assignor or "",
            "members": miembros,
        }

    def lag_grupo(self, group_id: str) -> dict:
        self.describir_grupo(group_id)  # 404 si el grupo no existe

        consulta = ConsumerGroupTopicPartitions(group_id)
        confirmados = self._esperar(
            self._admin.list_consumer_group_offsets([consulta], request_timeout=self._timeout)[group_id],
            f"offsets de '{group_id}'",
        ).topic_partitions

        # lag = (ultimo offset escrito en la particion) - (ultimo offset confirmado por el grupo)
        finales = {}
        if confirmados:
            pedido = {TopicPartition(tp.topic, tp.partition): OffsetSpec.latest() for tp in confirmados}
            for tp, futuro in self._admin.list_offsets(pedido, request_timeout=self._timeout).items():
                finales[(tp.topic, tp.partition)] = self._esperar(futuro, f"offset final de {tp.topic}-{tp.partition}").offset

        particiones = []
        for tp in sorted(confirmados, key=lambda t: (t.topic, t.partition)):
            actual = max(tp.offset, 0)  # offset negativo = el grupo aun no confirmo nada en esa particion
            final = finales.get((tp.topic, tp.partition), actual)
            particiones.append({
                "topic": tp.topic,
                "partition": tp.partition,
                "current_offset": actual,
                "log_end_offset": final,
                "lag": max(final - actual, 0),
            })
        return {"group_id": group_id, "total_lag": sum(p["lag"] for p in particiones), "partitions": particiones}


# ------------------------------------------------------------ fabrica (singleton)

_admin: Optional[KafkaAdminPort] = None
_lock = threading.Lock()


def obtener_admin(fabrica: Callable[[dict], object] = AdminClient) -> KafkaAdminPort:
    """El AdminClient es thread-safe y no conecta hasta la primera llamada: se crea una sola vez."""
    global _admin
    with _lock:
        if _admin is None:
            cliente = fabrica({
                "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                "client.id": "ms-kafka-admin",
                "socket.timeout.ms": int(settings.KAFKA_REQUEST_TIMEOUT_SECONDS * 1000),
            })
            _admin = ConfluentKafkaAdmin(cliente, settings.KAFKA_REQUEST_TIMEOUT_SECONDS)
        return _admin
