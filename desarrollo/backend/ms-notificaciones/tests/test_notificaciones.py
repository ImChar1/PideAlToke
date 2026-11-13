import json

import pytest
from fastapi.testclient import TestClient

import app.adapters.api.v1.routers.notificaciones_router as router_module
from app.adapters.messaging.eventos_handlers import manejar_alerta_stock, manejar_notificacion_pedido
from app.core.security import validar_jwt
from app.domain.services.notificacion_service import MAX_NOTIFICACIONES, NotificacionService
from app.infrastructure.messaging.rabbitmq_consumer import NonRetryableError
from app.main import app
from types import SimpleNamespace as NS

ADMIN = {"oid": "a", "roles": ["ADMIN"]}
METODO = NS(routing_key="pedido.confirmado", delivery_tag=1)


def pedido(tipo="confirmado", pedido_id=12, event_id=None, monto=15990.0):
    return json.dumps({"event_id": event_id or f"p-{tipo}-{pedido_id}", "tipo": tipo, "pedido_id": pedido_id,
                       "cliente_id": "c", "estado": tipo.upper(), "monto_total": monto, "items": [], "extra": 1}).encode()


def alerta(sku="SKU-1", event_id=None, disponible=4, umbral=5):
    return json.dumps({"event_id": event_id or f"a-{sku}-{disponible}", "tipo": "stock_bajo", "sku": sku,
                       "stock_disponible": disponible, "umbral_minimo": umbral}).encode()


@pytest.fixture
def svc():
    return NotificacionService()


# ------------------------------------------------------------ handlers (dominio: pedidos)

def test_pedido_confirmado_genera_notificacion(svc):
    manejar_notificacion_pedido(pedido("confirmado"), None, METODO, service=svc)
    (n,) = svc.listar()
    assert n["tipo"] == "pedido_confirmado" and n["referencia"] == "pedido:12" and "15,990" in n["mensaje"]


def test_pedido_cancelado_genera_notificacion(svc):
    manejar_notificacion_pedido(pedido("cancelado"), None, METODO, service=svc)
    assert svc.listar()[0]["tipo"] == "pedido_cancelado"


def test_pedido_creado_no_notifica(svc):
    manejar_notificacion_pedido(pedido("creado"), None, METODO, service=svc)
    assert svc.listar() == []


def test_mensaje_repetido_se_ignora_por_event_id(svc):
    for _ in range(3):
        manejar_notificacion_pedido(pedido("confirmado", event_id="mismo"), None, METODO, service=svc)
    assert len(svc.listar()) == 1 and svc.resumen()["duplicados_ignorados"] == 2


@pytest.mark.parametrize("basura", [b"no es json", b"{}", b'{"tipo":"inventado"}', b"",
                                    json.dumps({"event_id": "x", "tipo": "confirmado", "pedido_id": 1, "cliente_id": "c",
                                                "estado": "X", "monto_total": -5}).encode()])
def test_payload_invalido_va_directo_a_la_dlq(svc, basura):
    with pytest.raises(NonRetryableError):
        manejar_notificacion_pedido(basura, None, METODO, service=svc)


# ------------------------------------------------------------ handlers (dominio: alertas de stock)

def test_alerta_de_stock_bajo(svc):
    manejar_alerta_stock(alerta("SKU-9", disponible=3, umbral=5), None, METODO, service=svc)
    (n,) = svc.listar()
    assert n["tipo"] == "stock_bajo" and "SKU-9" in n["titulo"] and "3 unidades" in n["mensaje"] and "umbral 5" in n["mensaje"]


def test_alerta_sin_umbral(svc):
    manejar_alerta_stock(alerta(umbral=None), None, METODO, service=svc)
    assert "umbral" not in svc.listar()[0]["mensaje"]


def test_alerta_invalida_o_de_otro_tipo_va_a_la_dlq(svc):
    with pytest.raises(NonRetryableError):
        manejar_alerta_stock(b'{"event_id":"x","tipo":"reservado","sku":"A","stock_disponible":1}', None, METODO, service=svc)
    with pytest.raises(NonRetryableError):
        manejar_alerta_stock(b"basura", None, METODO, service=svc)


# ------------------------------------------------------------ servicio

def test_listar_filtra_por_tipo_y_ordena_reciente_primero(svc):
    manejar_notificacion_pedido(pedido("confirmado", 1), None, METODO, service=svc)
    manejar_alerta_stock(alerta("A"), None, METODO, service=svc)
    manejar_notificacion_pedido(pedido("cancelado", 2), None, METODO, service=svc)
    assert [n["tipo"] for n in svc.listar()] == ["pedido_cancelado", "stock_bajo", "pedido_confirmado"]
    assert [n["tipo"] for n in svc.listar(tipo="stock_bajo")] == ["stock_bajo"]
    assert len(svc.listar(limite=2)) == 2
    assert svc.resumen()["por_tipo"] == {"pedido_confirmado": 1, "stock_bajo": 1, "pedido_cancelado": 1}


def test_guarda_solo_las_ultimas_n(svc):
    for i in range(MAX_NOTIFICACIONES + 20):
        manejar_notificacion_pedido(pedido("confirmado", i), None, METODO, service=svc)
    assert len(svc.listar(limite=200)) == MAX_NOTIFICACIONES
    assert svc.listar()[0]["referencia"] == f"pedido:{MAX_NOTIFICACIONES + 19}"


# ------------------------------------------------------------ router

@pytest.fixture
def client(svc):
    manejar_notificacion_pedido(pedido("confirmado"), None, METODO, service=svc)
    manejar_alerta_stock(alerta(), None, METODO, service=svc)
    app.dependency_overrides[router_module.get_service] = lambda: svc
    app.dependency_overrides[validar_jwt] = lambda: ADMIN
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_listar_y_filtrar(client):
    assert len(client.get("/api/v1/notificaciones/").json()) == 2
    assert [n["tipo"] for n in client.get("/api/v1/notificaciones?tipo=stock_bajo").json()] == ["stock_bajo"]
    assert client.get("/api/v1/notificaciones/resumen").json()["total"] == 2


def test_parametros_invalidos_son_422(client):
    assert client.get("/api/v1/notificaciones?tipo=otro").status_code == 422
    assert client.get("/api/v1/notificaciones?limite=0").status_code == 422


def test_sin_rol_admin_es_403(client):
    app.dependency_overrides[validar_jwt] = lambda: {"oid": "u", "roles": []}
    assert client.get("/api/v1/notificaciones/").status_code == 403
    assert client.get("/api/v1/notificaciones/resumen").status_code == 403


def test_sin_token_no_pasa():
    app.dependency_overrides.clear()
    assert TestClient(app).get("/api/v1/notificaciones/").status_code in (401, 403)


def test_health():
    assert TestClient(app).get("/api/v1/health").json()["status"] == "ok"
