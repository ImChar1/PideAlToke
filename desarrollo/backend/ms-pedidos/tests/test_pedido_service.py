# Pruebas unitarias del PedidoService: integracion logica con Inventario y Catalogo
# (precio real, reserva de stock, compensacion, ciclo cancelar/confirmar) sin red ni DB real.

import pytest

from app.domain.services.pedido_service import (
    PedidoService,
    PedidoNoEncontradoError,
    PedidoEstadoInvalidoError,
)
from app.domain.ports.inventario_client_port import StockInsuficienteError, InventarioNoDisponibleError
from app.domain.ports.catalogo_client_port import ProductoNoDisponibleError, CatalogoNoDisponibleError
from app.schemas.schema_pedido import CrearPedidoSchema
from tests.fakes import FakePedidoRepository, FakeInventarioClient, FakeCatalogoClient

PRECIOS = {"COMBO-001": 2500, "BEB-001": 1000, "OFF-001": 500}


def _pedido(items):
    return CrearPedidoSchema(items=items)


def _armar(stock=None, repo=None, catalogo=None, inventario=None):
    inventario = inventario or FakeInventarioClient(stock=stock or {"COMBO-001": 10, "BEB-001": 5})
    repo = repo or FakePedidoRepository()
    catalogo = catalogo or FakeCatalogoClient(precios=PRECIOS)
    return PedidoService(repo, inventario, catalogo), repo, inventario, catalogo


# ------------------------------------------------------------------ crear

def test_crear_pedido_reserva_stock_y_calcula_monto_con_precios_del_catalogo():
    service, _, inventario, _ = _armar()

    pedido = service.crear_nuevo_pedido(_pedido([
        {"sku": "COMBO-001", "cantidad": 2},
        {"sku": "BEB-001", "cantidad": 1},
    ]), cliente_id="cliente-1")

    assert pedido.monto_total == 6000          # 2*2500 + 1*1000, precios del catalogo
    assert pedido.estado == "PENDIENTE"
    assert pedido.cliente_id == "cliente-1"
    assert inventario.reservas == {"COMBO-001": 2, "BEB-001": 1}


def test_crear_pedido_persiste_los_items_con_el_precio_del_catalogo():
    service, *_ = _armar()
    pedido = service.crear_nuevo_pedido(_pedido([{"sku": "COMBO-001", "cantidad": 3}]), "c1")
    assert pedido.items == [{"sku": "COMBO-001", "cantidad": 3, "precio_unitario": 2500.0}]


def test_el_cliente_no_puede_imponer_el_precio():
    # Aunque el body traiga precio_unitario / cliente_id, el schema los descarta.
    datos = CrearPedidoSchema(
        cliente_id="otro-usuario",
        items=[{"sku": "COMBO-001", "cantidad": 1, "precio_unitario": 1}],
    )
    assert not hasattr(datos.items[0], "precio_unitario")
    assert not hasattr(datos, "cliente_id")

    service, *_ = _armar()
    pedido = service.crear_nuevo_pedido(datos, cliente_id="usuario-del-jwt")
    assert pedido.monto_total == 2500
    assert pedido.cliente_id == "usuario-del-jwt"


def test_sku_repetido_se_consolida_en_una_sola_linea():
    service, _, inventario, catalogo = _armar()
    pedido = service.crear_nuevo_pedido(_pedido([
        {"sku": "COMBO-001", "cantidad": 1},
        {"sku": "COMBO-001", "cantidad": 2},
    ]), "c1")
    assert len(pedido.items) == 1 and pedido.items[0]["cantidad"] == 3
    assert inventario.reservas == {"COMBO-001": 3}
    assert catalogo.consultas == ["COMBO-001"]


def test_stock_insuficiente_no_crea_el_pedido_y_libera_lo_reservado():
    service, repo, inventario, _ = _armar(stock={"COMBO-001": 10, "BEB-001": 0})

    with pytest.raises(StockInsuficienteError):
        service.crear_nuevo_pedido(_pedido([
            {"sku": "COMBO-001", "cantidad": 2},
            {"sku": "BEB-001", "cantidad": 1},
        ]), "c1")

    assert repo._data == {}
    assert inventario.liberaciones.get("COMBO-001") == 2


