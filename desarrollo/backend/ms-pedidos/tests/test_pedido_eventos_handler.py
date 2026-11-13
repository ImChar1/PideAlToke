# Handler de seguimiento de pedidos: valida el contrato, descarta duplicados y marca lo malformado como irrecuperable.

import json
from types import SimpleNamespace

import pytest

from app.adapters.messaging import pedido_eventos_handler as h
from app.infrastructure.messaging.rabbitmq_consumer import NonRetryableError

METODO = SimpleNamespace(routing_key="pedido.creado")


def _evento(**cambios):
    base = {
        "event_id": "e-1", "tipo": "creado", "pedido_id": 5, "cliente_id": "c1",
        "estado": "PENDIENTE", "monto_total": 10.0, "ocurrido_en": "2026-10-09T00:00:00Z",
        "items": [{"sku": "A", "cantidad": 2, "precio_unitario": 5.0}],
    }
    return json.dumps({**base, **cambios}).encode()


@pytest.fixture(autouse=True)
def _limpiar_vistos():
    h._vistos.clear()
    yield
    h._vistos.clear()


def test_evento_valido_se_registra(caplog):
    with caplog.at_level("INFO"):
        h.manejar_evento_pedido(_evento(), SimpleNamespace(), METODO)
    assert any("pedido_id=5" in r.getMessage() for r in caplog.records)


def test_evento_duplicado_se_ignora(caplog):
    h.manejar_evento_pedido(_evento(), SimpleNamespace(), METODO)
    with caplog.at_level("INFO"):
        h.manejar_evento_pedido(_evento(), SimpleNamespace(), METODO)
    assert any("duplicado" in r.getMessage() for r in caplog.records)


def test_json_invalido_es_irrecuperable():
    with pytest.raises(NonRetryableError):
        h.manejar_evento_pedido(b"esto no es json", SimpleNamespace(), METODO)


def test_evento_sin_campos_obligatorios_es_irrecuperable():
    with pytest.raises(NonRetryableError):
        h.manejar_evento_pedido(json.dumps({"event_id": "e-1"}).encode(), SimpleNamespace(), METODO)


def test_memoria_de_eventos_esta_acotada(monkeypatch):
    monkeypatch.setattr(h, "_MAX_EVENTOS_RECORDADOS", 3)
    for i in range(5):
        h.manejar_evento_pedido(_evento(event_id=f"e-{i}"), SimpleNamespace(), METODO)
    assert len(h._vistos) == 3
