# Casos de uso y reglas de negocio del Catalogo de Productos.
# Sin dependencias directas de FastAPI ni de SQLAlchemy: solo conoce el Port.

from typing import List, Optional

from app.domain.ports.producto_repository_port import ProductoRepositoryPort


class ProductoNoEncontradoError(Exception):
    pass


class SkuDuplicadoError(Exception):
    pass


class ProductoService:
    def __init__(self, repository: ProductoRepositoryPort):
        self.repository = repository

    def crear_producto(self, datos: dict):
        # Regla de negocio: el SKU debe ser unico dentro del catalogo
        existente = self.repository.obtener_por_sku(datos["sku"])
        if existente:
            raise SkuDuplicadoError(f"Ya existe un producto con SKU '{datos['sku']}'")
        return self.repository.crear(datos)

    def obtener_producto(self, producto_id: int):
        producto = self.repository.obtener_por_id(producto_id)
        if not producto:
            raise ProductoNoEncontradoError(f"Producto {producto_id} no encontrado")
        return producto

    def listar_productos(self, categoria: Optional[str] = None) -> List:
        return self.repository.listar(categoria=categoria)

    def actualizar_producto(self, producto_id: int, datos: dict):
        producto = self.repository.actualizar(producto_id, datos)
        if not producto:
            raise ProductoNoEncontradoError(f"Producto {producto_id} no encontrado")
        return producto

    def desactivar_producto(self, producto_id: int):
        producto = self.repository.desactivar(producto_id)
        if not producto:
            raise ProductoNoEncontradoError(f"Producto {producto_id} no encontrado")
        return producto
