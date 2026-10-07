# Pruebas HTTP de /api/v1/pedidos. Usa la SQLite temporal de conftest.py (repositorio real);
# Inventario y Catalogo se reemplazan por fakes y el JWT se simula sobreescribiendo validar_jwt.

import uuid

import pytest
from fastapi.testclient import TestClient

import app.adapters.api.v1.routers.pedidos_router as router_module
from app.main import app
from app.core.security import validar_jwt, obtener_token_bearer
from tests.fakes import FakeInventarioClient, FakeCatalogoClient

BASE = "/api/v1/pedidos"
PRECIOS = {"PROD-1": 2500, "PROD-2": 1000, "PROD-OFF": 500}


def _uid(prefijo="user"):
    return f"{prefijo}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def entorno(monkeypatch):
    inventario = FakeInventarioClient(stock={"PROD-1": 100, "PROD-2": 0, "PROD-OFF": 10})
    catalogo = FakeCatalogoClient(precios=PRECIOS, inactivos={"PROD-OFF"})
    monkeypatch.setattr(router_module, "InventarioHttpClient", lambda token, **kw: inventario)
    monkeypatch.setattr(router_module, "CatalogoHttpClient", lambda token, **kw: catalogo)
    app.dependency_overrides[obtener_token_bearer] = lambda: "token-falso"

    def como(claims: dict) -> TestClient:
        app.dependency_overrides[validar_jwt] = lambda: claims
        return TestClient(app, raise_server_exceptions=False)

    yield como, inventario, catalogo
    app.dependency_overrides.clear()


def _crear(c, items=None, **extra):
    return c.post(BASE, json={"items": items or [{"sku": "PROD-1", "cantidad": 2}], **extra})


# ------------------------------------------------------------------ crear

def test_crear_pedido_usa_precio_del_catalogo_y_cliente_del_jwt(entorno):
    como, inventario, _ = entorno
    oid = _uid()
    c = como({"oid": oid, "roles": []})

    # El cliente intenta colarse: precio 1 y a nombre de otro usuario.
    r = c.post(BASE, json={
        "cliente_id": "victima",
        "items": [{"sku": "PROD-1", "cantidad": 2, "precio_unitario": 1}],
    })

    assert r.status_code == 201
    body = r.json()
    assert body["cliente_id"] == oid                      # sale del JWT
    assert body["monto_total"] == 5000                    # 2 * 2500 del catalogo
    assert body["items"][0]["precio_unitario"] == 2500
    assert body["estado"] == "PENDIENTE"
    assert inventario.reservas == {"PROD-1": 2}


def test_crear_pedido_usa_sub_si_el_token_no_trae_oid(entorno):
    como, *_ = entorno
    sub = _uid()
    assert _crear(como({"sub": sub})).json()["cliente_id"] == sub


def test_crear_pedido_sin_identificador_en_el_token_devuelve_401(entorno):
    como, *_ = entorno
    assert _crear(como({"roles": []})).status_code == 401


def test_crear_acepta_ruta_con_y_sin_barra_final_sin_redirect(entorno):
    como, *_ = entorno
    c = como({"oid": _uid()})
    for url in (BASE, BASE + "/"):
        r = c.post(url, json={"items": [{"sku": "PROD-1", "cantidad": 1}]}, follow_redirects=False)
        assert r.status_code == 201, url


def test_stock_insuficiente_devuelve_409(entorno):
    como, *_ = entorno
    r = _crear(como({"oid": _uid()}), items=[{"sku": "PROD-2", "cantidad": 1}])
    assert r.status_code == 409


def test_producto_inexistente_o_inactivo_devuelve_422(entorno):
    como, *_ = entorno
    c = como({"oid": _uid()})
    assert _crear(c, items=[{"sku": "NO-EXISTE", "cantidad": 1}]).status_code == 422
    assert _crear(c, items=[{"sku": "PROD-OFF", "cantidad": 1}]).status_code == 422


def test_catalogo_caido_devuelve_503(entorno):
    como, _, catalogo = entorno
    catalogo.caido = True
    assert _crear(como({"oid": _uid()})).status_code == 503


def test_un_error_inesperado_es_500_y_no_un_400_enganoso(entorno):
    como, inventario, _ = entorno
    inventario.error_inesperado_al_reservar = RuntimeError("bug interno")
    assert _crear(como({"oid": _uid()})).status_code == 500


