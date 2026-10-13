# Handler de eventos de pedido: valida el contrato y marca como irrecuperable lo malformado.

import json
from types import SimpleNamespace

import pytest

from app.adapters.messaging.pedido_eventos_handler import manejar_evento_pedido
from app.infrastructure.messaging.rabbitmq_consumer import NonRetryableError

METODO = SimpleNamespace(routing_key="pedido.creado")


def _evento(**cambios):
    base = {
        "event_id": "e-1", "tipo": "creado", "pedido_id": 5, "cliente_id": "c1",
        "estado": "PENDIENTE", "monto_total": 10.0, "ocurrido_en": "2026-10-09T00:00:00Z",
        "items": [{"sku": "A", "cantidad": 2, "precio_unitario": 5.0}],
    }
    return json.dumps({**base, **cambios}).encode()


def test_evento_valido_se_procesa_y_se_registra(caplog):
    with caplog.at_level("INFO"):
        manejar_evento_pedido(_evento(), SimpleNamespace(), METODO)
    assert any("pedido_id=5" in r.getMessage() for r in caplog.records)


def test_ignora_campos_nuevos_del_productor():
    manejar_evento_pedido(_evento(campo_futuro="x"), SimpleNamespace(), METODO)


def test_json_invalido_es_irrecuperable():
    with pytest.raises(NonRetryableError):
        manejar_evento_pedido(b"esto no es json", SimpleNamespace(), METODO)


def test_evento_sin_campos_obligatorios_es_irrecuperable():
    cuerpo = json.dumps({"event_id": "e-1"}).encode()
    with pytest.raises(NonRetryableError):
        manejar_evento_pedido(cuerpo, SimpleNamespace(), METODO)


def test_tipo_desconocido_es_irrecuperable():
    with pytest.raises(NonRetryableError):
        manejar_evento_pedido(_evento(tipo="otro"), SimpleNamespace(), METODO)
