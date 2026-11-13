# Casos de uso de la analitica en tiempo real. Sin Kafka ni FastAPI: recibe eventos ya validados y
# mantiene el estado en memoria (agregados), protegido con un lock porque lo escriben varios
# consumidores (hilos) y lo lee el API.
#
# IDEMPOTENCIA POR OFFSET: cada llamada trae el origen (topico, particion, offset). Si ese offset ya
# se aplico (o es menor) se ignora. Asi releer el log desde el principio (reconstruccion al arrancar o
# tras un rebalanceo) nunca cuenta dos veces el mismo evento.

import threading
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.schemas.schema_eventos import EventoMovimientoRecibido, EventoPedidoRecibido

Origen = Tuple[str, int, int]  # (topico, particion, offset)

MAX_ALERTAS = 50
MAX_HORAS = 48


class AnaliticaService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._inicio = datetime.now(timezone.utc)
        self._offsets: Dict[Tuple[str, int], int] = {}       # ultimo offset aplicado por particion

        # --- ventas (topico pedidos.eventos) ---
        self._pedidos: Dict[int, dict] = {}                  # pedido_id -> {estado, monto, items}
        self._estados = Counter()                            # pendiente / confirmado / cancelado
        self._ingresos = 0.0                                 # suma de monto_total de pedidos confirmados
        self._unidades: Counter = Counter()                  # sku -> unidades vendidas (confirmadas)
        self._ingresos_sku: Dict[str, float] = defaultdict(float)
        self._por_hora: "OrderedDict[str, dict]" = OrderedDict()
        self._ultimo_pedido_en: Optional[datetime] = None

        # --- stock (topico inventario.movimientos) ---
        self._stock: Dict[str, dict] = {}                    # sku -> ultimo estado conocido
        self._movimientos = Counter()                        # tipo -> cantidad de movimientos
        self._alertas: List[dict] = []                       # ultimas alertas stock_bajo
        self._ultimo_movimiento_en: Optional[datetime] = None

        # --- metricas del consumo ---
        self._consumidos = Counter()                         # topico -> mensajes aplicados
        self._invalidos = Counter()                          # topico -> mensajes descartados por formato
        self._fallidos = Counter()                           # topico -> mensajes descartados tras reintentos

    # ------------------------------------------------------------ idempotencia

    def _ya_aplicado(self, origen: Origen) -> bool:
        topico, particion, offset = origen
        return offset <= self._offsets.get((topico, particion), -1)

    def _marcar(self, origen: Origen) -> None:
        topico, particion, offset = origen
        self._offsets[(topico, particion)] = offset
        self._consumidos[topico] += 1

    # ------------------------------------------------------------ entrada de eventos

    def registrar_pedido(self, evento: EventoPedidoRecibido, origen: Origen) -> bool:
        """Aplica el evento. Devuelve False si ya estaba aplicado (relectura)."""
        with self._lock:
            if self._ya_aplicado(origen):
                return False
            previo = self._pedidos.get(evento.pedido_id)
            estado_previo = previo["estado"] if previo else None

            if evento.tipo == "creado":
                if estado_previo is None:
                    self._estados["pendiente"] += 1
                    self._pedidos[evento.pedido_id] = {"estado": "pendiente", "monto": evento.monto_total, "items": evento.items}
            elif evento.tipo in ("confirmado", "cancelado"):
                nuevo = "confirmado" if evento.tipo == "confirmado" else "cancelado"
                if estado_previo in (None, "pendiente"):
                    if estado_previo == "pendiente":
                        self._estados["pendiente"] -= 1
                    self._estados[nuevo] += 1
                    self._pedidos[evento.pedido_id] = {"estado": nuevo, "monto": evento.monto_total, "items": evento.items}
                    if nuevo == "confirmado":
                        self._contabilizar_venta(evento)
                # un pedido ya confirmado/cancelado no cambia de estado (transicion invalida: se ignora)

            self._ultimo_pedido_en = evento.ocurrido_en
            self._marcar(origen)
            return True

    def _contabilizar_venta(self, evento: EventoPedidoRecibido) -> None:
        self._ingresos += evento.monto_total
        for item in evento.items:
            self._unidades[item.sku] += item.cantidad
            self._ingresos_sku[item.sku] += item.cantidad * item.precio_unitario
        hora = evento.ocurrido_en.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:00:00Z")
        bucket = self._por_hora.setdefault(hora, {"hora": hora, "pedidos": 0, "ingresos": 0.0})
        bucket["pedidos"] += 1
        bucket["ingresos"] += evento.monto_total
        while len(self._por_hora) > MAX_HORAS:
            self._por_hora.popitem(last=False)

    def registrar_movimiento(self, evento: EventoMovimientoRecibido, origen: Origen) -> bool:
        with self._lock:
            if self._ya_aplicado(origen):
                return False
            self._movimientos[evento.tipo] += 1
            self._stock[evento.sku] = {
                "sku": evento.sku,
                "stock_disponible": evento.stock_disponible,
                "stock_reservado": evento.stock_reservado,
                "stock_vendible": evento.stock_vendible,
                "umbral_minimo": evento.umbral_minimo,
                "bajo_umbral": evento.umbral_minimo is not None and evento.stock_disponible <= evento.umbral_minimo,
                "actualizado_en": evento.ocurrido_en,
            }
            if evento.tipo == "stock_bajo":
                self._alertas.append({
                    "sku": evento.sku,
                    "stock_disponible": evento.stock_disponible,
                    "umbral_minimo": evento.umbral_minimo,
                    "ocurrido_en": evento.ocurrido_en,
                })
                del self._alertas[:-MAX_ALERTAS]
            self._ultimo_movimiento_en = evento.ocurrido_en
            self._marcar(origen)
            return True

    # ------------------------------------------------------------ metricas del consumo

    def registrar_invalido(self, topico: str) -> None:
        with self._lock:
            self._invalidos[topico] += 1

    def registrar_fallido(self, topico: str) -> None:
        with self._lock:
            self._fallidos[topico] += 1

    # ------------------------------------------------------------ consultas

    def resumen_ventas(self) -> dict:
        with self._lock:
            confirmados = self._estados["confirmado"]
            return {
                "pedidos_pendientes": self._estados["pendiente"],
                "pedidos_confirmados": confirmados,
                "pedidos_cancelados": self._estados["cancelado"],
                "pedidos_totales": sum(self._estados.values()),
                "ingresos_confirmados": round(self._ingresos, 2),
                "ticket_promedio": round(self._ingresos / confirmados, 2) if confirmados else 0.0,
                "ultimo_evento_en": self._ultimo_pedido_en,
            }

    def ventas_por_hora(self) -> List[dict]:
        with self._lock:
            return [{**b, "ingresos": round(b["ingresos"], 2)} for b in self._por_hora.values()]

    def productos_top(self, limite: int = 5) -> List[dict]:
        with self._lock:
            ranking = sorted(self._unidades.items(), key=lambda kv: (-kv[1], kv[0]))[:limite]
            return [
                {"sku": sku, "unidades_vendidas": u, "ingresos": round(self._ingresos_sku[sku], 2)}
                for sku, u in ranking
            ]

    def estado_stock(self, solo_bajo_umbral: bool = False) -> List[dict]:
        with self._lock:
            filas = [dict(s) for s in self._stock.values()]
        if solo_bajo_umbral:
            filas = [f for f in filas if f["bajo_umbral"]]
        return sorted(filas, key=lambda f: f["sku"])

    def alertas_stock(self) -> List[dict]:
        with self._lock:
            return list(reversed(self._alertas))  # la mas reciente primero

    def metricas(self) -> dict:
        with self._lock:
            return {
                "iniciado_en": self._inicio,
                "mensajes_consumidos": dict(self._consumidos),
                "mensajes_invalidos": dict(self._invalidos),
                "mensajes_fallidos": dict(self._fallidos),
                "movimientos_por_tipo": dict(self._movimientos),
                "ultimo_offset_por_particion": {f"{t}-{p}": o for (t, p), o in sorted(self._offsets.items())},
                "ultimo_movimiento_en": self._ultimo_movimiento_en,
            }
