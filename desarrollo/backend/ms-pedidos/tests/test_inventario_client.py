# Pruebas del cliente HTTP hacia ms-inventario (requests.post se reemplaza por un doble).
# Protege el contrato de URL: ms-inventario publica sus rutas bajo /api/v1/inventario.

import pytest
import requests

import app.infrastructure.clients.inventario_client as modulo
from app.domain.ports.inventario_client_port import (
    StockInsuficienteError,
    InventarioNoDisponibleError,
)
from app.infrastructure.clients.inventario_client import InventarioHttpClient


class _Resp:
    def __init__(self, status=200, data=None):
        self.status_code = status
        self._data = data or {}
        self.text = str(self._data)

    def json(self):
        return self._data


@pytest.fixture
def llamadas(monkeypatch):
    registro = []

    def _post(url, json=None, headers=None, timeout=None):
        registro.append({"url": url, "json": json, "headers": headers})
        return _Resp(200, {"sku": "X"})

    monkeypatch.setattr(modulo.requests, "post", _post)
    return registro


def test_reservar_usa_prefijo_api_v1_y_reenvia_el_token(llamadas):
    cliente = InventarioHttpClient(token="abc", base_url="http://ms-inventario:8000/")
    cliente.reservar_stock("PROD-HAMB-001", 2)

    assert llamadas[0]["url"] == "http://ms-inventario:8000/api/v1/inventario/PROD-HAMB-001/reservar"
    assert llamadas[0]["json"] == {"cantidad": 2}
    assert llamadas[0]["headers"]["Authorization"] == "Bearer abc"


def test_envia_la_clave_interna_en_cada_movimiento(llamadas):
    InventarioHttpClient(token="t", base_url="http://x").reservar_stock("S", 1)
    assert llamadas[0]["headers"]["X-Internal-Key"] == "clave-interna-de-test"


def test_confirmar_salida_usa_la_accion_confirmar_salida(llamadas):
    InventarioHttpClient(token="t", base_url="http://x").confirmar_salida("S", 3)
    assert llamadas[0]["url"] == "http://x/api/v1/inventario/S/confirmar-salida"
    assert llamadas[0]["json"] == {"cantidad": 3}


def test_clave_interna_rechazada_se_reporta_como_inventario_no_disponible(monkeypatch):
    monkeypatch.setattr(modulo.requests, "post", lambda *a, **k: _Resp(403, {"detail": "x"}))
    with pytest.raises(InventarioNoDisponibleError, match="INTERNAL_API_KEY"):
        InventarioHttpClient(token="t", base_url="http://x").reservar_stock("S", 1)


def test_liberar_usa_la_accion_liberar(llamadas):
    InventarioHttpClient(token="t", base_url="http://x").liberar_stock("S", 1)
    assert llamadas[0]["url"].endswith("/api/v1/inventario/S/liberar")


def test_sku_con_caracteres_especiales_se_codifica(llamadas):
    InventarioHttpClient(token="t", base_url="http://x").reservar_stock("A/B ?", 1)
    assert "/api/v1/inventario/A%2FB%20%3F/reservar" in llamadas[0]["url"]


@pytest.mark.parametrize("status,error", [
    (409, StockInsuficienteError),
    (404, InventarioNoDisponibleError),
    (500, InventarioNoDisponibleError),
])
def test_codigos_http_se_traducen_a_errores_de_dominio(monkeypatch, status, error):
    monkeypatch.setattr(modulo.requests, "post", lambda *a, **k: _Resp(status, {"detail": "x"}))
    with pytest.raises(error):
        InventarioHttpClient(token="t", base_url="http://x").reservar_stock("S", 1)


def test_error_de_red_se_traduce_a_inventario_no_disponible(monkeypatch):
    def _boom(*a, **k):
        raise requests.ConnectionError("sin red")

    monkeypatch.setattr(modulo.requests, "post", _boom)
    with pytest.raises(InventarioNoDisponibleError):
        InventarioHttpClient(token="t", base_url="http://x").reservar_stock("S", 1)
