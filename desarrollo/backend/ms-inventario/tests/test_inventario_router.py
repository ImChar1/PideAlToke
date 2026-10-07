# Pruebas de integracion de los endpoints HTTP usando TestClient.
# El JWT real de Azure AD se simula sobreescribiendo validar_jwt.

import os

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

    # Los movimientos internos (reservar/liberar/confirmar-salida) exigen la clave
    # entre microservicios; este cliente simula ser ms-pedidos.
    with TestClient(app, headers={"X-Internal-Key": os.environ["INTERNAL_API_KEY"]}) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def client_usuario_sin_clave_interna():
    """Un usuario con JWT valido (incluso ADMIN) pero SIN la clave interna."""
    fake_service = InventarioService(FakeInventarioRepository())
    fake_service.crear_inventario({"sku": "COMBO-001", "cantidad_disponible": 10})
    app.dependency_overrides[get_service] = lambda: fake_service
    app.dependency_overrides[validar_jwt] = _fake_claims_admin

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_crear_y_obtener_inventario(client):
    respuesta = client.post("/api/v1/inventario/", json={"sku": "COMBO-001", "cantidad_disponible": 10})
    assert respuesta.status_code == 201
    assert respuesta.json()["stock_vendible"] == 10

    respuesta_get = client.get("/api/v1/inventario/COMBO-001")
    assert respuesta_get.status_code == 200


def test_crear_inventario_sku_duplicado_devuelve_409(client):
    client.post("/api/v1/inventario/", json={"sku": "COMBO-001", "cantidad_disponible": 10})
    respuesta = client.post("/api/v1/inventario/", json={"sku": "COMBO-001", "cantidad_disponible": 5})
    assert respuesta.status_code == 409


def test_obtener_inventario_inexistente_devuelve_404(client):
    respuesta = client.get("/api/v1/inventario/NO-EXISTE")
    assert respuesta.status_code == 404


def test_reservar_stock_actualiza_reservada(client):
    client.post("/api/v1/inventario/", json={"sku": "COMBO-001", "cantidad_disponible": 10})

    respuesta = client.post("/api/v1/inventario/COMBO-001/reservar", json={"cantidad": 3})
    assert respuesta.status_code == 200
    body = respuesta.json()
    assert body["cantidad_reservada"] == 3
    assert body["stock_vendible"] == 7


def test_reservar_stock_insuficiente_devuelve_409(client):
    client.post("/api/v1/inventario/", json={"sku": "COMBO-001", "cantidad_disponible": 2})
    client.post("/api/v1/inventario/COMBO-001/reservar", json={"cantidad": 2})

    respuesta = client.post("/api/v1/inventario/COMBO-001/reservar", json={"cantidad": 1})
    assert respuesta.status_code == 409


def test_flujo_completo_reservar_y_confirmar_salida(client):
    client.post("/api/v1/inventario/", json={"sku": "COMBO-001", "cantidad_disponible": 10})
    client.post("/api/v1/inventario/COMBO-001/reservar", json={"cantidad": 4})

    respuesta = client.post("/api/v1/inventario/COMBO-001/confirmar-salida", json={"cantidad": 4})
    assert respuesta.status_code == 200
    body = respuesta.json()
    assert body["cantidad_disponible"] == 6
    assert body["cantidad_reservada"] == 0


def test_liberar_stock(client):
    client.post("/api/v1/inventario/", json={"sku": "COMBO-001", "cantidad_disponible": 10})
    client.post("/api/v1/inventario/COMBO-001/reservar", json={"cantidad": 5})

    respuesta = client.post("/api/v1/inventario/COMBO-001/liberar", json={"cantidad": 5})
    assert respuesta.status_code == 200
    assert respuesta.json()["cantidad_reservada"] == 0


def test_reponer_stock(client):
    client.post("/api/v1/inventario/", json={"sku": "COMBO-001", "cantidad_disponible": 10})
    respuesta = client.post("/api/v1/inventario/COMBO-001/reponer", json={"cantidad": 15})
    assert respuesta.status_code == 200
    assert respuesta.json()["cantidad_disponible"] == 25


def test_actualizar_umbral_y_filtro_bajo_umbral(client):
    client.post("/api/v1/inventario/", json={"sku": "COMBO-001", "cantidad_disponible": 2})
    client.put("/api/v1/inventario/COMBO-001/umbral", json={"umbral_minimo": 5})

    respuesta = client.get("/api/v1/inventario/?bajo_umbral=true")
    assert respuesta.status_code == 200
    assert len(respuesta.json()) == 1
    assert respuesta.json()[0]["sku"] == "COMBO-001"


def test_endpoints_sin_token_devuelven_401_o_403():
    with TestClient(app) as client_sin_auth:
        respuesta = client_sin_auth.get("/api/v1/inventario/")
        assert respuesta.status_code in (401, 403)


def test_listar_y_crear_aceptan_ruta_con_y_sin_barra_final_sin_redirect(client):
    for url in ("/api/v1/inventario", "/api/v1/inventario/"):
        assert client.get(url, follow_redirects=False).status_code == 200, url
    r = client.post("/api/v1/inventario", json={"sku": "SIN-BARRA", "cantidad_disponible": 1},
                    follow_redirects=False)
    assert r.status_code == 201


@pytest.mark.parametrize("accion", ["reservar", "liberar", "confirmar-salida"])
def test_movimientos_internos_sin_clave_interna_devuelven_403(client_usuario_sin_clave_interna, accion):
    r = client_usuario_sin_clave_interna.post(f"/api/v1/inventario/COMBO-001/{accion}", json={"cantidad": 1})
    assert r.status_code == 403


def test_movimientos_internos_con_clave_incorrecta_devuelven_403(client_usuario_sin_clave_interna):
    r = client_usuario_sin_clave_interna.post(
        "/api/v1/inventario/COMBO-001/reservar", json={"cantidad": 1},
        headers={"X-Internal-Key": "otra-clave"},
    )
    assert r.status_code == 403


def test_endpoints_de_admin_no_exigen_la_clave_interna(client_usuario_sin_clave_interna):
    # reponer/umbral/lectura siguen gobernados solo por JWT + rol
    c = client_usuario_sin_clave_interna
    assert c.get("/api/v1/inventario").status_code == 200
    assert c.post("/api/v1/inventario/COMBO-001/reponer", json={"cantidad": 5}).status_code == 200


def test_si_la_clave_interna_no_esta_configurada_se_rechaza_todo(client_usuario_sin_clave_interna, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")
    r = client_usuario_sin_clave_interna.post(
        "/api/v1/inventario/COMBO-001/reservar", json={"cantidad": 1}, headers={"X-Internal-Key": ""}
    )
    assert r.status_code == 403
