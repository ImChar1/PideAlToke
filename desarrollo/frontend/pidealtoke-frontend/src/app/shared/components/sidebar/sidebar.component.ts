import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  template: `
    <aside class="sidebar">
      <nav>
        <a routerLink="/dashboard" routerLinkActive="active">Dashboard</a>
        <a routerLink="/catalogo" routerLinkActive="active">Catálogo</a>
        <a routerLink="/inventario" routerLinkActive="active">Inventario</a>
        <a routerLink="/pedidos" routerLinkActive="active">Pedidos</a>
      </nav>
    </aside>
  `,
  styles: [`
    .sidebar { width: 220px; background: #f8fafc; height: calc(100vh - 60px); border-right: 1px solid #e2e8f0; }
    nav { display: flex; flex-direction: column; padding: 1rem 0; }
    a { padding: 0.75rem 1.5rem; text-decoration: none; color: #334155; }
    a.active { background: #e2e8f0; font-weight: bold; color: #0f172a; }
  `]
})
export class SidebarComponent {}