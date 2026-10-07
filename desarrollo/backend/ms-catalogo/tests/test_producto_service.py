import pytest

from app.domain.services.producto_service import (
    ProductoService, ProductoNoEncontradoError, SkuDuplicadoError,
)
from tests.fake_repository import FakeProductoRepository


@pytest.fixture
def service():
    return ProductoService(FakeProductoRepository())


def _datos(sku="P-1", **extra):
    return {"sku": sku, "nombre": "Hamburguesa", "precio": 6990.0, **extra}


def test_crear_producto_ok(service):
    p = service.crear_producto(_datos())
    assert p.id == 1 and p.sku == "P-1" and p.activo is True


def test_crear_producto_sku_duplicado_lanza_error(service):
    service.crear_producto(_datos())
    with pytest.raises(SkuDuplicadoError):
        service.crear_producto(_datos())


def test_obtener_producto_inexistente_lanza_error(service):
    with pytest.raises(ProductoNoEncontradoError):
        service.obtener_producto(99)


def test_listar_filtra_por_categoria(service):
    service.crear_producto(_datos("A", categoria="Pizzas"))
    service.crear_producto(_datos("B", categoria="Bebidas"))
    assert [p.sku for p in service.listar_productos(categoria="Pizzas")] == ["A"]


def test_actualizar_solo_cambia_los_campos_enviados(service):
    p = service.crear_producto(_datos(categoria="Pizzas"))
    actualizado = service.actualizar_producto(p.id, {"precio": 100.0})
    assert actualizado.precio == 100.0 and actualizado.categoria == "Pizzas"


def test_actualizar_inexistente_lanza_error(service):
    with pytest.raises(ProductoNoEncontradoError):
        service.actualizar_producto(99, {"precio": 1.0})


def test_desactivar_es_baja_logica_y_lo_oculta_del_listado(service):
    p = service.crear_producto(_datos())
    assert service.desactivar_producto(p.id).activo is False
    assert service.listar_productos() == []
    assert service.obtener_producto(p.id) is not None  # el registro sigue existiendo
