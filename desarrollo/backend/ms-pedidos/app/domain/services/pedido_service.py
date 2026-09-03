# Reglas de negocio

from app.domain.ports.pedido_repository_port import PedidoRepositoryPort
from app.schemas.schema_pedido import CrearPedidoSchema
from app.domain.models.pedido import PedidoModel

class PedidoService:

    def __init__(self, repositorty: PedidoRepositoryPort):
        self.repository = repositorty

    def crear_nuevo_pedido(self, datos_pedido: CrearPedidoSchema) -> PedidoModel:
        # Calculo del monto total automáticamente desde los items
        monto_total = sum(item.cantidad * item.precio_unitario for item in datos_pedido.items)

        # Instanciar modelo con estado inicial
        nuevo_pedido = PedidoModel(
            cliente_id=datos_pedido.cliente_id,
            monto_total=monto_total,
            estado="PENDIENTE"
        )

        # Guardar en DB mediante el puerto
        return self.repository.guardar(nuevo_pedido)