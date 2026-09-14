import { Routes } from '@angular/router';
import { MsalGuard } from '@azure/msal-angular';
import { LoginPageComponent } from './features/auth/pages/login-page/login-page';
import { RegisterPageComponent } from './features/auth/pages/register-page/register-page';
import { MainLayoutComponent } from './features/layout/main-layout/main-layout.component';
import { DashboardComponent } from './features/dashboard/dashboard.component';

export const routes: Routes = [
  { path: 'login', component: LoginPageComponent },
  { path: 'register', component: RegisterPageComponent },
  {
    path: '',
    component: MainLayoutComponent,
    canActivate: [MsalGuard],
    children: [
      { path: 'dashboard', component: DashboardComponent },
      { path: 'catalogo', loadComponent: () => import('./features/catalogo/catalogo.component').then(m => m.CatalogoComponent) },
      { path: 'inventario', loadComponent: () => import('./features/inventario/inventario.component').then(m => m.InventarioComponent) },
      { path: 'pedidos', loadComponent: () => import('./features/pedidos/pedidos.component').then(m => m.PedidosComponent) },
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' }
    ]
  },
  { path: '**', redirectTo: 'login' }
];
