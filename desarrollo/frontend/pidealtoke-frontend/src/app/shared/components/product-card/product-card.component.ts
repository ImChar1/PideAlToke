import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CurrencyPipe } from '@angular/common';
import { Producto } from '../../../features/catalogo/models/producto.model';

@Component({
  selector: 'app-product-card',
  standalone: true,
  imports: [CurrencyPipe],
  template: `
    <div class="card">
      <h3>{{ product.nombre }}</h3>
      <p class="description">{{ product.descripcion }}</p>
      <div class="card-footer">
        <span class="price">{{ product.precio | currency:'CLP':'symbol-narrow':'1.0-0' }}</span>
        <button (click)="addToCart.emit(product)">Agregar al Pedido</button>
      </div>
    </div>
  `,
  styles: [`
    .card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 1.2rem; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    .description { color: #64748b; font-size: 0.9rem; margin: 0.5rem 0 1rem; min-height: 40px; }
    .card-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 1rem; }
    .price { font-weight: bold; font-size: 1.1rem; color: #0f172a; }
    button { background: #2563eb; color: white; border: none; padding: 0.5rem 0.8rem; border-radius: 4px; cursor: pointer; }
    button:hover { background: #1d4ed8; }
  `]
})
export class ProductCardComponent {
  @Input({ required: true }) product!: Producto;
  @Output() addToCart = new EventEmitter<Producto>();
}