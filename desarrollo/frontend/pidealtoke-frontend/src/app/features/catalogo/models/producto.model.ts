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