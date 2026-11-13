# DTO de LECTURA de los eventos que consume ms-analitica. Son CONTRATOS ENTRE MICROSERVICIOS:
# las copias del productor viven en ms-pedidos (EventoPedidoSchema) y ms-inventario
# (EventoMovimientoStock). `extra="ignore"` hace que campos nuevos agregados por el productor no
# rompan a este servicio; los campos que SI se declaran aqui son obligatorios (si faltan, el mensaje
# es invalido y se descarta con log, sin detener el consumo).

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ItemEventoPedido(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sku: str
    cantidad: int = Field(gt=0)
    precio_unitario: float = Field(ge=0)


class EventoPedidoRecibido(BaseModel):
    model_config = ConfigDict(extra="ignore")

    event_id: str
    tipo: Literal["creado", "confirmado", "cancelado"]
    ocurrido_en: datetime
    pedido_id: int
    cliente_id: str
    estado: str
    monto_total: float = Field(ge=0)
    items: List[ItemEventoPedido]


class EventoMovimientoRecibido(BaseModel):
    model_config = ConfigDict(extra="ignore")

    event_id: str
    tipo: Literal["reservado", "liberado", "confirmado", "repuesto", "stock_bajo"]
    ocurrido_en: datetime
    sku: str
    cantidad: int = Field(ge=0)
    stock_disponible: int
    stock_reservado: int
    stock_vendible: int
    umbral_minimo: Optional[int] = None
    pedido_id: Optional[int] = None
