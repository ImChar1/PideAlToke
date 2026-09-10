# Pruebas de integracion de los endpoints HTTP usando TestClient.
# El JWT real de Azure AD se simula sobreescribiendo validar_jwt.

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.adapters.api.v1.routers.inventario_router import get_service
from app.core.security import validar_jwt
from app.domain.services.inventario_service import InventarioService
from tests.fake_repository import FakeInventarioRepository


def _fake_claims_admin():
    return {"roles": ["ADMIN"], "sub": "test-user"}


@pytest.fixture
def client():
    fake_service = InventarioService(FakeInventarioRepository())

    app.dependency_overrides[get_service] = lambda: fake_service
    app.dependency_overrides[validar_jwt] = _fake_claims_admin

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_crear_y_obtener_inventario(client):
    respuesta = client.post("/inventario/", json={"sku": "COMBO-001", "cantidad_disponible": 10})
    assert respuesta.status_code == 201
    assert respuesta.json()["stock_vendible"] == 10

    respuesta_get = client.get("/inventario/COMBO-001")
    assert respuesta_get.status_code == 200


def test_crear_inventario_sku_duplicado_devuelve_409(client):
    client.post("/inventario/", json={"sku": "COMBO-001", "cantidad_disponible": 10})
    respuesta = client.post("/inventario/", json={"sku": "COMBO-001", "cantidad_disponible": 5})
    assert respuesta.status_code == 409


def test_obtener_inventario_inexistente_devuelve_404(client):
    respuesta = client.get("/inventario/NO-EXISTE")
    assert respuesta.status_code == 404


def test_reservar_stock_actualiza_reservada(client):
    client.post("/inventario/", json={"sku": "COMBO-001", "cantidad_disponible": 10})

    respuesta = client.post("/inventario/COMBO-001/reservar", json={"cantidad": 3})
    assert respuesta.status_code == 200
    body = respuesta.json()
    assert body["cantidad_reservada"] == 3
    assert body["stock_vendible"] == 7


def test_reservar_stock_insuficiente_devuelve_409(client):
    client.post("/inventario/", json={"sku": "COMBO-001", "cantidad_disponible": 2})
    client.post("/inventario/COMBO-001/reservar", json={"cantidad": 2})

    respuesta = client.post("/inventario/COMBO-001/reservar", json={"cantidad": 1})
    assert respuesta.status_code == 409


def test_flujo_completo_reservar_y_confirmar_salida(client):
    client.post("/inventario/", json={"sku": "COMBO-001", "cantidad_disponible": 10})
    client.post("/inventario/COMBO-001/reservar", json={"cantidad": 4})

    respuesta = client.post("/inventario/COMBO-001/confirmar-salida", json={"cantidad": 4})
    assert respuesta.status_code == 200
    body = respuesta.json()
    assert body["cantidad_disponible"] == 6
    assert body["cantidad_reservada"] == 0


def test_liberar_stock(client):
    client.post("/inventario/", json={"sku": "COMBO-001", "cantidad_disponible": 10})
    client.post("/inventario/COMBO-001/reservar", json={"cantidad": 5})

    respuesta = client.post("/inventario/COMBO-001/liberar", json={"cantidad": 5})
    assert respuesta.status_code == 200
    assert respuesta.json()["cantidad_reservada"] == 0


def test_reponer_stock(client):
    client.post("/inventario/", json={"sku": "COMBO-001", "cantidad_disponible": 10})
    respuesta = client.post("/inventario/COMBO-001/reponer", json={"cantidad": 15})
    assert respuesta.status_code == 200
    assert respuesta.json()["cantidad_disponible"] == 25


def test_actualizar_umbral_y_filtro_bajo_umbral(client):
    client.post("/inventario/", json={"sku": "COMBO-001", "cantidad_disponible": 2})
    client.put("/inventario/COMBO-001/umbral", json={"umbral_minimo": 5})

    respuesta = client.get("/inventario/?bajo_umbral=true")
    assert respuesta.status_code == 200
    assert len(respuesta.json()) == 1
    assert respuesta.json()[0]["sku"] == "COMBO-001"


def test_endpoints_sin_token_devuelven_401_o_403():
    with TestClient(app) as client_sin_auth:
        respuesta = client_sin_auth.get("/inventario/")
        assert respuesta.status_code in (401, 403)
