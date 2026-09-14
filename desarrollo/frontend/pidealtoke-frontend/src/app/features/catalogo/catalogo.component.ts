import { Component, inject, OnInit } from '@angular/core';
import { CatalogoService } from './services/catalogo.service';
import { CartService } from '../../core/carrito/cart.service';
import { Producto } from './models/producto.model';
import { ProductCardComponent } from '../../shared/components/product-card/product-card.component';

@Component({
  selector: 'app-catalogo',
  standalone: true,
  imports: [ProductCardComponent],
  templateUrl: './catalogo.component.html',
  styleUrl: './catalogo.component.css'
})
export class CatalogoComponent implements OnInit {
  private catalogoService = inject(CatalogoService);
  private cartService = inject(CartService);
  
  productos: Producto[] = [];
  loading = true;
  error: string | null = null;

  ngOnInit(): void {
    this.catalogoService.getProducts().subscribe({
      next: (res: Producto[]) => {
        this.productos = res;
        this.loading = false;
      },
      error: (err) => {
        console.error('Error al cargar productos:', err);
        this.error = 'No se pudieron cargar los productos del catálogo.';
        this.loading = false;
      }
    });
  }

  onAddToCart(producto: Producto): void {
    this.cartService.agregarProducto(producto);
    console.log('Carrito actualizado:', this.cartService.items());
  }
}