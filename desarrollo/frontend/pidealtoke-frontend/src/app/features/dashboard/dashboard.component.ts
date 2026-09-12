import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div style="padding: 2rem;">
      <h2>Bienvenido a PideAlToke</h2>
      <div *ngIf="user">
        <p><strong>Nombre:</strong> {{ user.name }}</p>
        <p><strong>Correo:</strong> {{ user.username }}</p>
      </div>
      <button (click)="onLogout()">Cerrar Sesión</button>
    </div>
  `
})
export class DashboardComponent implements OnInit {
  private authService = inject(AuthService);
  user: any = null;

  ngOnInit(): void {
    this.user = this.authService.getAccount();
  }

  onLogout(): void {
    this.authService.logout();
  }
}