def test_cantidad_invalida_o_items_vacios_devuelven_422(entorno):
    como, *_ = entorno
    c = como({"oid": _uid()})
    assert _crear(c, items=[{"sku": "PROD-1", "cantidad": 0}]).status_code == 422
    assert c.post(BASE, json={"items": []}).status_code == 422


def test_sin_token_devuelve_401_o_403():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        assert c.post(BASE, json={"items": [{"sku": "PROD-1", "cantidad": 1}]}).status_code in (401, 403)
        assert c.get(BASE).status_code in (401, 403)


# ------------------------------------------------------------------ leer

def test_obtener_pedido_propio_ok_y_ajeno_404(entorno):
    como, *_ = entorno
    dueno, intruso = _uid(), _uid()
    pid = _crear(como({"oid": dueno})).json()["id"]

    assert como({"oid": dueno}).get(f"{BASE}/{pid}").status_code == 200
    assert como({"oid": intruso}).get(f"{BASE}/{pid}").status_code == 404


def test_admin_puede_obtener_pedidos_ajenos(entorno):
    como, *_ = entorno
    pid = _crear(como({"oid": _uid()})).json()["id"]
    assert como({"oid": _uid("admin"), "roles": ["ADMIN"]}).get(f"{BASE}/{pid}").status_code == 200


def test_listar_devuelve_solo_mis_pedidos(entorno):
    como, *_ = entorno
    yo, otro = _uid(), _uid()
    _crear(como({"oid": yo})); _crear(como({"oid": yo})); _crear(como({"oid": otro}))

    for url in (BASE, BASE + "/"):
        r = como({"oid": yo}).get(url, follow_redirects=False)
        assert r.status_code == 200 and len(r.json()) == 2
        assert {p["cliente_id"] for p in r.json()} == {yo}


def test_listar_todos_requiere_admin(entorno):
    como, *_ = entorno
    otro = _uid()
    _crear(como({"oid": otro}))

    assert como({"oid": _uid()}).get(BASE, params={"todos": "true"}).status_code == 403
    r = como({"oid": _uid("admin"), "roles": ["ADMIN"]}).get(BASE, params={"todos": "true"})
    assert r.status_code == 200 and otro in {p["cliente_id"] for p in r.json()}


# ------------------------------------------------- cerrar el ciclo de stock

def test_cancelar_pedido_propio_libera_stock(entorno):
    como, inventario, _ = entorno
    oid = _uid()
    c = como({"oid": oid})
    pid = _crear(c).json()["id"]

    r = c.post(f"{BASE}/{pid}/cancelar")

    assert r.status_code == 200 and r.json()["estado"] == "CANCELADO"
    assert inventario.liberaciones == {"PROD-1": 2}
    assert c.post(f"{BASE}/{pid}/cancelar").status_code == 200       # idempotente
    assert inventario.liberaciones == {"PROD-1": 2}


def test_no_se_puede_cancelar_un_pedido_ajeno(entorno):
    como, inventario, _ = entorno
    pid = _crear(como({"oid": _uid()})).json()["id"]
    assert como({"oid": _uid()}).post(f"{BASE}/{pid}/cancelar").status_code == 404
    assert inventario.liberaciones == {}


def test_confirmar_requiere_rol_admin(entorno):
    como, inventario, _ = entorno
    pid = _crear(como({"oid": _uid()})).json()["id"]

    assert como({"oid": _uid(), "roles": ["CLIENTE"]}).post(f"{BASE}/{pid}/confirmar").status_code == 403
    r = como({"oid": _uid("admin"), "roles": ["ADMIN"]}).post(f"{BASE}/{pid}/confirmar")
    assert r.status_code == 200 and r.json()["estado"] == "CONFIRMADO"
    assert inventario.confirmaciones == {"PROD-1": 2}


def test_cancelar_un_pedido_confirmado_devuelve_409(entorno):
    como, *_ = entorno
    oid = _uid()
    pid = _crear(como({"oid": oid})).json()["id"]
    como({"oid": _uid("admin"), "roles": ["ADMIN"]}).post(f"{BASE}/{pid}/confirmar")
    assert como({"oid": oid}).post(f"{BASE}/{pid}/cancelar").status_code == 409

