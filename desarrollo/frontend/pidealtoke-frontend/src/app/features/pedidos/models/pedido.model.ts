export type EstadoPedido = 'PENDIENTE' | 'CONFIRMADO' | 'CANCELADO';

// Lo que el cliente ENVIA al crear un pedido: solo que compra y cuanto.
// El precio lo define ms-catalogo y el cliente se toma del token (el backend ignora
// cualquier precio_unitario o cliente_id que se mande).
export interface ItemPedidoPayload {
  sku: string;
  cantidad: number;
}

export interface CrearPedidoPayload {
  items: ItemPedidoPayload[];
}

// Lo que el backend DEVUELVE: incluye el precio real que aplico el catalogo.
export interface ItemPedido {
  sku: string;
  cantidad: number;
  precio_unitario: number;
}

export interface Pedido {
  id: number;
  cliente_id: string;
  monto_total: number;
  estado: EstadoPedido;
  items: ItemPedido[];
  fecha_creacion: string;
}
