export interface ItemInventario {
  id: number;
  sku: string;
  cantidad_disponible: number;
  cantidad_reservada: number;
  umbral_minimo?: number | null;
  fecha_creacion?: string;
  fecha_actualizacion?: string;
}

// Payload para dar de alta el registro de stock en ms-inventario (POST /inventario)
export interface CrearInventarioPayload {
  sku: string;
  cantidad_disponible: number;
  umbral_minimo?: number | null;
}

// Vista combinada usada solo en el frontend: junta el producto (ms-catalogo)
// con su stock (ms-inventario) por SKU, ya que son recursos separados por diseño.
export interface ProductoInventario {
  productoId: number;
  sku: string;
  nombre: string;
  categoria?: string;
  precio: number;
  activo: boolean;
  cantidad_disponible: number;
  cantidad_reservada: number;
  umbral_minimo?: number | null;
}