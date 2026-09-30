# Reglas de negocio

from app.domain.ports.pedido_repository_port import PedidoRepositoryPort
from app.domain.ports.inventario_client_port import (
    InventarioClientPort,
    StockInsuficienteError,
    InventarioNoDisponibleError,
)
from app.schemas.schema_pedido import CrearPedidoSchema
from app.domain.models.pedido import PedidoModel


class PedidoService:

    def __init__(self, repository: PedidoRepositoryPort, inventario_client: InventarioClientPort):
        self.repository = repository
        self.inventario_client = inventario_client

    def crear_nuevo_pedido(self, datos_pedido: CrearPedidoSchema) -> PedidoModel:
        # Calculo del monto total automáticamente desde los items
        monto_total = sum(item.cantidad * item.precio_unitario for item in datos_pedido.items)

        # 1. Reservar stock en ms-inventario, item por item.
        # Si alguno falla (stock insuficiente o inventario no disponible), se liberan
        # las reservas que ya se hayan alcanzado a hacer (compensacion), para no dejar
        # stock "fantasma" apartado por un pedido que nunca se va a crear.
        items_reservados = []
        try:
            for item in datos_pedido.items:
                self.inventario_client.reservar_stock(item.sku, item.cantidad)
                items_reservados.append(item)
        except (StockInsuficienteError, InventarioNoDisponibleError):
            for item in items_reservados:
                self.inventario_client.liberar_stock(item.sku, item.cantidad)
            raise

        # 2. Solo si el stock quedo reservado, se persiste el pedido.
        nuevo_pedido = PedidoModel(
            cliente_id=datos_pedido.cliente_id,
            monto_total=monto_total,
            estado="PENDIENTE",
            items=[item.model_dump() for item in datos_pedido.items],
        )

        return self.repository.guardar(nuevo_pedido)
