# Contratos (DTO) de respuesta del API de analitica.

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel


class ResumenVentasSchema(BaseModel):
    pedidos_pendientes: int
    pedidos_confirmados: int
    pedidos_cancelados: int
    pedidos_totales: int
    ingresos_confirmados: float
    ticket_promedio: float
    ultimo_evento_en: Optional[datetime] = None


class VentasHoraSchema(BaseModel):
    hora: str
    pedidos: int
    ingresos: float


class ProductoTopSchema(BaseModel):
    sku: str
    unidades_vendidas: int
    ingresos: float


class StockSkuSchema(BaseModel):
    sku: str
    stock_disponible: int
    stock_reservado: int
    stock_vendible: int
    umbral_minimo: Optional[int] = None
    bajo_umbral: bool
    actualizado_en: datetime


class AlertaStockSchema(BaseModel):
    sku: str
    stock_disponible: int
    umbral_minimo: Optional[int] = None
    ocurrido_en: datetime


class MetricasSchema(BaseModel):
    iniciado_en: datetime
    mensajes_consumidos: Dict[str, int]
    mensajes_invalidos: Dict[str, int]
    mensajes_fallidos: Dict[str, int]
    movimientos_por_tipo: Dict[str, int]
    ultimo_offset_por_particion: Dict[str, int]
    ultimo_movimiento_en: Optional[datetime] = None
