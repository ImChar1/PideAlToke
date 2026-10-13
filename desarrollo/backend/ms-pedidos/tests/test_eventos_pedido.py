# El PedidoService publica un evento por cada cambio de estado (creado / confirmado / cancelado)
# y un fallo del broker NUNCA rompe ni revierte la operacion. Sin red ni RabbitMQ: se usa un Fake.

from app.domain.ports.evento_publisher_port import PedidoEventPublisherPort, PublicacionEventoError
from app.domain.services.pedido_service import PedidoService
from app.schemas.schema_pedido import CrearPedidoSchema
from tests.fakes import FakePedidoRepository, FakeInventarioClient, FakeCatalogoClient

PRECIOS = {"COMBO-001": 2500, "BEB-001": 1000}


class FakeEventPublisher(PedidoEventPublisherPort):
    """Guarda los eventos en memoria; con `fallar=True` simula un broker caido."""

    def __init__(self, fallar: bool = False):
        self.eventos = []
        self.fallar = fallar

    def publicar(self, evento) -> None:
        if self.fallar:
            raise PublicacionEventoError("broker caido")
        self.eventos.append(evento)


def _armar(publisher):
    inventario = FakeInventarioClient(stock={"COMBO-001": 10, "BEB-001": 5})
    repo = FakePedidoRepository()
    service = PedidoService(repo, inventario, FakeCatalogoClient(precios=PRECIOS), event_publisher=publisher)
    return service, repo, inventario


def _crear(service):
    datos = CrearPedidoSchema(items=[{"sku": "COMBO-001", "cantidad": 2}, {"sku": "BEB-001", "cantidad": 1}])
    return service.crear_nuevo_pedido(datos, cliente_id="cliente-1")


def test_crear_pedido_publica_evento_creado():
    publisher = FakeEventPublisher()
    service, _, _ = _armar(publisher)

    pedido = _crear(service)

    assert len(publisher.eventos) == 1
    evento = publisher.eventos[0]
    assert evento.tipo == "creado"
    assert evento.pedido_id == pedido.id
    assert evento.cliente_id == "cliente-1"
    assert evento.estado == "PENDIENTE"
    assert evento.monto_total == 6000.0
    assert [(i.sku, i.cantidad, i.precio_unitario) for i in evento.items] == [
        ("COMBO-001", 2, 2500.0),
        ("BEB-001", 1, 1000.0),
    ]


def test_cancelar_publica_evento_cancelado_una_sola_vez():
    publisher = FakeEventPublisher()
    service, _, _ = _armar(publisher)
    pedido = _crear(service)

    service.cancelar_pedido(pedido.id, "cliente-1")
    service.cancelar_pedido(pedido.id, "cliente-1")  # idempotente: no cambia nada, no vuelve a publicar

    assert [e.tipo for e in publisher.eventos] == ["creado", "cancelado"]
    assert publisher.eventos[1].estado == "CANCELADO"


def test_confirmar_publica_evento_confirmado_una_sola_vez():
    publisher = FakeEventPublisher()
    service, _, _ = _armar(publisher)
    pedido = _crear(service)

    service.confirmar_pedido(pedido.id)
    service.confirmar_pedido(pedido.id)

    assert [e.tipo for e in publisher.eventos] == ["creado", "confirmado"]


def test_el_evento_no_filtra_las_marcas_internas_de_progreso():
    publisher = FakeEventPublisher()
    service, _, _ = _armar(publisher)
    pedido = _crear(service)

    service.cancelar_pedido(pedido.id, "cliente-1")  # deja `stock_liberado` en cada item guardado

    cuerpo = publisher.eventos[1].model_dump()
    for item in cuerpo["items"]:
        assert set(item) == {"sku", "cantidad", "precio_unitario"}


def test_si_el_broker_falla_el_pedido_se_crea_igual_y_no_se_libera_el_stock():
    service, repo, inventario = _armar(FakeEventPublisher(fallar=True))

    pedido = _crear(service)

    assert pedido.estado == "PENDIENTE"
    assert repo.obtener_por_id(pedido.id) is not None
    # La compensacion (liberar reservas) es solo para fallos de reserva/persistencia, no de eventos.
    assert inventario.liberaciones == {}
    assert inventario.reservas == {"COMBO-001": 2, "BEB-001": 1}


def test_si_el_broker_falla_cancelar_y_confirmar_tambien_se_completan():
    publisher = FakeEventPublisher()
    service, _, _ = _armar(publisher)
    p1 = _crear(service)
    p2 = _crear(service)
    publisher.fallar = True

    assert service.cancelar_pedido(p1.id, "cliente-1").estado == "CANCELADO"
    assert service.confirmar_pedido(p2.id).estado == "CONFIRMADO"


def test_sin_publicador_el_servicio_funciona_igual():
    service, _, _ = _armar(None)  # RabbitMQ apagado -> NullEventPublisher por defecto
    assert _crear(service).estado == "PENDIENTE"
