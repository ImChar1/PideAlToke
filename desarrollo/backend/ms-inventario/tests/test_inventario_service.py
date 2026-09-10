# Pruebas unitarias del InventarioService, usando el repositorio en memoria (fake).

import pytest

from app.domain.services.inventario_service import (
    InventarioService,
    InventarioNoEncontradoError,
    SkuDuplicadoError,
    StockInsuficienteError,
    CantidadInvalidaError,
)
from tests.fake_repository import FakeInventarioRepository


@pytest.fixture
def service():
    return InventarioService(FakeInventarioRepository())


def test_crear_inventario_ok(service):
    registro = service.crear_inventario({"sku": "COMBO-001", "cantidad_disponible": 10})
    assert registro.cantidad_disponible == 10
    assert registro.cantidad_reservada == 0


def test_crear_inventario_sku_duplicado_lanza_error(service):
    service.crear_inventario({"sku": "COMBO-001", "cantidad_disponible": 10})
    with pytest.raises(SkuDuplicadoError):
        service.crear_inventario({"sku": "COMBO-001", "cantidad_disponible": 5})


def test_obtener_inventario_inexistente_lanza_error(service):
    with pytest.raises(InventarioNoEncontradoError):
        service.obtener_inventario("NO-EXISTE")


def test_reservar_stock_descuenta_del_vendible_no_del_disponible(service):
    service.crear_inventario({"sku": "COMBO-001", "cantidad_disponible": 10})
    registro = service.reservar_stock("COMBO-001", 3)

    assert registro.cantidad_disponible == 10  # no cambia
    assert registro.cantidad_reservada == 3
    # stock vendible = 10 - 3 = 7


def test_reservar_mas_stock_del_vendible_lanza_error(service):
    service.crear_inventario({"sku": "COMBO-001", "cantidad_disponible": 5})
    service.reservar_stock("COMBO-001", 5)  # se agota el vendible

    with pytest.raises(StockInsuficienteError):
        service.reservar_stock("COMBO-001", 1)


def test_liberar_stock_revierte_la_reserva(service):
    service.crear_inventario({"sku": "COMBO-001", "cantidad_disponible": 10})
    service.reservar_stock("COMBO-001", 4)

    registro = service.liberar_stock("COMBO-001", 4)
    assert registro.cantidad_reservada == 0
    assert registro.cantidad_disponible == 10


def test_confirmar_salida_descuenta_disponible_y_reservada(service):
    service.crear_inventario({"sku": "COMBO-001", "cantidad_disponible": 10})
    service.reservar_stock("COMBO-001", 4)

    registro = service.confirmar_salida("COMBO-001", 4)
    assert registro.cantidad_disponible == 6
    assert registro.cantidad_reservada == 0


def test_confirmar_salida_mayor_a_lo_reservado_lanza_error(service):
    service.crear_inventario({"sku": "COMBO-001", "cantidad_disponible": 10})
    service.reservar_stock("COMBO-001", 2)

    with pytest.raises(StockInsuficienteError):
        service.confirmar_salida("COMBO-001", 5)


def test_reponer_stock_incrementa_disponible(service):
    service.crear_inventario({"sku": "COMBO-001", "cantidad_disponible": 10})
    registro = service.reponer_stock("COMBO-001", 20)
    assert registro.cantidad_disponible == 30


def test_cantidad_cero_o_negativa_lanza_error(service):
    service.crear_inventario({"sku": "COMBO-001", "cantidad_disponible": 10})
    with pytest.raises(CantidadInvalidaError):
        service.reservar_stock("COMBO-001", 0)
    with pytest.raises(CantidadInvalidaError):
        service.reponer_stock("COMBO-001", -1)


def test_listar_bajo_umbral(service):
    service.crear_inventario({"sku": "BAJO", "cantidad_disponible": 2, "umbral_minimo": 5})
    service.crear_inventario({"sku": "OK", "cantidad_disponible": 50, "umbral_minimo": 5})

    resultado = service.listar_inventario(solo_bajo_umbral=True)
    assert len(resultado) == 1
    assert resultado[0].sku == "BAJO"
