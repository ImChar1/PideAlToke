import pytest
from fastapi.testclient import TestClient

import app.adapters.api.v1.routers.analitica_router as router_module
from app.adapters.messaging.eventos_handlers import crear_handler_movimientos, crear_handler_pedidos
from app.core.security import validar_jwt
from app.domain.services.analitica_service import AnaliticaService
from app.infrastructure.kafka.kafka_consumer import MensajeKafka, NonRetryableError
from app.main import app
from tests.helpers import movimiento_json, pedido_json

ADMIN = {"oid": "a", "roles": ["ADMIN"]}
USUARIO = {"oid": "u", "roles": []}


def m(valor, topico="pedidos.eventos", particion=0, offset=0):
    return MensajeKafka(topico, particion, offset, b"1", valor)


# ------------------------------------------------------------ handlers

def test_handler_de_pedidos_valida_y_aplica():
    svc = AnaliticaService()
    crear_handler_pedidos(svc)(m(pedido_json(tipo="creado", pedido_id=9)))
    assert svc.resumen_ventas()["pedidos_pendientes"] == 1


def test_handler_tolera_campos_nuevos_del_productor():
    svc = AnaliticaService()
    crear_handler_pedidos(svc)(m(pedido_json()))          # trae "campo_futuro"
    assert svc.resumen_ventas()["pedidos_totales"] == 1


@pytest.mark.parametrize("basura", [b"no es json", b"{}", b'{"tipo": "inventado"}', b""])
def test_handler_de_pedidos_rechaza_payloads_invalidos(basura):
    with pytest.raises(NonRetryableError):
        crear_handler_pedidos(AnaliticaService())(m(basura))


def test_handler_rechaza_montos_o_cantidades_invalidas():
    malo = pedido_json(items=[{"sku": "A", "cantidad": 0, "precio_unitario": 1}])
    with pytest.raises(NonRetryableError):
        crear_handler_pedidos(AnaliticaService())(m(malo))


def test_handler_de_movimientos():
    svc = AnaliticaService()
    crear_handler_movimientos(svc)(m(movimiento_json(tipo="stock_bajo", sku="Z", disponible=2), "inventario.movimientos"))
    assert svc.alertas_stock()[0]["sku"] == "Z"
    with pytest.raises(NonRetryableError):
        crear_handler_movimientos(svc)(m(b'{"tipo":"reservado"}', "inventario.movimientos"))


def test_relectura_del_mismo_offset_no_duplica():
    svc = AnaliticaService()
    h = crear_handler_pedidos(svc)
    h(m(pedido_json(), offset=4))
    h(m(pedido_json(), offset=4))
    assert svc.resumen_ventas()["pedidos_totales"] == 1


# ------------------------------------------------------------ router

@pytest.fixture
def svc():
    s = AnaliticaService()
    h = crear_handler_pedidos(s)
    h(m(pedido_json(tipo="creado", pedido_id=1, monto=20000), offset=0))
    h(m(pedido_json(tipo="confirmado", pedido_id=1, monto=20000), offset=1))
    crear_handler_movimientos(s)(m(movimiento_json(tipo="stock_bajo", sku="SKU-1", disponible=3), "inventario.movimientos"))
    return s


@pytest.fixture
def client(svc):
    app.dependency_overrides[router_module.get_service] = lambda: svc
    app.dependency_overrides[validar_jwt] = lambda: ADMIN
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_endpoints_de_lectura(client):
    assert client.get("/api/v1/analitica/ventas/resumen").json()["ingresos_confirmados"] == 20000.0
    assert client.get("/api/v1/analitica/ventas/por-hora").json()[0]["pedidos"] == 1
    assert client.get("/api/v1/analitica/productos/top?limite=1").json()[0]["sku"] == "SKU-1"
    assert client.get("/api/v1/analitica/stock/estado?bajo_umbral=true").json()[0]["bajo_umbral"] is True
    assert client.get("/api/v1/analitica/stock/alertas").json()[0]["sku"] == "SKU-1"
    metricas = client.get("/api/v1/analitica/metricas").json()
    assert metricas["mensajes_consumidos"]["pedidos.eventos"] == 2


def test_limite_invalido_es_422(client):
    assert client.get("/api/v1/analitica/productos/top?limite=0").status_code == 422
    assert client.get("/api/v1/analitica/productos/top?limite=999").status_code == 422


def test_sin_rol_admin_es_403(client):
    app.dependency_overrides[validar_jwt] = lambda: USUARIO
    for ruta in ("ventas/resumen", "ventas/por-hora", "productos/top", "stock/estado", "stock/alertas", "metricas"):
        assert client.get(f"/api/v1/analitica/{ruta}").status_code == 403, ruta


def test_sin_token_no_pasa():
    app.dependency_overrides.clear()
    assert TestClient(app).get("/api/v1/analitica/ventas/resumen").status_code in (401, 403)


def test_health():
    assert TestClient(app).get("/api/v1/health").json()["status"] == "ok"
