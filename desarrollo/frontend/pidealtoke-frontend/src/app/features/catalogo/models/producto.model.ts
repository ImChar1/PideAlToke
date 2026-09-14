export interface Producto {
  id: number;
  sku: string;
  nombre: string;
  descripcion: string;
  precio: number;
  categoria?: string;
  imagen_url?: string;
  activo: boolean;
}

// Payload para dar de alta un producto nuevo en ms-catalogo (POST /productos)
export interface CrearProductoPayload {
  sku: string;
  nombre: string;
  descripcion?: string;
  precio: number;
  categoria?: string;
  imagen_url?: string;
}