from datetime import datetime, timezone

import pytest

from app.domain.services.analitica_service import AnaliticaService
from app.schemas.schema_eventos import EventoMovimientoRecibido, EventoPedidoRecibido
from tests.helpers import movimiento_json, pedido_json

T = "pedidos.eventos"
M = "inventario.movimientos"


def ped(**kw):
    return EventoPedidoRecibido.model_validate_json(pedido_json(**kw))


def mov(**kw):
    return EventoMovimientoRecibido.model_validate_json(movimiento_json(**kw))


@pytest.fixture
def svc():
    return AnaliticaService()


def test_estado_inicial_vacio(svc):
    r = svc.resumen_ventas()
    assert r["pedidos_totales"] == 0 and r["ingresos_confirmados"] == 0 and r["ticket_promedio"] == 0
    assert svc.productos_top() == [] and svc.estado_stock() == [] and svc.alertas_stock() == []


def test_ciclo_creado_confirmado_suma_ingresos(svc):
    svc.registrar_pedido(ped(tipo="creado", pedido_id=1, monto=20000), (T, 0, 0))
    assert svc.resumen_ventas()["pedidos_pendientes"] == 1
    svc.registrar_pedido(ped(tipo="confirmado", pedido_id=1, monto=20000), (T, 0, 1))
    r = svc.resumen_ventas()
    assert (r["pedidos_pendientes"], r["pedidos_confirmados"], r["ingresos_confirmados"]) == (0, 1, 20000.0)
    assert r["ticket_promedio"] == 20000.0


def test_cancelado_no_suma_ingresos(svc):
    svc.registrar_pedido(ped(tipo="creado", pedido_id=2), (T, 0, 0))
    svc.registrar_pedido(ped(tipo="cancelado", pedido_id=2), (T, 0, 1))
    r = svc.resumen_ventas()
    assert r["pedidos_cancelados"] == 1 and r["ingresos_confirmados"] == 0 and r["pedidos_pendientes"] == 0


def test_un_pedido_confirmado_no_cambia_de_estado_despues(svc):
    svc.registrar_pedido(ped(tipo="creado", pedido_id=3), (T, 0, 0))
    svc.registrar_pedido(ped(tipo="confirmado", pedido_id=3), (T, 0, 1))
    svc.registrar_pedido(ped(tipo="cancelado", pedido_id=3), (T, 0, 2))   # transicion invalida
    r = svc.resumen_ventas()
    assert r["pedidos_confirmados"] == 1 and r["pedidos_cancelados"] == 0


def test_es_idempotente_por_offset(svc):
    e = ped(tipo="creado", pedido_id=4)
    assert svc.registrar_pedido(e, (T, 0, 7)) is True
    assert svc.registrar_pedido(e, (T, 0, 7)) is False          # relectura del mismo offset
    assert svc.registrar_pedido(e, (T, 0, 3)) is False          # offset anterior
    assert svc.resumen_ventas()["pedidos_totales"] == 1
    assert svc.registrar_pedido(e, (T, 1, 7)) is True           # otra particion: offsets independientes


def test_reconstruccion_completa_da_el_mismo_resultado(svc):
    eventos = [(ped(tipo="creado", pedido_id=1), 0), (ped(tipo="confirmado", pedido_id=1), 1)]
    for e, off in eventos:
        svc.registrar_pedido(e, (T, 0, off))
    antes = svc.resumen_ventas()
    for e, off in eventos:                                      # el log se relee entero
        svc.registrar_pedido(e, (T, 0, off))
    assert svc.resumen_ventas() == antes


def test_productos_top_ordena_por_unidades(svc):
    def confirmar(pid, off, items):
        svc.registrar_pedido(ped(tipo="confirmado", pedido_id=pid, items=items), (T, 0, off))
    confirmar(1, 0, [{"sku": "A", "cantidad": 1, "precio_unitario": 100}, {"sku": "B", "cantidad": 5, "precio_unitario": 10}])
    confirmar(2, 1, [{"sku": "A", "cantidad": 2, "precio_unitario": 100}])
    top = svc.productos_top(2)
    assert top[0] == {"sku": "B", "unidades_vendidas": 5, "ingresos": 50.0}
    assert top[1] == {"sku": "A", "unidades_vendidas": 3, "ingresos": 300.0}
    assert len(svc.productos_top(1)) == 1


def test_ventas_por_hora_agrupa_por_hora_utc(svc):
    svc.registrar_pedido(ped(tipo="confirmado", pedido_id=1, monto=100, hora=(2026, 11, 4, 15, 5)), (T, 0, 0))
    svc.registrar_pedido(ped(tipo="confirmado", pedido_id=2, monto=50, hora=(2026, 11, 4, 15, 55)), (T, 0, 1))
    svc.registrar_pedido(ped(tipo="confirmado", pedido_id=3, monto=70, hora=(2026, 11, 4, 16, 1)), (T, 0, 2))
    assert svc.ventas_por_hora() == [
        {"hora": "2026-11-04T15:00:00Z", "pedidos": 2, "ingresos": 150.0},
        {"hora": "2026-11-04T16:00:00Z", "pedidos": 1, "ingresos": 70.0},
    ]


def test_stock_guarda_el_ultimo_estado_y_marca_bajo_umbral(svc):
    svc.registrar_movimiento(mov(tipo="reservado", sku="X", disponible=10, umbral=5), (M, 0, 0))
    svc.registrar_movimiento(mov(tipo="confirmado", sku="X", disponible=4, umbral=5), (M, 0, 1))
    (fila,) = svc.estado_stock()
    assert fila["stock_disponible"] == 4 and fila["bajo_umbral"] is True
    assert [f["sku"] for f in svc.estado_stock(solo_bajo_umbral=True)] == ["X"]


def test_alertas_la_mas_reciente_primero_y_con_tope(svc):
    for i in range(60):
        svc.registrar_movimiento(mov(tipo="stock_bajo", sku=f"S{i}", disponible=1), (M, 0, i))
    alertas = svc.alertas_stock()
    assert len(alertas) == 50 and alertas[0]["sku"] == "S59"


def test_metricas_cuentan_consumidos_invalidos_y_fallidos(svc):
    svc.registrar_pedido(ped(), (T, 2, 9))
    svc.registrar_invalido(T)
    svc.registrar_fallido(M)
    m = svc.metricas()
    assert m["mensajes_consumidos"] == {T: 1} and m["mensajes_invalidos"] == {T: 1} and m["mensajes_fallidos"] == {M: 1}
    assert m["ultimo_offset_por_particion"] == {f"{T}-2": 9}


def test_escritura_concurrente_no_pierde_eventos():
    import threading
    svc = AnaliticaService()

    def hilo(particion):
        for off in range(200):
            svc.registrar_pedido(ped(tipo="creado", pedido_id=particion * 1000 + off), (T, particion, off))
    hilos = [threading.Thread(target=hilo, args=(p,)) for p in range(3)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert svc.resumen_ventas()["pedidos_totales"] == 600
