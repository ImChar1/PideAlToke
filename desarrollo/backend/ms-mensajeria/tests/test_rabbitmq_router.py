# Pruebas HTTP de /api/rabbitmq. El servicio se reemplaza por un Fake (sin broker) y el JWT se
# simula sobreescribiendo validar_jwt, igual que en los demas microservicios.

import pytest
from fastapi.testclient import TestClient

import app.adapters.api.v1.routers.rabbitmq_router as router_module
from app.core.security import validar_jwt
from app.domain.services.rabbit_admin_service import (
    ConflictoRabbitError,
    RabbitNoDisponibleError,
    RecursoNoEncontradoError,
)
from app.main import app

BASE = "/api/rabbitmq"
ADMIN = {"oid": "admin-1", "roles": ["ADMIN"]}
USUARIO = {"oid": "user-1", "roles": []}


class ServicioFalso:
    def __init__(self):
        self.llamadas = []
        self.error = None

    def _go(self, nombre, resultado, *args, **kwargs):
        self.llamadas.append((nombre, args, kwargs))
        if self.error:
            raise self.error
        return resultado

    def crear_cola(self, datos):
        return self._go("crear_cola", {"name": datos.name, "messages": 0, "consumers": 0}, datos)

    def obtener_cola(self, nombre):
        return self._go("obtener_cola", {"name": nombre, "messages": 2, "consumers": 1}, nombre)

    def eliminar_cola(self, nombre, if_unused=False, if_empty=False):
        return self._go(
            "eliminar_cola", {"name": nombre, "deleted": True, "messages_discarded": 0},
            nombre, if_unused=if_unused, if_empty=if_empty,
        )

    def purgar_cola(self, nombre):
        return self._go("purgar_cola", {"name": nombre, "purged_messages": 4}, nombre)

    def crear_exchange(self, datos):
        return self._go(
            "crear_exchange",
            {"name": datos.name, "type": datos.type, "durable": datos.durable,
             "auto_delete": datos.auto_delete, "internal": datos.internal},
            datos,
        )

    def crear_binding(self, datos):
        return self._go(
            "crear_binding",
            {"queue": datos.queue, "exchange": datos.exchange, "routing_key": datos.routing_key},
            datos,
        )


@pytest.fixture
def entorno():
    servicio = ServicioFalso()
    app.dependency_overrides[router_module.get_service] = lambda: servicio

    def como(claims: dict) -> TestClient:
        app.dependency_overrides[validar_jwt] = lambda: claims
        return TestClient(app, raise_server_exceptions=False)

    yield como, servicio
    app.dependency_overrides.clear()


# ------------------------------------------------------------------ autorizacion

def test_todos_los_endpoints_exigen_rol_admin(entorno):
    como, servicio = entorno
    c = como(USUARIO)
    respuestas = [
        c.post(f"{BASE}/queues", json={"name": "q"}),
        c.get(f"{BASE}/queues/q"),
        c.delete(f"{BASE}/queues/q"),
        c.post(f"{BASE}/queues/q/purge"),
        c.post(f"{BASE}/exchanges", json={"name": "e", "type": "topic"}),
        c.post(f"{BASE}/bindings", json={"queue": "q", "exchange": "e"}),
    ]
    assert [r.status_code for r in respuestas] == [403] * 6
    assert servicio.llamadas == []  # nada llego al servicio


def test_health_no_requiere_autenticacion():
    assert TestClient(app).get("/api/v1/health").status_code == 200


# ------------------------------------------------------------------ casos felices

def test_crear_cola_201(entorno):
    como, servicio = entorno
    r = como(ADMIN).post(f"{BASE}/queues", json={
        "name": "q", "message_ttl_ms": 1000, "dead_letter_exchange": "dlx", "dead_letter_routing_key": "q.dlq",
    })
    assert r.status_code == 201
    assert r.json() == {"name": "q", "messages": 0, "consumers": 0}
    assert servicio.llamadas[0][1][0].dead_letter_routing_key == "q.dlq"


def test_obtener_cola_200(entorno):
    como, _ = entorno
    r = como(ADMIN).get(f"{BASE}/queues/inventario.pedidos")
    assert r.status_code == 200 and r.json()["messages"] == 2


def test_eliminar_cola_pasa_las_guardas_de_la_query(entorno):
    como, servicio = entorno
    r = como(ADMIN).delete(f"{BASE}/queues/q?if_unused=true&if_empty=true")
    assert r.status_code == 200 and r.json()["deleted"] is True
    assert servicio.llamadas[0][2] == {"if_unused": True, "if_empty": True}


def test_eliminar_cola_por_defecto_no_activa_las_guardas(entorno):
    como, servicio = entorno
    como(ADMIN).delete(f"{BASE}/queues/q")
    assert servicio.llamadas[0][2] == {"if_unused": False, "if_empty": False}


def test_purgar_cola_200(entorno):
    como, _ = entorno
    r = como(ADMIN).post(f"{BASE}/queues/q.dlq/purge")
    assert r.status_code == 200 and r.json() == {"name": "q.dlq", "purged_messages": 4}


def test_crear_exchange_y_binding_201(entorno):
    como, _ = entorno
    c = como(ADMIN)
    r1 = c.post(f"{BASE}/exchanges", json={"name": "e", "type": "fanout"})
    r2 = c.post(f"{BASE}/bindings", json={"queue": "q", "exchange": "e", "routing_key": "a.*"})
    assert (r1.status_code, r2.status_code) == (201, 201)
    assert r1.json()["type"] == "fanout" and r2.json()["routing_key"] == "a.*"


# ------------------------------------------------------------------ validacion (422, sin llegar al servicio)

def test_bodies_invalidos_dan_422_y_no_llegan_al_servicio(entorno):
    como, servicio = entorno
    c = como(ADMIN)
    respuestas = [
        c.post(f"{BASE}/queues", json={"name": ""}),
        c.post(f"{BASE}/queues", json={"name": "con espacio"}),
        c.post(f"{BASE}/queues", json={"name": "amq.reservado"}),
        c.post(f"{BASE}/queues", json={"name": "q", "dead_letter_routing_key": "x"}),
        c.post(f"{BASE}/queues", json={"name": "q", "campo_inventado": 1}),
        c.post(f"{BASE}/exchanges", json={"name": "e", "type": "inexistente"}),
        c.post(f"{BASE}/bindings", json={"queue": "", "exchange": "e"}),
    ]
    assert [r.status_code for r in respuestas] == [422] * 7
    assert servicio.llamadas == []


def test_nombre_invalido_en_la_url_da_422(entorno):
    como, servicio = entorno
    assert como(ADMIN).get(f"{BASE}/queues/con%20espacio").status_code == 422
    assert servicio.llamadas == []


# ------------------------------------------------------------------ traduccion de errores

def test_cola_inexistente_404(entorno):
    como, servicio = entorno
    servicio.error = RecursoNoEncontradoError("NOT_FOUND - no queue 'x'")
    assert como(ADMIN).get(f"{BASE}/queues/x").status_code == 404


def test_conflicto_409(entorno):
    como, servicio = entorno
    servicio.error = ConflictoRabbitError("PRECONDITION_FAILED")
    assert como(ADMIN).post(f"{BASE}/queues", json={"name": "q"}).status_code == 409


def test_broker_caido_503(entorno):
    como, servicio = entorno
    servicio.error = RabbitNoDisponibleError("No se pudo comunicar con RabbitMQ")
    assert como(ADMIN).post(f"{BASE}/queues/q/purge").status_code == 503
