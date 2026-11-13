# Pruebas HTTP de /api/kafka con un Fake (sin cluster) y el JWT simulado.

import pytest
from fastapi.testclient import TestClient

import app.adapters.api.v1.routers.kafka_router as router_module
from app.core.security import validar_jwt
from app.domain.services.kafka_admin_service import KafkaAdminService
from app.main import app
from tests.fake_admin import FakeKafkaAdmin

BASE = "/api/kafka"
ADMIN = {"oid": "admin-1", "roles": ["ADMIN"]}
USUARIO = {"oid": "user-1", "roles": []}


@pytest.fixture
def fake():
    return FakeKafkaAdmin(brokers=3)


@pytest.fixture
def client(fake):
    app.dependency_overrides[router_module.get_service] = lambda: KafkaAdminService(fake)
    app.dependency_overrides[validar_jwt] = lambda: ADMIN
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_crear_topico_201_y_luego_409(client):
    cuerpo = {"name": "pedidos.eventos", "partitions": 3, "replication_factor": 3,
              "config": {"retention.ms": "604800000"}}
    r = client.post(f"{BASE}/topics", json=cuerpo)
    assert r.status_code == 201
    assert r.json()["partitions"] == 3 and len(r.json()["particiones"]) == 3
    assert client.post(f"{BASE}/topics", json=cuerpo).status_code == 409


def test_crear_usa_3_y_3_por_defecto(client, fake):
    assert client.post(f"{BASE}/topics", json={"name": "t"}).status_code == 201
    assert fake.llamadas[0][2:4] == (3, 3)


@pytest.mark.parametrize("cuerpo", [
    {"name": ""},
    {"name": "con espacio"},
    {"name": "a/b"},
    {"name": "ok", "partitions": 0},
    {"name": "ok", "replication_factor": 0},
    {"name": "ok", "partitions": 500},
])
def test_valida_el_body_422(client, cuerpo):
    assert client.post(f"{BASE}/topics", json=cuerpo).status_code == 422


def test_config_invalida_es_422_con_mensaje(client):
    r = client.post(f"{BASE}/topics", json={"name": "t", "config": {"foo": "bar"}})
    assert r.status_code == 422 and "no permitida" in r.json()["detail"]


def test_listar_obtener_y_404(client):
    client.post(f"{BASE}/topics", json={"name": "t"})
    assert [t["name"] for t in client.get(f"{BASE}/topics").json()] == ["t"]
    assert client.get(f"{BASE}/topics/t").status_code == 200
    assert client.get(f"{BASE}/topics/nada").status_code == 404


def test_patch_config_y_put_particiones(client):
    client.post(f"{BASE}/topics", json={"name": "t"})
    r = client.patch(f"{BASE}/topics/t/config", json={"config": {"cleanup.policy": "compact"}})
    assert r.status_code == 200 and r.json()["config"]["cleanup.policy"] == "compact"
    assert client.put(f"{BASE}/topics/t/partitions", json={"total": 6}).json()["partitions"] == 6
    assert client.put(f"{BASE}/topics/t/partitions", json={"total": 2}).status_code == 422


def test_eliminar_topico(client):
    client.post(f"{BASE}/topics", json={"name": "t"})
    assert client.delete(f"{BASE}/topics/t").json() == {"name": "t", "deleted": True}
    assert client.delete(f"{BASE}/topics/t").status_code == 404
    assert client.delete(f"{BASE}/topics/__consumer_offsets").status_code == 422


def test_configuraciones_permitidas(client):
    assert "retention.ms" in client.get(f"{BASE}/topics/config-permitida").json()


def test_grupos(client, fake):
    fake.grupos["analitica-ventas"] = {"state": "STABLE", "lag": [
        {"topic": "pedidos.eventos", "partition": 0, "current_offset": 1, "log_end_offset": 4, "lag": 3}]}
    assert client.get(f"{BASE}/consumer-groups").json() == [{"group_id": "analitica-ventas", "state": "STABLE"}]
    assert client.get(f"{BASE}/consumer-groups/analitica-ventas").status_code == 200
    assert client.get(f"{BASE}/consumer-groups/analitica-ventas/lag").json()["total_lag"] == 3
    assert client.get(f"{BASE}/consumer-groups/fantasma/lag").status_code == 404


def test_cluster_caido_es_503(client, fake):
    from app.domain.ports.kafka_admin_port import KafkaNoDisponibleError

    def caido():
        raise KafkaNoDisponibleError("sin brokers")
    fake.listar_topicos = caido
    assert client.get(f"{BASE}/topics").status_code == 503


def test_sin_rol_admin_es_403(client):
    app.dependency_overrides[validar_jwt] = lambda: USUARIO
    assert client.get(f"{BASE}/topics").status_code == 403
    assert client.post(f"{BASE}/topics", json={"name": "t"}).status_code == 403
    assert client.delete(f"{BASE}/topics/t").status_code == 403
    assert client.get(f"{BASE}/consumer-groups").status_code == 403


def test_sin_token_es_401_o_403():
    app.dependency_overrides.clear()
    assert TestClient(app).get(f"{BASE}/topics").status_code in (401, 403)


def test_health():
    assert TestClient(app).get("/api/v1/health").json()["status"] == "ok"
