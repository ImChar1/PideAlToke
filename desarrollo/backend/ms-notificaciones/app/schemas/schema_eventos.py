# DTO de LECTURA de los eventos que consume ms-notificaciones (contratos entre microservicios).
# `extra="ignore"`: campos nuevos del productor no rompen a este servicio. Los campos declarados
# aqui son obligatorios: si faltan, el mensaje es invalido y va directo a la DLQ.

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class EventoPedidoRecibido(BaseModel):
    """Evento publicado por ms-pedidos en `pedidos.events` (routing key pedido.*)."""
    model_config = ConfigDict(extra="ignore")

    event_id: str
    tipo: Literal["creado", "confirmado", "cancelado"]
    pedido_id: int
    cliente_id: str
    estado: str
    monto_total: float = Field(ge=0)


class EventoAlertaStockRecibido(BaseModel):
    """Alerta publicada por ms-inventario en `pidealtoke.alertas` (routing key stock.bajo)."""
    model_config = ConfigDict(extra="ignore")

    event_id: str
    tipo: Literal["stock_bajo"]
    sku: str
    stock_disponible: int
    umbral_minimo: Optional[int] = None
