# Casos de uso y reglas de negocio del Inventario.
# Sin dependencias directas de FastAPI ni de SQLAlchemy: solo conoce el Port.
#
# Concepto clave: "stock vendible" = cantidad_disponible - cantidad_reservada.
# Un pedido en curso RESERVA stock (no lo descuenta aun); si el pedido se cancela,
# se LIBERA la reserva; si el pedido se confirma/paga, se CONFIRMA LA SALIDA
# (ahi si se descuenta cantidad_disponible en firme).

import logging
from typing import List, Optional

from app.domain.ports.inventario_repository_port import InventarioRepositoryPort
from app.domain.ports.movimiento_publisher_port import (
    MovimientoEventPublisherPort,
    NullMovimientoPublisher,
)
from app.schemas.schema_eventos_movimiento import EventoMovimientoStock

logger = logging.getLogger(__name__)


class InventarioNoEncontradoError(Exception):
    pass


class SkuDuplicadoError(Exception):
    pass


class StockInsuficienteError(Exception):
    pass


class CantidadInvalidaError(Exception):
    pass


class InventarioService:
    def __init__(
        self,
        repository: InventarioRepositoryPort,
        movimiento_publisher: Optional[MovimientoEventPublisherPort] = None,
    ):
        self.repository = repository
        # Opcional: sin publicador (tests, Kafka/RabbitMQ apagados) no se emite ningun evento.
        self.movimiento_publisher = movimiento_publisher or NullMovimientoPublisher()

    def _emitir(self, tipo: str, registro, cantidad: int) -> None:
        """
        Publica el movimiento ya persistido. NUNCA lanza: el stock ya cambio en la base y un broker
        caido no puede romper (ni revertir) la operacion. Si el movimiento deja el stock cruzando el
        umbral minimo, ademas se emite UNA alerta `stock_bajo`.
        """
        try:
            self.movimiento_publisher.publicar(EventoMovimientoStock.desde_registro(tipo, registro, cantidad))
            if self._cruzo_umbral(tipo, registro, cantidad):
                self.movimiento_publisher.publicar(EventoMovimientoStock.desde_registro("stock_bajo", registro, 0))
        except Exception:
            logger.exception(
                "No se pudo publicar el movimiento '%s' del SKU %s (la operacion se completo igual)",
                tipo, getattr(registro, "sku", None),
            )

    @staticmethod
    def _cruzo_umbral(tipo: str, registro, cantidad: int) -> bool:
        """
        True si ESTE movimiento hizo pasar cantidad_disponible de "sobre el umbral" a "en o bajo el umbral"
        (misma definicion de "bajo umbral" que el listado ?bajo_umbral=true). Solo una salida en firme
        baja cantidad_disponible; se alerta al cruzar, no en cada movimiento posterior (sin spam).
        """
        if tipo != "confirmado" or registro.umbral_minimo is None:
            return False
        antes = registro.cantidad_disponible + cantidad
        return antes > registro.umbral_minimo >= registro.cantidad_disponible

    def crear_inventario(self, datos: dict):
        if self.repository.obtener_por_sku(datos["sku"]):
            raise SkuDuplicadoError(f"Ya existe inventario para el SKU '{datos['sku']}'")
        datos.setdefault("cantidad_disponible", 0)
        datos.setdefault("cantidad_reservada", 0)
        return self.repository.crear(datos)

    def obtener_inventario(self, sku: str):
        registro = self.repository.obtener_por_sku(sku)
        if not registro:
            raise InventarioNoEncontradoError(f"No hay inventario para el SKU '{sku}'")
        return registro

    def listar_inventario(self, solo_bajo_umbral: bool = False) -> List:
        return self.repository.listar(solo_bajo_umbral=solo_bajo_umbral)

    def reservar_stock(self, sku: str, cantidad: int):
        self._validar_cantidad_positiva(cantidad)
        self.obtener_inventario(sku)  # 404 si no existe

        # La validacion de stock vendible y el ajuste son UNA operacion atomica en el
        # repositorio: sin ventana entre "comprobar" y "reservar" (sin sobreventa).
        resultado = self.repository.ajustar_cantidades(
            sku, delta_disponible=0, delta_reservada=cantidad, min_vendible=cantidad
        )
        if resultado is None:
            registro = self.obtener_inventario(sku)
            vendible = registro.cantidad_disponible - registro.cantidad_reservada
            raise StockInsuficienteError(
                f"Stock insuficiente para '{sku}': disponible={vendible}, solicitado={cantidad}"
            )
        self._emitir("reservado", resultado, cantidad)
        return resultado

    def liberar_stock(self, sku: str, cantidad: int):
        """Revierte una reserva previa (ej. el pedido asociado se cancelo)."""
        self._validar_cantidad_positiva(cantidad)
        self.obtener_inventario(sku)  # 404 si no existe

        resultado = self.repository.liberar_reserva(sku, cantidad)
        if resultado is None:
            raise InventarioNoEncontradoError(f"No hay inventario para el SKU '{sku}'")
        self._emitir("liberado", resultado, cantidad)
        return resultado

    def confirmar_salida(self, sku: str, cantidad: int):
        """
        El pedido se confirma/paga: el stock reservado se descuenta en firme
        de cantidad_disponible, y deja de estar reservado.
        """
        self._validar_cantidad_positiva(cantidad)
        self.obtener_inventario(sku)  # 404 si no existe

        resultado = self.repository.ajustar_cantidades(
            sku, delta_disponible=-cantidad, delta_reservada=-cantidad, min_reservada=cantidad
        )
        if resultado is None:
            registro = self.obtener_inventario(sku)
            raise StockInsuficienteError(
                f"No se puede confirmar salida de {cantidad} unidades para '{sku}': "
                f"solo hay {registro.cantidad_reservada} reservadas"
            )
        self._emitir("confirmado", resultado, cantidad)
        return resultado

    def reponer_stock(self, sku: str, cantidad: int):
        """Ingreso de nueva mercaderia: aumenta el stock disponible."""
        self._validar_cantidad_positiva(cantidad)
        self.obtener_inventario(sku)  # valida que exista
        resultado = self.repository.ajustar_cantidades(sku, delta_disponible=cantidad, delta_reservada=0)
        if resultado is None:
            raise InventarioNoEncontradoError(f"No hay inventario para el SKU '{sku}'")
        self._emitir("repuesto", resultado, cantidad)
        return resultado

    def actualizar_umbral(self, sku: str, umbral_minimo: int):
        self.obtener_inventario(sku)  # valida que exista
        return self.repository.actualizar_umbral(sku, umbral_minimo)

    @staticmethod
    def _validar_cantidad_positiva(cantidad: int):
        if cantidad <= 0:
            raise CantidadInvalidaError("La cantidad debe ser mayor a 0")
