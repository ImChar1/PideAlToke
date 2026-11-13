import { Component, inject, OnInit } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';
import { CartService } from '../../../core/carrito/cart.service';

@Component({
  selector: 'app-main-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './main-layout.component.html',
  styleUrl: './main-layout.component.css'
})
export class MainLayoutComponent implements OnInit {
  private authService = inject(AuthService);
  private cartService = inject(CartService);

  userName = '';
  cartCount = this.cartService.totalCount;

  ngOnInit(): void {
    const account = this.authService.getAccount();
    this.userName = account?.name || 'Usuario';
  }

  // La analitica es solo para ADMIN (el backend responde 403 al resto): el link no se muestra a los demas.
  get esAdmin(): boolean {
    return this.authService.isAdmin();
  }

  get iniciales(): string {
    return this.userName
      .split(' ')
      .filter(Boolean)
      .slice(0, 2)
      .map(p => p.charAt(0).toUpperCase())
      .join('');
  }

  onLogout(): void {
    this.authService.logout();
  }
}
