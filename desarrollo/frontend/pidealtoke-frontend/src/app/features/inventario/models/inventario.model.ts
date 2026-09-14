export interface ItemInventario {
  id: number;
  sku: string;
  cantidad_disponible: number;
  cantidad_reservada: number;
  umbral_minimo?: number | null;
  fecha_creacion?: string;
  fecha_actualizacion?: string;
}