# Reglas de negocio de la administracion de Kafka, sin cluster (Fake en memoria).

import pytest

from app.domain.ports.kafka_admin_port import (
    GrupoNoEncontradoError,
    OperacionRechazadaError,
    TopicoNoEncontradoError,
    TopicoYaExisteError,
)
from app.domain.services.kafka_admin_service import KafkaAdminService, validar_config
from tests.fake_admin import FakeKafkaAdmin


@pytest.fixture
def admin():
    return FakeKafkaAdmin(brokers=3)


@pytest.fixture
def service(admin):
    return KafkaAdminService(admin)


def test_crea_topico_con_particiones_replicas_y_config(service, admin):
    t = service.crear_topico("pedidos.eventos", 3, 3, {"retention.ms": "604800000", "min.insync.replicas": "2"})
    assert t["partitions"] == 3 and t["replication_factor"] == 3
    assert admin.llamadas[0] == ("crear", "pedidos.eventos", 3, 3, {"retention.ms": "604800000", "min.insync.replicas": "2"})


def test_no_crea_topico_duplicado(service):
    service.crear_topico("a", 3, 3, {})
    with pytest.raises(TopicoYaExisteError):
        service.crear_topico("a", 3, 3, {})


def test_rechaza_replication_factor_mayor_a_los_brokers(admin):
    service = KafkaAdminService(FakeKafkaAdmin(brokers=1))
    with pytest.raises(OperacionRechazadaError, match="brokers disponibles"):
        service.crear_topico("a", 3, 3, {})


def test_rechaza_min_isr_mayor_al_factor_de_replicacion(service):
    with pytest.raises(OperacionRechazadaError, match="min.insync.replicas"):
        service.crear_topico("a", 3, 2, {"min.insync.replicas": "3"})


def test_rechaza_nombres_reservados(service):
    with pytest.raises(OperacionRechazadaError, match="reservados"):
        service.crear_topico("__mio", 1, 1, {})


@pytest.mark.parametrize("config", [
    {"auto.create.topics.enable": "true"},        # clave fuera de la lista
    {"retention.ms": "mucho"},                    # no es entero
    {"retention.ms": "-5"},                       # fuera de rango
    {"min.insync.replicas": "0"},                 # minimo 1
    {"cleanup.policy": "borrar"},                 # valor invalido
    {"compression.type": "rar"},
])
def test_validar_config_rechaza_valores_invalidos(config):
    with pytest.raises(OperacionRechazadaError):
        validar_config(config)


@pytest.mark.parametrize("config", [
    {"retention.ms": "-1"},
    {"cleanup.policy": "compact"},
    {"cleanup.policy": "compact,delete"},
    {"retention.bytes": "1073741824", "compression.type": "zstd"},
])
def test_validar_config_acepta_valores_validos(config):
    validar_config(config)


def test_actualiza_solo_las_claves_enviadas(service):
    service.crear_topico("a", 3, 3, {"retention.ms": "1000"})
    t = service.actualizar_config("a", {"cleanup.policy": "compact"})
    assert t["config"] == {"retention.ms": "1000", "cleanup.policy": "compact"}


def test_actualizar_config_de_topico_inexistente_da_404(service):
    with pytest.raises(TopicoNoEncontradoError):
        service.actualizar_config("nada", {"retention.ms": "1"})


def test_actualizar_min_isr_no_puede_superar_replicas(service):
    service.crear_topico("a", 3, 2, {})
    with pytest.raises(OperacionRechazadaError):
        service.actualizar_config("a", {"min.insync.replicas": "3"})


def test_aumenta_particiones(service):
    service.crear_topico("a", 3, 3, {})
    assert service.aumentar_particiones("a", 6)["partitions"] == 6


@pytest.mark.parametrize("total", [3, 2])
def test_no_permite_reducir_ni_repetir_particiones(service, total):
    service.crear_topico("a", 3, 3, {})
    with pytest.raises(OperacionRechazadaError):
        service.aumentar_particiones("a", total)


def test_elimina_topico(service, admin):
    service.crear_topico("a", 3, 3, {})
    service.eliminar_topico("a")
    assert "a" not in admin.topicos


def test_no_elimina_topicos_internos_ni_inexistentes(service):
    with pytest.raises(OperacionRechazadaError):
        service.eliminar_topico("__consumer_offsets")
    with pytest.raises(TopicoNoEncontradoError):
        service.eliminar_topico("nada")


def test_listar_oculta_internos_por_defecto(service):
    service.crear_topico("b", 3, 3, {})
    service.crear_topico("a", 3, 3, {})
    assert [t["name"] for t in service.listar_topicos()] == ["a", "b"]
    assert "__consumer_offsets" in [t["name"] for t in service.listar_topicos(incluir_internos=True)]


def test_grupos_listado_detalle_y_lag(service, admin):
    admin.grupos["analitica-ventas"] = {
        "state": "STABLE",
        "lag": [{"topic": "pedidos.eventos", "partition": 0, "current_offset": 8, "log_end_offset": 10, "lag": 2}],
    }
    assert service.listar_grupos() == [{"group_id": "analitica-ventas", "state": "STABLE"}]
    assert service.lag_grupo("analitica-ventas")["total_lag"] == 2
    with pytest.raises(GrupoNoEncontradoError):
        service.describir_grupo("fantasma")
