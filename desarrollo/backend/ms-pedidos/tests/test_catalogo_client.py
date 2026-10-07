# Pruebas del cliente HTTP hacia ms-catalogo (requests.get se reemplaza por un doble).

import pytest
import requests

import app.infrastructure.clients.catalogo_client as modulo
from app.domain.ports.catalogo_client_port import ProductoNoDisponibleError, CatalogoNoDisponibleError
from app.infrastructure.clients.catalogo_client import CatalogoHttpClient


class _Resp:
    def __init__(self, status=200, data=None):
        self.status_code = status
        self._data = data or {}
        self.text = str(self._data)

    def json(self):
        return self._data


def _cliente():
    return CatalogoHttpClient(token="abc", base_url="http://ms-catalogo:8000/")


def test_consulta_por_sku_con_prefijo_api_v1_y_token(monkeypatch):
    visto = {}

    def _get(url, headers=None, timeout=None):
        visto.update(url=url, headers=headers)
        return _Resp(200, {"sku": "P-1", "precio": 6990, "activo": True})

    monkeypatch.setattr(modulo.requests, "get", _get)
    producto = _cliente().obtener_producto_por_sku("P-1")

    assert visto["url"] == "http://ms-catalogo:8000/api/v1/productos/sku/P-1"
    assert visto["headers"]["Authorization"] == "Bearer abc"
    assert producto["precio"] == 6990


def test_sku_con_caracteres_especiales_se_codifica(monkeypatch):
    visto = {}
    monkeypatch.setattr(modulo.requests, "get",
                        lambda url, **k: visto.update(url=url) or _Resp(200, {"precio": 1, "activo": True}))
    _cliente().obtener_producto_por_sku("A/B ?")
    assert visto["url"].endswith("/api/v1/productos/sku/A%2FB%20%3F")


def test_404_se_traduce_a_producto_no_disponible(monkeypatch):
    monkeypatch.setattr(modulo.requests, "get", lambda *a, **k: _Resp(404, {"detail": "no"}))
    with pytest.raises(ProductoNoDisponibleError):
        _cliente().obtener_producto_por_sku("X")


def test_producto_inactivo_se_traduce_a_producto_no_disponible(monkeypatch):
    monkeypatch.setattr(modulo.requests, "get",
                        lambda *a, **k: _Resp(200, {"sku": "X", "precio": 1, "activo": False}))
    with pytest.raises(ProductoNoDisponibleError):
        _cliente().obtener_producto_por_sku("X")


@pytest.mark.parametrize("status", [401, 403, 500, 503])
def test_otros_errores_http_se_traducen_a_catalogo_no_disponible(monkeypatch, status):
    monkeypatch.setattr(modulo.requests, "get", lambda *a, **k: _Resp(status, {"detail": "x"}))
    with pytest.raises(CatalogoNoDisponibleError):
        _cliente().obtener_producto_por_sku("X")


def test_error_de_red_se_traduce_a_catalogo_no_disponible(monkeypatch):
    def _boom(*a, **k):
        raise requests.ConnectionError("sin red")

    monkeypatch.setattr(modulo.requests, "get", _boom)
    with pytest.raises(CatalogoNoDisponibleError):
        _cliente().obtener_producto_por_sku("X")
