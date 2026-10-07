# Casos de uso y reglas de negocio del Inventario.
# Sin dependencias directas de FastAPI ni de SQLAlchemy: solo conoce el Port.
#
# Concepto clave: "stock vendible" = cantidad_disponible - cantidad_reservada.
# Un pedido en curso RESERVA stock (no lo descuenta aun); si el pedido se cancela,
# se LIBERA la reserva; si el pedido se confirma/paga, se CONFIRMA LA SALIDA
# (ahi si se descuenta cantidad_disponible en firme).

from typing import List, Optional

from app.domain.ports.inventario_repository_port import InventarioRepositoryPort


class InventarioNoEncontradoError(Exception):
    pass


class SkuDuplicadoError(Exception):
    pass


class StockInsuficienteError(Exception):
    pass


class CantidadInvalidaError(Exception):
    pass


class InventarioService:
    def __init__(self, repository: InventarioRepositoryPort):
        self.repository = repository

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
        return resultado

    def liberar_stock(self, sku: str, cantidad: int):
        """Revierte una reserva previa (ej. el pedido asociado se cancelo)."""
        self._validar_cantidad_positiva(cantidad)
        self.obtener_inventario(sku)  # 404 si no existe

        resultado = self.repository.liberar_reserva(sku, cantidad)
        if resultado is None:
            raise InventarioNoEncontradoError(f"No hay inventario para el SKU '{sku}'")
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
        return resultado

    def reponer_stock(self, sku: str, cantidad: int):
        """Ingreso de nueva mercaderia: aumenta el stock disponible."""
        self._validar_cantidad_positiva(cantidad)
        self.obtener_inventario(sku)  # valida que exista
        resultado = self.repository.ajustar_cantidades(sku, delta_disponible=cantidad, delta_reservada=0)
        if resultado is None:
            raise InventarioNoEncontradoError(f"No hay inventario para el SKU '{sku}'")
        return resultado

    def actualizar_umbral(self, sku: str, umbral_minimo: int):
        self.obtener_inventario(sku)  # valida que exista
        return self.repository.actualizar_umbral(sku, umbral_minimo)

    @staticmethod
    def _validar_cantidad_positiva(cantidad: int):
        if cantidad <= 0:
            raise CantidadInvalidaError("La cantidad debe ser mayor a 0")
