import { Component, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { CartService } from '../../core/carrito/cart.service';
import { AuthService } from '../../core/auth/auth.service';
import { PedidosService } from './services/pedidos.service';
import { Pedido } from './models/pedido.model';
import { Producto } from '../catalogo/models/producto.model';

@Component({
  selector: 'app-pedidos',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './pedidos.component.html',
  styleUrl: './pedidos.component.css'
})
export class PedidosComponent {
  private cart = inject(CartService);
  private authService = inject(AuthService);
  private pedidosService = inject(PedidosService);

  items = this.cart.items;

  total = computed(() =>
    this.items().reduce((acc, i) => acc + i.producto.precio * i.cantidad, 0)
  );

  enviando = signal(false);
  error = signal<string | null>(null);
  pedidoConfirmado = signal<Pedido | null>(null);

  incrementar(producto: Producto): void {
    const actualizado = this.items().map(i =>
      i.producto.id === producto.id ? { ...i, cantidad: i.cantidad + 1 } : i
    );
    this.cart.items.set(actualizado);
  }

  decrementar(producto: Producto): void {
    const actualizado = this.items()
      .map(i => (i.producto.id === producto.id ? { ...i, cantidad: i.cantidad - 1 } : i))
      .filter(i => i.cantidad > 0);
    this.cart.items.set(actualizado);
  }

  quitar(producto: Producto): void {
    this.cart.items.set(this.items().filter(i => i.producto.id !== producto.id));
  }

  confirmarPedido(): void {
    const cuenta = this.authService.getAccount();
    const clienteId = cuenta?.username || cuenta?.name || 'cliente-anonimo';

    this.enviando.set(true);
    this.error.set(null);

    this.pedidosService
      .crearPedido({
        cliente_id: clienteId,
        items: this.items().map(i => ({
          sku: i.producto.sku,
          cantidad: i.cantidad,
          precio_unitario: i.producto.precio
        }))
      })
      .subscribe({
        next: (pedido) => {
          this.pedidoConfirmado.set(pedido);
          this.cart.items.set([]);
          this.enviando.set(false);
        },
        error: (err) => {
          this.enviando.set(false);
          if (err.status === 409) {
            this.error.set('No hay stock suficiente para uno o más productos de tu pedido.');
          } else if (err.status === 503) {
            this.error.set('El servicio de inventario no está disponible en este momento. Intenta nuevamente.');
          } else if (err.status === 401 || err.status === 403) {
            this.error.set('Tu sesión no es válida. Vuelve a iniciar sesión.');
          } else {
            this.error.set('Ocurrió un error al procesar tu pedido. Intenta nuevamente.');
          }
        }
      });
  }

  nuevoPedido(): void {
    this.pedidoConfirmado.set(null);
    this.error.set(null);
  }
}
