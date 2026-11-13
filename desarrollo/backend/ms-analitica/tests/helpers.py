import json
from datetime import datetime, timezone


def pedido_json(tipo="creado", pedido_id=1, monto=10000.0, items=None, hora=(2026, 11, 4, 15, 30)):
    return json.dumps({
        "event_id": f"e-{tipo}-{pedido_id}",
        "tipo": tipo,
        "ocurrido_en": datetime(*hora, tzinfo=timezone.utc).isoformat(),
        "pedido_id": pedido_id,
        "cliente_id": "cli-1",
        "estado": tipo.upper(),
        "monto_total": monto,
        "items": items if items is not None else [{"sku": "SKU-1", "cantidad": 2, "precio_unitario": monto / 2}],
        "campo_futuro": "ignorado",   # el consumidor tolera campos nuevos del productor
    }).encode()


def movimiento_json(tipo="reservado", sku="SKU-1", disponible=10, reservado=0, umbral=5):
    return json.dumps({
        "event_id": f"m-{tipo}-{sku}",
        "tipo": tipo,
        "ocurrido_en": datetime(2026, 11, 4, 15, 31, tzinfo=timezone.utc).isoformat(),
        "sku": sku,
        "cantidad": 0 if tipo == "stock_bajo" else 2,
        "stock_disponible": disponible,
        "stock_reservado": reservado,
        "stock_vendible": disponible - reservado,
        "umbral_minimo": umbral,
        "pedido_id": None,
    }).encode()
