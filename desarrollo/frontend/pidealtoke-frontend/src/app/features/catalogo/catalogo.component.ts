import { Component, inject, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { CatalogoService } from './services/catalogo.service';
import { CartService } from '../../core/carrito/cart.service';
import { Producto } from './models/producto.model';

@Component({
  selector: 'app-catalogo',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './catalogo.component.html',
  styleUrl: './catalogo.component.css'
})
export class CatalogoComponent implements OnInit {
  private catalogoService = inject(CatalogoService);
  private cartService = inject(CartService);

  productos = signal<Producto[]>([]);
  loading = signal(true);
  error = signal<string | null>(null);

  busqueda = signal('');
  categoriaActiva = signal<string | null>(null);

  // Pequeño feedback visual transitorio al agregar un producto
  ultimoAgregado = signal<string | null>(null);
  private timeoutToast?: ReturnType<typeof setTimeout>;

  cartCount = this.cartService.totalCount;

  categorias = computed(() => {
    const set = new Set(
      this.productos()
        .filter(p => p.activo)
        .map(p => p.categoria)
        .filter((c): c is string => !!c)
    );
    return Array.from(set);
  });

  productosFiltrados = computed(() => {
    const texto = this.busqueda().trim().toLowerCase();
    const categoria = this.categoriaActiva();

    return this.productos().filter(p => {
      // Los productos dados de baja desde Inventario quedan con activo=false
      // en ms-catalogo (baja logica); no deben mostrarse en el catalogo publico.
      if (!p.activo) return false;
      const coincideTexto = !texto || p.nombre.toLowerCase().includes(texto);
      const coincideCategoria = !categoria || p.categoria === categoria;
      return coincideTexto && coincideCategoria;
    });
  });

  ngOnInit(): void {
    this.catalogoService.getProducts().subscribe({
      next: (res) => {
        this.productos.set(res);
        this.loading.set(false);
      },
      error: (err) => {
        console.error('Error al cargar productos:', err);
        this.error.set('No se pudieron cargar los productos del catálogo.');
        this.loading.set(false);
      }
    });
  }

  filtrarPorCategoria(categoria: string | null): void {
    this.categoriaActiva.set(categoria);
  }

  onAddToCart(producto: Producto): void {
    this.cartService.agregarProducto(producto);

    this.ultimoAgregado.set(producto.nombre);
    clearTimeout(this.timeoutToast);
    this.timeoutToast = setTimeout(() => this.ultimoAgregado.set(null), 2200);
  }
}
