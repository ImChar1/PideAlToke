# Implementacion concreta del InventarioClientPort: llama por HTTP al microservicio
# ms-inventario. Reenvia el JWT del usuario para que ms-inventario pueda validarlo
# igual que cualquier otra peticion (propagacion de identidad entre microservicios).

import requests

from app.core.config import settings
from app.domain.ports.inventario_client_port import (
    InventarioClientPort,
    StockInsuficienteError,
    InventarioNoDisponibleError,
)


class InventarioHttpClient(InventarioClientPort):
    def __init__(self, token: str, base_url: str = None):
        self.base_url = (base_url or settings.INVENTARIO_SERVICE_URL).rstrip("/")
        self.token = token

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

    def _post(self, sku: str, accion: str, cantidad: int) -> dict:
        url = f"{self.base_url}/inventario/{sku}/{accion}"
        try:
            response = requests.post(
                url, json={"cantidad": cantidad}, headers=self._headers(), timeout=5
            )
        except requests.RequestException as e:
            raise InventarioNoDisponibleError(
                f"No fue posible contactar a ms-inventario: {e}"
            )

        if response.status_code == 409:
            raise StockInsuficienteError(
                f"Stock insuficiente para el SKU '{sku}': {response.json().get('detail')}"
            )
        if response.status_code == 404:
            raise InventarioNoDisponibleError(
                f"El SKU '{sku}' no existe en Inventario"
            )
        if response.status_code >= 400:
            raise InventarioNoDisponibleError(
                f"ms-inventario respondio {response.status_code}: {response.text}"
            )

        return response.json()

    def reservar_stock(self, sku: str, cantidad: int) -> dict:
        return self._post(sku, "reservar", cantidad)

    def liberar_stock(self, sku: str, cantidad: int) -> dict:
        return self._post(sku, "liberar", cantidad)
