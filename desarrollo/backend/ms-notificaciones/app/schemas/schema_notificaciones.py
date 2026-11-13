from datetime import datetime
from typing import Dict, List

from pydantic import BaseModel


class NotificacionSchema(BaseModel):
    id: str
    tipo: str            # pedido_confirmado | pedido_cancelado | stock_bajo
    titulo: str
    mensaje: str
    referencia: str      # "pedido:12" o "sku:SKU-001"
    creada_en: datetime


class ResumenNotificacionesSchema(BaseModel):
    total: int
    por_tipo: Dict[str, int]
    duplicados_ignorados: int
