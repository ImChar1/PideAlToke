# Adaptador ConfluentKafkaAdmin contra un AdminClient FALSO (sin broker): comprueba que traduce
# bien los futuros, los errores de librdkafka y arma las llamadas correctas al cliente real.

import concurrent.futures
from types import SimpleNamespace as NS

import pytest
from confluent_kafka import KafkaError, KafkaException
from confluent_kafka.admin import AlterConfigOpType, ConfigSource, OffsetSpec

from app.domain.ports.kafka_admin_port import (
    GrupoNoEncontradoError,
    KafkaNoDisponibleError,
    OperacionRechazadaError,
    TopicoNoEncontradoError,
    TopicoYaExisteError,
)
from app.infrastructure.kafka.confluent_admin import ConfluentKafkaAdmin


def futuro(valor=None, error=None):
    f = concurrent.futures.Future()
    if error is not None:
        f.set_exception(error)
    else:
        f.set_result(valor)
    return f


def kafka_error(codigo):
    return KafkaException(KafkaError(codigo))


def particion(id_, replicas=(1, 2, 3)):
    return NS(id=id_, leader=replicas[0], replicas=list(replicas), isrs=list(replicas), error=None)


def metadata_topico(n_particiones=3, factor=3, error=None):
    reps = tuple(range(1, factor + 1))
    return NS(partitions={i: particion(i, reps) for i in range(n_particiones)}, error=error)


class AdminFalso:
    """Registra las llamadas y devuelve futuros ya resueltos."""
    def __init__(self):
        self.llamadas = []
        self.topics = {"pedidos.eventos": metadata_topico()}
        self.brokers = {1: object(), 2: object(), 3: object()}
        self.config = {}
        self.error_en = {}   # nombre de metodo -> excepcion a devolver en el futuro
        self.error_metadata = None

    def _f(self, metodo, clave, valor=None):
        self.llamadas.append((metodo, clave))
        return futuro(valor, self.error_en.get(metodo))

    def list_topics(self, timeout=None):
        if self.error_metadata:
            raise self.error_metadata
        return NS(topics=self.topics, brokers=self.brokers)

    def describe_configs(self, recursos):
        return {r: self._f("describe_configs", r.name, self.config) for r in recursos}

    def create_topics(self, nuevos):
        return {n.topic: self._f("create_topics", n) for n in nuevos}

    def incremental_alter_configs(self, recursos):
        return {r: self._f("incremental_alter_configs", r) for r in recursos}

    def create_partitions(self, nuevas):
        return {n.topic: self._f("create_partitions", n) for n in nuevas}

    def delete_topics(self, nombres):
        return {n: self._f("delete_topics", n) for n in nombres}

    def list_consumer_groups(self, request_timeout=None):
        self.llamadas.append(("list_consumer_groups", None))
        return futuro(NS(valid=self.grupos_validos, errors=[]))

    def describe_consumer_groups(self, ids, request_timeout=None):
        return {i: self._f("describe_consumer_groups", i, self.descripcion) for i in ids}

    def list_consumer_group_offsets(self, consultas, request_timeout=None):
        return {c.group_id: self._f("list_consumer_group_offsets", c.group_id, self.offsets) for c in consultas}

    def list_offsets(self, pedido, request_timeout=None):
        self.llamadas.append(("list_offsets", pedido))
        return {tp: futuro(NS(offset=self.finales[(tp.topic, tp.partition)])) for tp in pedido}


@pytest.fixture
def cliente():
    return AdminFalso()


@pytest.fixture
def admin(cliente):
    return ConfluentKafkaAdmin(cliente, timeout=1.0)


def entrada(valor, fuente=ConfigSource.DYNAMIC_TOPIC_CONFIG):
    return NS(value=valor, source=fuente)


# ------------------------------------------------------------ topicos

def test_cantidad_de_brokers_y_listado(admin):
    assert admin.cantidad_brokers() == 3
    assert admin.listar_topicos() == [{"name": "pedidos.eventos", "partitions": 3, "replication_factor": 3}]


def test_obtener_topico_devuelve_particiones_y_config(admin, cliente):
    cliente.config = {
        "retention.ms": entrada("604800000"),
        "min.insync.replicas": entrada("2"),
        "segment.ms": entrada("604800000", ConfigSource.DEFAULT_CONFIG),
    }
    t = admin.obtener_topico("pedidos.eventos")
    assert t["partitions"] == 3 and t["replication_factor"] == 3
    assert t["particiones"][0] == {"id": 0, "leader": 1, "replicas": [1, 2, 3], "isr": [1, 2, 3]}
    assert t["config"]["retention.ms"] == "604800000"
    assert t["config_personalizada"] == ["min.insync.replicas", "retention.ms"]  # la default no cuenta


def test_obtener_topico_inexistente(admin):
    with pytest.raises(TopicoNoEncontradoError):
        admin.obtener_topico("nada")


def test_obtener_topico_con_error_de_metadata_unknown(admin, cliente):
    cliente.topics["x"] = metadata_topico(error=KafkaError(KafkaError.UNKNOWN_TOPIC_OR_PART))
    with pytest.raises(TopicoNoEncontradoError):
        admin.obtener_topico("x")


