# Pruebas HTTP de /users/me. Usa la sqlite temporal definida en conftest.py
# y simula el JWT sobreescribiendo get_current_user_claims.

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import get_current_user_claims

URL = "/api/v1/users/me"


@pytest.fixture
def client_con_claims():
    def _make(claims):
        app.dependency_overrides[get_current_user_claims] = lambda: claims
        return TestClient(app)

    yield _make
    app.dependency_overrides.clear()


def _oid():
    return f"oid-{uuid.uuid4()}"


def test_me_crea_el_usuario_como_cliente_por_defecto(client_con_claims):
    oid = _oid()
    c = client_con_claims({"oid": oid, "preferred_username": f"{oid}@example.com"})
    r = c.get(URL)
    assert r.status_code == 200
    assert r.json()["azure_oid"] == oid and r.json()["rol"] == "CLIENTE"


def test_me_asigna_admin_si_el_token_trae_el_app_role(client_con_claims):
    oid = _oid()
    c = client_con_claims({"oid": oid, "preferred_username": f"{oid}@example.com", "roles": ["ADMIN"]})
    assert c.get(URL).json()["rol"] == "ADMIN"


def test_me_sincroniza_el_rol_en_llamadas_posteriores(client_con_claims):
    oid = _oid()
    email = f"{oid}@example.com"
    assert client_con_claims({"oid": oid, "email": email}).get(URL).json()["rol"] == "CLIENTE"
    assert client_con_claims({"oid": oid, "email": email, "roles": ["ADMIN"]}).get(URL).json()["rol"] == "ADMIN"


def test_me_usa_sub_si_no_hay_oid(client_con_claims):
    sub = _oid()
    r = client_con_claims({"sub": sub, "email": f"{sub}@example.com"}).get(URL)
    assert r.json()["azure_oid"] == sub


def test_me_sin_oid_ni_sub_devuelve_400(client_con_claims):
    assert client_con_claims({"email": "x@example.com"}).get(URL).status_code == 400


def test_me_sin_token_devuelve_401_o_403():
    with TestClient(app) as c:
        assert c.get(URL).status_code in (401, 403)