def test_sku_inexistente_en_inventario_lanza_error_y_no_crea_pedido():
    inventario = FakeInventarioClient(stock={"COMBO-001": 10}, sku_inexistente="BEB-001")
    service, repo, *_ = _armar(inventario=inventario)

    with pytest.raises(InventarioNoDisponibleError):
        service.crear_nuevo_pedido(_pedido([{"sku": "BEB-001", "cantidad": 1}]), "c1")

    assert repo._data == {}


def test_producto_inexistente_en_catalogo_falla_sin_reservar_nada():
    service, repo, inventario, _ = _armar()
    with pytest.raises(ProductoNoDisponibleError):
        service.crear_nuevo_pedido(_pedido([
            {"sku": "COMBO-001", "cantidad": 1},
            {"sku": "NO-EXISTE", "cantidad": 1},
        ]), "c1")
    assert inventario.reservas == {} and repo._data == {}


def test_producto_inactivo_no_se_puede_pedir():
    catalogo = FakeCatalogoClient(precios=PRECIOS, inactivos={"OFF-001"})
    service, repo, inventario, _ = _armar(stock={"OFF-001": 5}, catalogo=catalogo)
    with pytest.raises(ProductoNoDisponibleError):
        service.crear_nuevo_pedido(_pedido([{"sku": "OFF-001", "cantidad": 1}]), "c1")
    assert inventario.reservas == {}


def test_catalogo_caido_propaga_error_sin_reservar():
    service, _, inventario, _ = _armar(catalogo=FakeCatalogoClient(precios=PRECIOS, caido=True))
    with pytest.raises(CatalogoNoDisponibleError):
        service.crear_nuevo_pedido(_pedido([{"sku": "COMBO-001", "cantidad": 1}]), "c1")
    assert inventario.reservas == {}


def test_si_falla_el_guardado_se_libera_el_stock_y_se_propaga_el_error_original():
    service, _, inventario, _ = _armar(repo=FakePedidoRepository(fallar_al_guardar=True))

    with pytest.raises(RuntimeError, match="base de datos"):
        service.crear_nuevo_pedido(_pedido([
            {"sku": "COMBO-001", "cantidad": 2},
            {"sku": "BEB-001", "cantidad": 1},
        ]), "c1")

    assert inventario.liberaciones == {"COMBO-001": 2, "BEB-001": 1}


def test_un_fallo_al_compensar_no_tapa_el_error_original():
    inventario = FakeInventarioClient(stock={"COMBO-001": 10, "BEB-001": 0})
    inventario.fallar_liberar.add("COMBO-001")      # la compensacion tambien va a fallar
    service, *_ = _armar(inventario=inventario)

    with pytest.raises(StockInsuficienteError):     # el error ORIGINAL, no el de liberar
        service.crear_nuevo_pedido(_pedido([
            {"sku": "COMBO-001", "cantidad": 2},
            {"sku": "BEB-001", "cantidad": 1},
        ]), "c1")


# ------------------------------------------------------------------ leer

def _crear(service, cliente="c1", sku="COMBO-001", cantidad=2):
    return service.crear_nuevo_pedido(_pedido([{"sku": sku, "cantidad": cantidad}]), cliente)


def test_el_dueno_obtiene_su_pedido():
    service, *_ = _armar()
    p = _crear(service, "c1")
    assert service.obtener_pedido(p.id, "c1") is p


def test_un_pedido_ajeno_se_reporta_como_no_encontrado():
    service, *_ = _armar()
    p = _crear(service, "c1")
    with pytest.raises(PedidoNoEncontradoError):
        service.obtener_pedido(p.id, "c2")


def test_un_admin_puede_ver_pedidos_ajenos():
    service, *_ = _armar()
    p = _crear(service, "c1")
    assert service.obtener_pedido(p.id, "admin", es_admin=True) is p


def test_pedido_inexistente_lanza_error():
    service, *_ = _armar()
    with pytest.raises(PedidoNoEncontradoError):
        service.obtener_pedido(999, "c1")


def test_listar_devuelve_solo_los_del_cliente_y_todos_si_se_pide():
    service, *_ = _armar()
    _crear(service, "c1"); _crear(service, "c1"); _crear(service, "c2")
    assert len(service.listar_pedidos("c1")) == 2
    assert len(service.listar_pedidos("c1", todos=True)) == 3


# ------------------------------------------------- cerrar el ciclo de stock

def test_cancelar_libera_el_stock_reservado_y_marca_cancelado():
    service, _, inventario, _ = _armar()
    p = _crear(service, "c1")

    cancelado = service.cancelar_pedido(p.id, "c1")

    assert cancelado.estado == "CANCELADO"
    assert inventario.liberaciones == {"COMBO-001": 2}
    assert inventario.reservas["COMBO-001"] == 0


