# Pruebas de integracion del router de Pedidos usando TestClient.
# Se sobreescribe validar_jwt (simula el token) y se parchea InventarioHttpClient
# por un FakeInventarioClient para no depender de red ni de ms-inventario real.

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import validar_jwt, obtener_token_bearer
from app.infrastructure.db.session import get_db
import app.adapters.api.v1.routers.pedidos_router as pedidos_router_module
from tests.fakes import FakeInventarioClient


def _fake_claims():
    return {"roles": ["USER"], "sub": "test-user"}


def _fake_token():
    return "token-de-prueba"


@pytest.fixture
def client(monkeypatch):
    # Reemplaza el cliente HTTP real por el fake dentro del router, sin tocar la DB real
    # (se usa la sqlite local definida en .env para simplificar este ejemplo de test).
    fake_inventario = FakeInventarioClient(stock={"COMBO-001": 10, "BEB-001": 0})

    def _fake_constructor(token, base_url=None):
        return fake_inventario

    monkeypatch.setattr(pedidos_router_module, "InventarioHttpClient", _fake_constructor)

    app.dependency_overrides[validar_jwt] = _fake_claims
    app.dependency_overrides[obtener_token_bearer] = _fake_token

    with TestClient(app) as test_client:
        yield test_client, fake_inventario

    app.dependency_overrides.clear()


def test_crear_pedido_ok(client):
    test_client, _ = client
    respuesta = test_client.post("/pedidos/", json={
        "cliente_id": "cliente-1",
        "items": [{"sku": "COMBO-001", "cantidad": 2, "precio_unitario": 2500}],
    })
    assert respuesta.status_code == 201
    body = respuesta.json()
    assert body["monto_total"] == 5000
    assert body["estado"] == "PENDIENTE"


def test_crear_pedido_con_stock_insuficiente_devuelve_409(client):
    test_client, _ = client
    respuesta = test_client.post("/pedidos/", json={
        "cliente_id": "cliente-1",
        "items": [{"sku": "BEB-001", "cantidad": 1, "precio_unitario": 1000}],
    })
    assert respuesta.status_code == 409


def test_crear_pedido_sin_token_devuelve_401_o_403():
    with TestClient(app) as client_sin_auth:
        respuesta = client_sin_auth.post("/pedidos/", json={
            "cliente_id": "cliente-1",
            "items": [{"sku": "COMBO-001", "cantidad": 1, "precio_unitario": 1000}],
        })
        assert respuesta.status_code in (401, 403)