def test_crear_topico_arma_newtopic(admin, cliente):
    admin.crear_topico("inventario.movimientos", 3, 3, {"retention.ms": "1000"})
    nuevo = cliente.llamadas[0][1]
    assert (nuevo.topic, nuevo.num_partitions, nuevo.replication_factor) == ("inventario.movimientos", 3, 3)
    assert nuevo.config == {"retention.ms": "1000"}


@pytest.mark.parametrize("codigo,excepcion", [
    (KafkaError.TOPIC_ALREADY_EXISTS, TopicoYaExisteError),
    (KafkaError.INVALID_REPLICATION_FACTOR, OperacionRechazadaError),
    (KafkaError.INVALID_CONFIG, OperacionRechazadaError),
    (KafkaError.UNKNOWN_TOPIC_OR_PART, TopicoNoEncontradoError),
    (KafkaError._TRANSPORT, KafkaNoDisponibleError),
    (KafkaError._ALL_BROKERS_DOWN, KafkaNoDisponibleError),
])
def test_traduce_errores_de_librdkafka(admin, cliente, codigo, excepcion):
    cliente.error_en["create_topics"] = kafka_error(codigo)
    with pytest.raises(excepcion):
        admin.crear_topico("x", 3, 3, {})


def test_timeout_del_futuro_es_503(admin, cliente):
    cliente.error_en["delete_topics"] = concurrent.futures.TimeoutError()
    with pytest.raises(KafkaNoDisponibleError, match="Timeout"):
        admin.eliminar_topico("x")


def test_metadata_caida_es_503(admin, cliente):
    cliente.error_metadata = kafka_error(KafkaError._TRANSPORT)
    with pytest.raises(KafkaNoDisponibleError):
        admin.listar_topicos()


def test_actualizar_config_usa_alter_incremental_set(admin, cliente):
    admin.actualizar_config("pedidos.eventos", {"cleanup.policy": "compact"})
    recurso = cliente.llamadas[0][1]
    (e,) = recurso.incremental_configs
    assert (e.name, e.value, e.incremental_operation) == ("cleanup.policy", "compact", AlterConfigOpType.SET)


def test_aumentar_particiones_y_eliminar(admin, cliente):
    admin.aumentar_particiones("pedidos.eventos", 6)
    admin.eliminar_topico("pedidos.eventos")
    assert cliente.llamadas[0][1].new_total_count == 6
    assert cliente.llamadas[1] == ("delete_topics", "pedidos.eventos")


# ------------------------------------------------------------ consumer groups

def grupo(estado="STABLE", miembros=()):
    return NS(group_id="analitica-ventas", state=NS(name=estado), partition_assignor="range", members=list(miembros))


def test_listar_grupos(admin, cliente):
    cliente.grupos_validos = [NS(group_id="g1", state=NS(name="STABLE")), NS(group_id="g2", state=None)]
    assert admin.listar_grupos() == [{"group_id": "g1", "state": "STABLE"}, {"group_id": "g2", "state": "UNKNOWN"}]


def test_describir_grupo_con_miembros(admin, cliente):
    tp = NS(topic="pedidos.eventos", partition=1)
    cliente.descripcion = grupo(miembros=[NS(member_id="m1", client_id="c1", host="/10.0.0.2",
                                              assignment=NS(topic_partitions=[tp]))])
    d = admin.describir_grupo("analitica-ventas")
    assert d["state"] == "STABLE" and d["members"][0]["partitions"] == ["pedidos.eventos-1"]


def test_grupo_dead_es_404(admin, cliente):
    cliente.descripcion = grupo(estado="DEAD")
    with pytest.raises(GrupoNoEncontradoError):
        admin.describir_grupo("fantasma")


def test_lag_es_offset_final_menos_offset_confirmado(admin, cliente):
    cliente.descripcion = grupo()
    cliente.offsets = NS(topic_partitions=[
        NS(topic="pedidos.eventos", partition=0, offset=8),
        NS(topic="pedidos.eventos", partition=1, offset=-1001),   # sin commit todavia
    ])
    cliente.finales = {("pedidos.eventos", 0): 10, ("pedidos.eventos", 1): 4}
    lag = admin.lag_grupo("analitica-ventas")
    assert lag["total_lag"] == 6
    assert lag["partitions"][0] == {"topic": "pedidos.eventos", "partition": 0, "current_offset": 8, "log_end_offset": 10, "lag": 2}
    assert lag["partitions"][1]["current_offset"] == 0 and lag["partitions"][1]["lag"] == 4
    pedido = next(v for m, v in cliente.llamadas if m == "list_offsets")
    assert all(spec == OffsetSpec.latest() or isinstance(spec, type(OffsetSpec.latest())) for spec in pedido.values())


def test_lag_de_grupo_sin_offsets(admin, cliente):
    cliente.descripcion = grupo()
    cliente.offsets = NS(topic_partitions=[])
    assert admin.lag_grupo("analitica-ventas") == {"group_id": "analitica-ventas", "total_lag": 0, "partitions": []}
