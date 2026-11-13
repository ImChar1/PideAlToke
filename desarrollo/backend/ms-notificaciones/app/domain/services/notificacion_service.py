# Casos de uso de las notificaciones. Sin RabbitMQ ni FastAPI: recibe eventos ya validados, genera la
# notificacion y la guarda en memoria (ultimas N). Hoy el "canal" de entrega es el log del servicio;
# enviar correo/push seria un adaptador nuevo que reemplaza `_entregar`, sin tocar el resto.
#
# IDEMPOTENCIA: RabbitMQ entrega "al menos una vez" (si el consumidor cae antes del ACK, el mensaje
# vuelve). El `event_id` del evento permite descartar la repeticion.

import logging
import threading
from collections import Counter, OrderedDict, deque
from datetime import datetime, timezone
from typing import List, Optional

from app.schemas.schema_eventos import EventoAlertaStockRecibido, EventoPedidoRecibido

logger = logging.getLogger(__name__)

MAX_NOTIFICACIONES = 200
MAX_IDS_VISTOS = 10_000


class NotificacionService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._notificaciones: deque = deque(maxlen=MAX_NOTIFICACIONES)
        self._vistos: "OrderedDict[str, None]" = OrderedDict()
        self._por_tipo: Counter = Counter()
        self._duplicados = 0

    def _nuevo(self, event_id: str) -> bool:
        if event_id in self._vistos:
            self._duplicados += 1
            return False
        self._vistos[event_id] = None
        while len(self._vistos) > MAX_IDS_VISTOS:
            self._vistos.popitem(last=False)
        return True

    def _guardar(self, event_id: str, tipo: str, titulo: str, mensaje: str, referencia: str) -> None:
        notificacion = {
            "id": event_id, "tipo": tipo, "titulo": titulo, "mensaje": mensaje,
            "referencia": referencia, "creada_en": datetime.now(timezone.utc),
        }
        self._notificaciones.append(notificacion)
        self._por_tipo[tipo] += 1
        logger.info("NOTIFICACION [%s] %s: %s", tipo, titulo, mensaje)   # canal de entrega actual: log

    def notificar_pedido(self, evento: EventoPedidoRecibido) -> Optional[str]:
        """Genera la notificacion de un pedido en estado final. `creado` no notifica (devuelve None)."""
        if evento.tipo == "creado":
            return None
        with self._lock:
            if not self._nuevo(evento.event_id):
                return None
            if evento.tipo == "confirmado":
                self._guardar(evento.event_id, "pedido_confirmado", f"Pedido #{evento.pedido_id} confirmado",
                              f"El pedido #{evento.pedido_id} fue confirmado por ${evento.monto_total:,.0f}.",
                              f"pedido:{evento.pedido_id}")
            else:
                self._guardar(evento.event_id, "pedido_cancelado", f"Pedido #{evento.pedido_id} cancelado",
                              f"El pedido #{evento.pedido_id} fue cancelado y su stock liberado.",
                              f"pedido:{evento.pedido_id}")
            return evento.event_id

    def notificar_stock_bajo(self, evento: EventoAlertaStockRecibido) -> Optional[str]:
        with self._lock:
            if not self._nuevo(evento.event_id):
                return None
            umbral = f" (umbral {evento.umbral_minimo})" if evento.umbral_minimo is not None else ""
            self._guardar(evento.event_id, "stock_bajo", f"Stock bajo: {evento.sku}",
                          f"El SKU {evento.sku} quedo con {evento.stock_disponible} unidades{umbral}. Conviene reponer.",
                          f"sku:{evento.sku}")
            return evento.event_id

    def listar(self, tipo: Optional[str] = None, limite: int = 50) -> List[dict]:
        with self._lock:
            filas = [dict(n) for n in reversed(self._notificaciones) if tipo is None or n["tipo"] == tipo]
        return filas[:limite]

    def resumen(self) -> dict:
        with self._lock:
            return {"total": sum(self._por_tipo.values()), "por_tipo": dict(self._por_tipo),
                    "duplicados_ignorados": self._duplicados}
