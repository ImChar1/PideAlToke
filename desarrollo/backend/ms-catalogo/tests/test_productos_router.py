# Pruebas HTTP del catalogo. El JWT real de Azure se simula sobreescribiendo validar_jwt.

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.adapters.api.v1.routers.productos_router import get_service
from app.core.security import validar_jwt
from app.domain.services.producto_service import ProductoService
from tests.fake_repository import FakeProductoRepository

BASE = "/api/v1/productos"
PRODUCTO = {"sku": "P-1", "nombre": "Hamburguesa", "precio": 6990, "categoria": "Comida Rapida"}


@pytest.fixture
def make_client():
    def _make(roles):
        servicio = ProductoService(FakeProductoRepository())
        app.dependency_overrides[get_service] = lambda: servicio
        app.dependency_overrides[validar_jwt] = lambda: {"roles": roles, "sub": "u"}
        return TestClient(app, follow_redirects=False)

    yield _make
    app.dependency_overrides.clear()


def test_admin_crea_y_lista_productos(make_client):
    c = make_client(["ADMIN"])
    r = c.post(BASE, json=PRODUCTO)
    assert r.status_code == 201 and r.json()["sku"] == "P-1"
    assert [p["sku"] for p in c.get(BASE).json()] == ["P-1"]


def test_rutas_con_y_sin_barra_final_no_redirigen(make_client):
    c = make_client(["ADMIN"])
    for url in (BASE, BASE + "/"):
        assert c.get(url).status_code == 200, url
    assert c.post(BASE + "/", json={**PRODUCTO, "sku": "P-2"}).status_code == 201


def test_cliente_puede_leer_pero_no_crear(make_client):
    c = make_client(["CLIENTE"])
    assert c.get(BASE).status_code == 200
    assert c.post(BASE, json=PRODUCTO).status_code == 403


def test_sku_duplicado_devuelve_409(make_client):
    c = make_client(["ADMIN"])
    c.post(BASE, json=PRODUCTO)
    assert c.post(BASE, json=PRODUCTO).status_code == 409


def test_precio_invalido_devuelve_422(make_client):
    c = make_client(["ADMIN"])
    assert c.post(BASE, json={**PRODUCTO, "precio": 0}).status_code == 422


def test_obtener_inexistente_devuelve_404(make_client):
    assert make_client(["CLIENTE"]).get(BASE + "/99").status_code == 404


def test_delete_desactiva_el_producto_y_requiere_admin(make_client):
    c = make_client(["ADMIN"])
    pid = c.post(BASE, json=PRODUCTO).json()["id"]
    r = c.delete(f"{BASE}/{pid}")
    assert r.status_code == 200 and r.json()["activo"] is False
    assert c.get(BASE).json() == []

    c2 = make_client(["CLIENTE"])
    assert c2.delete(f"{BASE}/1").status_code == 403


def test_sin_token_devuelve_401_o_403():
    with TestClient(app) as c:
        assert c.get(BASE).status_code in (401, 403)


def test_obtener_por_sku_devuelve_precio_y_estado(make_client):
    c = make_client(["ADMIN"])
    c.post(BASE, json=PRODUCTO)
    r = c.get(f"{BASE}/sku/P-1")
    assert r.status_code == 200
    assert r.json()["precio"] == 6990 and r.json()["activo"] is True


def test_obtener_por_sku_inexistente_devuelve_404(make_client):
    assert make_client(["CLIENTE"]).get(f"{BASE}/sku/NO-EXISTE").status_code == 404


def test_obtener_por_sku_de_producto_desactivado_informa_activo_false(make_client):
    c = make_client(["ADMIN"])
    pid = c.post(BASE, json=PRODUCTO).json()["id"]
    c.delete(f"{BASE}/{pid}")
    assert c.get(f"{BASE}/sku/P-1").json()["activo"] is False
