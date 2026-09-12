import { Routes } from '@angular/router';
import { RegisterPageComponent } from './features/auth/pages/register-page/register-page';
import { LoginPageComponent } from './features/auth/pages/login-page/login-page';
import { MsalGuard } from '@azure/msal-angular';

export const routes: Routes = [
  { path: 'login', component: LoginPageComponent },
  { path: 'register', component: RegisterPageComponent },
  { 
    path: 'dashboard', 
    loadComponent: () => import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent),
    canActivate: [MsalGuard]
  },
  { path: '', redirectTo: 'login', pathMatch: 'full' },
  { path: '**', redirectTo: 'login' }
];