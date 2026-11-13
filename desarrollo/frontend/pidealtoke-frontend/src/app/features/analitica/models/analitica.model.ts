// Contratos de ms-analitica (Kafka) y ms-notificaciones (RabbitMQ). Espejo de sus schemas Pydantic.

export interface ResumenVentas {
  pedidos_pendientes: number;
  pedidos_confirmados: number;
  pedidos_cancelados: number;
  pedidos_totales: number;
  ingresos_confirmados: number;
  ticket_promedio: number;
  ultimo_evento_en: string | null;
}

export interface VentasHora {
  hora: string;      // "2026-11-04T15:00:00Z"
  pedidos: number;
  ingresos: number;
}

export interface ProductoTop {
  sku: string;
  unidades_vendidas: number;
  ingresos: number;
}

export interface StockSku {
  sku: string;
  stock_disponible: number;
  stock_reservado: number;
  stock_vendible: number;
  umbral_minimo: number | null;
  bajo_umbral: boolean;
  actualizado_en: string;
}

export interface AlertaStock {
  sku: string;
  stock_disponible: number;
  umbral_minimo: number | null;
  ocurrido_en: string;
}

export interface MetricasConsumo {
  iniciado_en: string;
  mensajes_consumidos: Record<string, number>;
  mensajes_invalidos: Record<string, number>;
  mensajes_fallidos: Record<string, number>;
  movimientos_por_tipo: Record<string, number>;
  ultimo_offset_por_particion: Record<string, number>;
  ultimo_movimiento_en: string | null;
}

export type TipoNotificacion = 'pedido_confirmado' | 'pedido_cancelado' | 'stock_bajo';

export interface Notificacion {
  id: string;
  tipo: TipoNotificacion;
  titulo: string;
  mensaje: string;
  referencia: string;
  creada_en: string;
}
