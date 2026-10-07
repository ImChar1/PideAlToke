# Implementacion concreta del CatalogoClientPort: consulta por HTTP a ms-catalogo.
# Reenvia el JWT del usuario (propagacion de identidad), igual que el cliente de inventario.

from urllib.parse import quote

import requests

from app.core.config import settings
from app.domain.ports.catalogo_client_port import (
    CatalogoClientPort,
    ProductoNoDisponibleError,
    CatalogoNoDisponibleError,
)


class CatalogoHttpClient(CatalogoClientPort):
    def __init__(self, token: str, base_url: str = None):
        self.base_url = (base_url or settings.CATALOGO_SERVICE_URL).rstrip("/")
        self.token = token

    def obtener_producto_por_sku(self, sku: str) -> dict:
        url = f"{self.base_url}/api/v1/productos/sku/{quote(sku, safe='')}"
        try:
            response = requests.get(
                url, headers={"Authorization": f"Bearer {self.token}"}, timeout=5
            )
        except requests.RequestException as e:
            raise CatalogoNoDisponibleError(f"No fue posible contactar a ms-catalogo: {e}")

        if response.status_code == 404:
            raise ProductoNoDisponibleError(f"El producto '{sku}' no existe en el catalogo")
        if response.status_code >= 400:
            raise CatalogoNoDisponibleError(
                f"ms-catalogo respondio {response.status_code}: {response.text}"
            )

        producto = response.json()
        if not producto.get("activo", True):
            raise ProductoNoDisponibleError(f"El producto '{sku}' ya no esta disponible")
        return producto
