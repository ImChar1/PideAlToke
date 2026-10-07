# Reglas de negocio

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import List

from app.domain.ports.pedido_repository_port import PedidoRepositoryPort
from app.domain.ports.inventario_client_port import InventarioClientPort
from app.domain.ports.catalogo_client_port import CatalogoClientPort
from app.schemas.schema_pedido import CrearPedidoSchema
from app.domain.models.pedido import PedidoModel

logger = logging.getLogger(__name__)

ESTADO_PENDIENTE = "PENDIENTE"
ESTADO_CONFIRMADO = "CONFIRMADO"
ESTADO_CANCELADO = "CANCELADO"

# Marcas de progreso guardadas en cada item del pedido mientras se cierran sus reservas.
# Hacen que cancelar/confirmar sea REINTENTABLE: si ms-inventario falla a mitad de camino,
# al reintentar no se vuelve a liberar/confirmar lo que ya se proceso (lo que descontaria
# reservas de OTROS pedidos).
_MARCA_LIBERADO = "stock_liberado"
_MARCA_CONFIRMADO = "stock_confirmado"


class PedidoNoEncontradoError(Exception):
    pass


class PedidoEstadoInvalidoError(Exception):
    pass


class PedidoService:

    def __init__(
        self,
        repository: PedidoRepositoryPort,
        inventario_client: InventarioClientPort,
        catalogo_client: CatalogoClientPort,
    ):
        self.repository = repository
        self.inventario_client = inventario_client
        self.catalogo_client = catalogo_client

    # ------------------------------------------------------------------ crear

    def crear_nuevo_pedido(self, datos_pedido: CrearPedidoSchema, cliente_id: str) -> PedidoModel:
        """
        `cliente_id` lo entrega el router desde el JWT (nunca desde el body) y los
        precios se consultan al catalogo: el cliente solo decide QUE y CUANTO compra.
        """
        # Un mismo SKU repetido en el pedido se consolida en una sola linea.
        cantidades: dict[str, int] = {}
        for item in datos_pedido.items:
            cantidades[item.sku] = cantidades.get(item.sku, 0) + item.cantidad

        # 1. Precio real desde ms-catalogo (falla rapido ANTES de reservar nada).
        lineas = []
        monto_total = Decimal("0")
        for sku, cantidad in cantidades.items():
            producto = self.catalogo_client.obtener_producto_por_sku(sku)
            precio = Decimal(str(producto["precio"]))
            lineas.append({"sku": sku, "cantidad": cantidad, "precio_unitario": float(precio)})
            monto_total += precio * cantidad
        monto_total = monto_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # 2. Reservar stock item por item. Cualquier fallo (de inventario o al persistir)
        # libera lo ya reservado para no dejar stock "fantasma" apartado.
        items_reservados = []
        try:
            for linea in lineas:
                self.inventario_client.reservar_stock(linea["sku"], linea["cantidad"])
                items_reservados.append(linea)

            nuevo_pedido = PedidoModel(
                cliente_id=cliente_id,
                monto_total=monto_total,
                estado=ESTADO_PENDIENTE,
                items=lineas,
            )
            return self.repository.guardar(nuevo_pedido)
        except Exception:
            self._compensar_reservas(items_reservados)
            raise

    def _compensar_reservas(self, items_reservados: List[dict]) -> None:
        """
        Libera, en modo "mejor esfuerzo", las reservas ya hechas. NUNCA lanza: un fallo
        al compensar no debe tapar el error original que disparo la compensacion.
        """
        for item in items_reservados:
            try:
                self.inventario_client.liberar_stock(item["sku"], item["cantidad"])
            except Exception:
                logger.exception(
                    "No se pudo liberar la reserva de %s x%s al compensar un pedido fallido; "
                    "requiere revision manual", item["sku"], item["cantidad"],
                )

    # ------------------------------------------------------------------ leer

    def obtener_pedido(self, pedido_id: int, cliente_id: str, es_admin: bool = False) -> PedidoModel:
        pedido = self.repository.obtener_por_id(pedido_id)
        # Un pedido ajeno se reporta como "no encontrado" (no 403) para no revelar que existe.
        if pedido is None or (not es_admin and pedido.cliente_id != cliente_id):
            raise PedidoNoEncontradoError("Pedido no encontrado")
        return pedido

    def listar_pedidos(self, cliente_id: str, todos: bool = False) -> List[PedidoModel]:
        if todos:
            return self.repository.listar_todos()
        return self.repository.listar_por_cliente(cliente_id)

    # ------------------------------------------------- cerrar el ciclo de stock

    def cancelar_pedido(self, pedido_id: int, cliente_id: str, es_admin: bool = False) -> PedidoModel:
        """Cancela un pedido PENDIENTE y LIBERA el stock que tenia reservado."""
        pedido = self.obtener_pedido(pedido_id, cliente_id, es_admin)

        if pedido.estado == ESTADO_CANCELADO:
            return pedido  # idempotente
        self._exigir_pendiente(pedido, "cancelar")
        if any(i.get(_MARCA_CONFIRMADO) for i in pedido.items):
            raise PedidoEstadoInvalidoError(
                "El pedido tiene una confirmacion de stock a medio completar; reintenta confirmarlo."
            )

        self._cerrar_reservas(pedido, self.inventario_client.liberar_stock, _MARCA_LIBERADO)
        pedido.estado = ESTADO_CANCELADO
        return self.repository.guardar(pedido)

    def confirmar_pedido(self, pedido_id: int) -> PedidoModel:
        """
        Confirma un pedido PENDIENTE (pago recibido / entregado): el stock reservado se
        descuenta en firme del inventario. Uso administrativo (el router exige rol ADMIN).
        """
        pedido = self.obtener_pedido(pedido_id, cliente_id="", es_admin=True)

        if pedido.estado == ESTADO_CONFIRMADO:
            return pedido  # idempotente
        self._exigir_pendiente(pedido, "confirmar")
        if any(i.get(_MARCA_LIBERADO) for i in pedido.items):
            raise PedidoEstadoInvalidoError(
                "El pedido tiene una cancelacion de stock a medio completar; reintenta cancelarlo."
            )

        self._cerrar_reservas(pedido, self.inventario_client.confirmar_salida, _MARCA_CONFIRMADO)
        pedido.estado = ESTADO_CONFIRMADO
        return self.repository.guardar(pedido)

    @staticmethod
    def _exigir_pendiente(pedido: PedidoModel, accion: str) -> None:
        if pedido.estado != ESTADO_PENDIENTE:
            raise PedidoEstadoInvalidoError(
                f"No se puede {accion} un pedido en estado {pedido.estado}"
            )

    def _cerrar_reservas(self, pedido: PedidoModel, operacion, marca: str) -> None:
        """
        Aplica `operacion(sku, cantidad)` (liberar o confirmar_salida) a cada item aun no
        procesado, guardando el progreso despues de cada uno. Si ms-inventario falla a
        mitad de camino la excepcion se propaga, pero lo ya hecho queda registrado.
        """
        items = [dict(i) for i in pedido.items]
        for item in items:
            if item.get(marca):
                continue
            operacion(item["sku"], item["cantidad"])
            item[marca] = True
            # Se reasigna una lista nueva: SQLAlchemy no detecta mutaciones in-place de JSON.
            pedido.items = [dict(i) for i in items]
            self.repository.guardar(pedido)
