export interface ItemPedido {
  sku: string;
  cantidad: number;
  precio_unitario: number;
}

export interface CrearPedidoPayload {
  cliente_id: string;
  items: ItemPedido[];
}

export interface Pedido {
  id: number;
  cliente_id: string;
  monto_total: number;
  estado: string;
  items: ItemPedido[];
  fecha_creacion: string;
}
