# Contrato (DTO) de los eventos de MOVIMIENTO DE STOCK que ms-inventario publica.
# Viaja por Kafka (topico `inventario.movimientos`, key = sku) y, solo el tipo `stock_bajo`, tambien
# por RabbitMQ (exchange direct `pidealtoke.alertas`). Es un CONTRATO ENTRE MICROSERVICIOS:
# ms-analitica y ms-notificaciones tienen su propia copia de lectura. Agrega campos nuevos como
# opcionales para no romper a los consumidores.

import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

TipoMovimiento = Literal["reservado", "liberado", "confirmado", "repuesto", "stock_bajo"]


class EventoMovimientoStock(BaseModel):
    # Id unico: los consumidores lo usan para descartar duplicados (entrega "al menos una vez").
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tipo: TipoMovimiento
    ocurrido_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sku: str
    cantidad: int                       # unidades del movimiento (0 en `stock_bajo`: no mueve nada)
    stock_disponible: int               # cantidad_disponible DESPUES del movimiento
    stock_reservado: int                # cantidad_reservada DESPUES del movimiento
    stock_vendible: int                 # disponible - reservado
    umbral_minimo: Optional[int] = None  # umbral configurado para el SKU (si tiene)
    pedido_id: Optional[int] = None     # correlacion con el pedido, cuando el origen la conoce

    @classmethod
    def desde_registro(cls, tipo: str, registro, cantidad: int, pedido_id: Optional[int] = None) -> "EventoMovimientoStock":
        """Arma el evento desde el registro de inventario ya actualizado (duck-typing: no importa el ORM)."""
        return cls(
            tipo=tipo,
            sku=registro.sku,
            cantidad=cantidad,
            stock_disponible=registro.cantidad_disponible,
            stock_reservado=registro.cantidad_reservada,
            stock_vendible=registro.cantidad_disponible - registro.cantidad_reservada,
            umbral_minimo=registro.umbral_minimo,
            pedido_id=pedido_id,
        )
