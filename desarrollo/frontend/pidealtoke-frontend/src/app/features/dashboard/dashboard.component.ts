import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { UserService } from '../../core/usuarios/user.service';
import { CatalogoService } from '../catalogo/services/catalogo.service';
import { InventarioService } from '../inventario/services/inventario.service';

interface PerfilUsuario {
  email: string;
  rol: string;
  activo: boolean;
  fecha_creacion: string;
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css'
})
export class DashboardComponent implements OnInit {
  private authService = inject(AuthService);
  private userService = inject(UserService);
  private catalogoService = inject(CatalogoService);
  private inventarioService = inject(InventarioService);

  nombre = signal<string>('');
  perfil = signal<PerfilUsuario | null>(null);

  // El rol mostrado en el Dashboard viene siempre del backend (ms-usuarios),
  // que a su vez lo sincroniza en cada /me con el App Role de Azure AD
  // ("ADMIN" o "CLIENTE"). No se lee del token directamente aquí para que
  // el badge y los datos del perfil sean siempre consistentes entre sí.
  esAdmin = computed(() => this.perfil()?.rol === 'ADMIN');

  totalProductos = signal<number | null>(null);
  totalBajoStock = signal<number | null>(null);

  ngOnInit(): void {
    const cuenta = this.authService.getAccount();
    this.nombre.set(cuenta?.name || 'Usuario');

    this.userService.getUserProfile().subscribe({
      next: (data) => this.perfil.set(data),
      error: (err) => console.error('No se pudo obtener el perfil del usuario:', err)
    });

    this.catalogoService.getProducts().subscribe({
      next: (productos) => this.totalProductos.set(productos.length),
      error: () => this.totalProductos.set(null)
    });

    this.inventarioService.getInventario().subscribe({
      next: (items) => {
        const bajoStock = items.filter(
          i => i.umbral_minimo != null && i.cantidad_disponible <= i.umbral_minimo
        ).length;
        this.totalBajoStock.set(bajoStock);
      },
      error: () => this.totalBajoStock.set(null)
    });
  }
}
