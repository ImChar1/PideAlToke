import { Component, inject, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { InventarioService } from './services/inventario.service';
import { CatalogoService } from '../catalogo/services/catalogo.service';
import { AuthService } from '../../core/auth/auth.service';
import { ProductoInventario } from './models/inventario.model';
import { CrearProductoPayload } from '../catalogo/models/producto.model';

interface NuevoProductoForm {
  sku: string;
  nombre: string;
  descripcion: string;
  precio: number | null;
  categoria: string;
  imagen_url: string;
  cantidad_disponible: number | null;
  umbral_minimo: number | null;
}

const FORM_VACIO: NuevoProductoForm = {
  sku: '',
  nombre: '',
  descripcion: '',
  precio: null,
  categoria: '',
  imagen_url: '',
  cantidad_disponible: 0,
  umbral_minimo: null
};

@Component({
  selector: 'app-inventario',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './inventario.component.html',
  styleUrl: './inventario.component.css'
})
export class InventarioComponent implements OnInit {
  private inventarioService = inject(InventarioService);
  private catalogoService = inject(CatalogoService);
  private authService = inject(AuthService);

  productos = signal<ProductoInventario[]>([]);
  loading = signal(true);
  error = signal<string | null>(null);

  soloBajoStock = signal(false);
  mostrarFormulario = signal(false);
  guardando = signal(false);
  errorFormulario = signal<string | null>(null);
  eliminandoId = signal<number | null>(null);

  form: NuevoProductoForm = { ...FORM_VACIO };

  esAdmin = this.authService.isAdmin();

  esBajoStock = (item: ProductoInventario): boolean =>
    item.umbral_minimo != null && item.cantidad_disponible <= item.umbral_minimo;

  totalBajoStock = computed(() => this.productos().filter(this.esBajoStock).length);

  itemsFiltrados = computed(() =>
    this.soloBajoStock() ? this.productos().filter(this.esBajoStock) : this.productos()
  );

  ngOnInit(): void {
    this.cargarDatos();
  }

  // Combina ms-catalogo (nombre/precio/estado) con ms-inventario (stock) por SKU,
  // ya que son recursos separados por diseño en la arquitectura de microservicios.
  cargarDatos(): void {
    this.loading.set(true);
    this.error.set(null);

    forkJoin({
      productos: this.catalogoService.getProducts(),
      inventario: this.inventarioService.getInventario()
    }).subscribe({
      next: ({ productos, inventario }) => {
        const stockPorSku = new Map(inventario.map(i => [i.sku, i]));

        const combinado: ProductoInventario[] = productos.map(p => {
          const stock = stockPorSku.get(p.sku);
          return {
            productoId: p.id,
            sku: p.sku,
            nombre: p.nombre,
            categoria: p.categoria,
            precio: p.precio,
            activo: p.activo,
            cantidad_disponible: stock?.cantidad_disponible ?? 0,
            cantidad_reservada: stock?.cantidad_reservada ?? 0,
            umbral_minimo: stock?.umbral_minimo ?? null
          };
        });

        this.productos.set(combinado);
        this.loading.set(false);
      },
      error: (err) => {
        console.error('Error cargando inventario/catalogo:', err);
        this.error.set('No se pudo conectar con ms-inventario o ms-catalogo.');
        this.loading.set(false);
      }
    });
  }

  toggleFiltro(): void {
    this.soloBajoStock.set(!this.soloBajoStock());
  }

  toggleFormulario(): void {
    this.mostrarFormulario.set(!this.mostrarFormulario());
    this.errorFormulario.set(null);
    if (!this.mostrarFormulario()) {
      this.form = { ...FORM_VACIO };
    }
  }

  guardarProducto(): void {
    if (!this.form.sku.trim() || !this.form.nombre.trim() || !this.form.precio || this.form.precio <= 0) {
      this.errorFormulario.set('SKU, nombre y precio (mayor a 0) son obligatorios.');
      return;
    }

    this.guardando.set(true);
    this.errorFormulario.set(null);

    const payloadProducto: CrearProductoPayload = {
      sku: this.form.sku.trim(),
      nombre: this.form.nombre.trim(),
      descripcion: this.form.descripcion.trim() || undefined,
      precio: this.form.precio,
      categoria: this.form.categoria.trim() || undefined,
      imagen_url: this.form.imagen_url.trim() || undefined
    };

    // Paso 1: crear el producto en ms-catalogo.
    this.catalogoService.crearProducto(payloadProducto).subscribe({
      next: () => {
        // Paso 2: crear el registro de stock en ms-inventario con el mismo SKU.
        this.inventarioService
          .crearInventario({
            sku: payloadProducto.sku,
            cantidad_disponible: this.form.cantidad_disponible ?? 0,
            umbral_minimo: this.form.umbral_minimo
          })
          .subscribe({
            next: () => {
              this.guardando.set(false);
              this.mostrarFormulario.set(false);
              this.form = { ...FORM_VACIO };
              this.cargarDatos();
            },
            error: (err) => {
              this.guardando.set(false);
              // El producto ya se creó en catalogo aunque falle este paso; refrescamos
              // igual para reflejarlo (aparecerá con stock 0 hasta reintentar).
              this.cargarDatos();
              this.errorFormulario.set(
                this.mensajeError(err, 'El producto se creó, pero no se pudo registrar su stock inicial.')
              );
            }
          });
      },
      error: (err) => {
        this.guardando.set(false);
        this.errorFormulario.set(this.mensajeError(err, 'No se pudo crear el producto.'));
      }
    });
  }

  eliminarProducto(item: ProductoInventario): void {
    if (!confirm(`¿Eliminar "${item.nombre}" del catálogo? Dejará de mostrarse a los clientes.`)) {
      return;
    }

    this.eliminandoId.set(item.productoId);
    this.error.set(null);

    // Baja lógica en ms-catalogo (marca activo=false); no hay endpoint de borrado
    // en ms-inventario, así que el registro de stock queda huérfano pero inofensivo.
    this.catalogoService.eliminarProducto(item.productoId).subscribe({
      next: () => {
        this.eliminandoId.set(null);
        this.cargarDatos();
      },
      error: (err) => {
        this.eliminandoId.set(null);
        this.error.set(this.mensajeError(err, 'No se pudo eliminar el producto.'));
      }
    });
  }

  private mensajeError(err: any, fallback: string): string {
    if (err.status === 409) {
      return 'Ya existe un producto con ese SKU.';
    }
    if (err.status === 403) {
      return 'Tu cuenta no tiene el rol ADMIN necesario para esta acción (se asigna en Azure AD).';
    }
    if (err.status === 401) {
      return 'Tu sesión no es válida. Vuelve a iniciar sesión.';
    }
    return fallback;
  }
}