def test_cancelar_es_idempotente_y_no_libera_dos_veces():
    service, _, inventario, _ = _armar()
    p = _crear(service, "c1")
    service.cancelar_pedido(p.id, "c1")
    service.cancelar_pedido(p.id, "c1")
    assert inventario.liberaciones == {"COMBO-001": 2}


def test_no_se_puede_cancelar_un_pedido_ajeno():
    service, *_ = _armar()
    p = _crear(service, "c1")
    with pytest.raises(PedidoNoEncontradoError):
        service.cancelar_pedido(p.id, "c2")


def test_admin_puede_cancelar_pedidos_de_otros():
    service, *_ = _armar()
    p = _crear(service, "c1")
    assert service.cancelar_pedido(p.id, "admin", es_admin=True).estado == "CANCELADO"


def test_confirmar_descuenta_en_firme_y_marca_confirmado():
    service, _, inventario, _ = _armar()
    p = _crear(service, "c1")

    confirmado = service.confirmar_pedido(p.id)

    assert confirmado.estado == "CONFIRMADO"
    assert inventario.confirmaciones == {"COMBO-001": 2}
    assert inventario.liberaciones == {}


def test_confirmar_es_idempotente():
    service, _, inventario, _ = _armar()
    p = _crear(service, "c1")
    service.confirmar_pedido(p.id)
    service.confirmar_pedido(p.id)
    assert inventario.confirmaciones == {"COMBO-001": 2}


def test_no_se_puede_cancelar_un_pedido_confirmado_ni_confirmar_uno_cancelado():
    service, *_ = _armar()
    confirmado = _crear(service, "c1"); service.confirmar_pedido(confirmado.id)
    cancelado = _crear(service, "c1"); service.cancelar_pedido(cancelado.id, "c1")

    with pytest.raises(PedidoEstadoInvalidoError):
        service.cancelar_pedido(confirmado.id, "c1")
    with pytest.raises(PedidoEstadoInvalidoError):
        service.confirmar_pedido(cancelado.id)


def test_cancelar_a_medias_es_reintentable_sin_liberar_dos_veces():
    service, _, inventario, _ = _armar()
    p = service.crear_nuevo_pedido(_pedido([
        {"sku": "COMBO-001", "cantidad": 2},
        {"sku": "BEB-001", "cantidad": 1},
    ]), "c1")

    inventario.fallar_liberar.add("BEB-001")           # inventario cae en el 2do item
    with pytest.raises(InventarioNoDisponibleError):
        service.cancelar_pedido(p.id, "c1")
    assert p.estado == "PENDIENTE"
    assert inventario.liberaciones == {"COMBO-001": 2}  # el 1ro ya se libero

    inventario.fallar_liberar.clear()                   # inventario vuelve
    service.cancelar_pedido(p.id, "c1")

    assert p.estado == "CANCELADO"
    assert inventario.liberaciones == {"COMBO-001": 2, "BEB-001": 1}   # COMBO-001 NO se libero otra vez


def test_confirmar_a_medias_es_reintentable_sin_confirmar_dos_veces():
    service, _, inventario, _ = _armar()
    p = service.crear_nuevo_pedido(_pedido([
        {"sku": "COMBO-001", "cantidad": 2},
        {"sku": "BEB-001", "cantidad": 1},
    ]), "c1")

    inventario.fallar_confirmar.add("BEB-001")
    with pytest.raises(InventarioNoDisponibleError):
        service.confirmar_pedido(p.id)

    inventario.fallar_confirmar.clear()
    service.confirmar_pedido(p.id)

    assert p.estado == "CONFIRMADO"
    assert inventario.confirmaciones == {"COMBO-001": 2, "BEB-001": 1}


def test_no_se_puede_confirmar_un_pedido_con_cancelacion_a_medias():
    service, _, inventario, _ = _armar()
    p = service.crear_nuevo_pedido(_pedido([
        {"sku": "COMBO-001", "cantidad": 2},
        {"sku": "BEB-001", "cantidad": 1},
    ]), "c1")
    inventario.fallar_liberar.add("BEB-001")
    with pytest.raises(InventarioNoDisponibleError):
        service.cancelar_pedido(p.id, "c1")

    with pytest.raises(PedidoEstadoInvalidoError):
        service.confirmar_pedido(p.id)
