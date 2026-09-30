import { Injectable, signal, computed } from '@angular/core';
import { Producto } from '../../features/catalogo/models/producto.model';

export interface CartItem {
  producto: Producto;
  cantidad: number;
}

@Injectable({
  providedIn: 'root'
})
export class CartService {
  // Estado reactivo del carrito usando Angular Signals
  items = signal<CartItem[]>([]);

  // Contador total de productos para la barra superior / badge
  totalCount = computed(() => 
    this.items().reduce((acc, item) => acc + item.cantidad, 0)
  );

  agregarProducto(producto: Producto): void {
    const actual = this.items();
    const index = actual.findIndex(i => i.producto.id === producto.id);

    if (index > -1) {
      const actualizado = [...actual];
      actualizado[index].cantidad += 1;
      this.items.set(actualizado);
    } else {
      this.items.set([...actual, { producto, cantidad: 1 }]);
    }
  }
}