# Pruebas unitarias del PedidoService: valida la integracion logica con Inventario
# (reserva de stock, compensacion si falla a mitad de camino) sin red ni base de datos real.

import pytest

from app.domain.services.pedido_service import PedidoService
from app.domain.ports.inventario_client_port import StockInsuficienteError, InventarioNoDisponibleError
from app.schemas.schema_pedido import CrearPedidoSchema
from tests.fakes import FakePedidoRepository, FakeInventarioClient


def _pedido_de_ejemplo(items):
    return CrearPedidoSchema(cliente_id="cliente-1", items=items)


def test_crear_pedido_reserva_stock_y_calcula_monto_total():
    inventario = FakeInventarioClient(stock={"COMBO-001": 10, "BEB-001": 5})
    service = PedidoService(FakePedidoRepository(), inventario)

    pedido = service.crear_nuevo_pedido(_pedido_de_ejemplo([
        {"sku": "COMBO-001", "cantidad": 2, "precio_unitario": 2500},
        {"sku": "BEB-001", "cantidad": 1, "precio_unitario": 1000},
    ]))

    assert pedido.monto_total == 6000
    assert pedido.estado == "PENDIENTE"
    assert inventario.reservas == {"COMBO-001": 2, "BEB-001": 1}


def test_crear_pedido_persiste_los_items():
    inventario = FakeInventarioClient(stock={"COMBO-001": 10})
    service = PedidoService(FakePedidoRepository(), inventario)

    pedido = service.crear_nuevo_pedido(_pedido_de_ejemplo([
        {"sku": "COMBO-001", "cantidad": 3, "precio_unitario": 2500},
    ]))

    assert pedido.items == [{"sku": "COMBO-001", "cantidad": 3, "precio_unitario": 2500.0}]


def test_stock_insuficiente_no_crea_el_pedido_y_libera_lo_reservado():
    # COMBO-001 alcanza a reservarse, pero BEB-001 no tiene stock suficiente.
    # El pedido NO debe crearse, y la reserva de COMBO-001 debe liberarse (compensacion).
    inventario = FakeInventarioClient(stock={"COMBO-001": 10, "BEB-001": 0})
    repository = FakePedidoRepository()
    service = PedidoService(repository, inventario)

    with pytest.raises(StockInsuficienteError):
        service.crear_nuevo_pedido(_pedido_de_ejemplo([
            {"sku": "COMBO-001", "cantidad": 2, "precio_unitario": 2500},
            {"sku": "BEB-001", "cantidad": 1, "precio_unitario": 1000},
        ]))

    assert repository._data == {}  # no se persistio ningun pedido
    assert inventario.liberaciones.get("COMBO-001") == 2  # se libero la reserva parcial


def test_sku_inexistente_en_inventario_lanza_error_y_no_crea_pedido():
    inventario = FakeInventarioClient(stock={"COMBO-001": 10}, sku_inexistente="NO-EXISTE")
    repository = FakePedidoRepository()
    service = PedidoService(repository, inventario)

    with pytest.raises(InventarioNoDisponibleError):
        service.crear_nuevo_pedido(_pedido_de_ejemplo([
            {"sku": "NO-EXISTE", "cantidad": 1, "precio_unitario": 1000},
        ]))

    assert repository._data == {}
