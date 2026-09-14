import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AuthService } from '../../core/auth/auth.service';
import { UserService } from '../../core/usuarios/user.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div style="padding: 2rem;">
      <h2>Bienvenido a PideAlToke</h2>
      
      <!-- 1. Datos del Token guardados localmente por Azure -->
      <div *ngIf="user">
        <p><strong>Nombre (Azure):</strong> {{ user.name }}</p>
        <p><strong>Correo (Azure):</strong> {{ user.username }}</p>
      </div>

      <hr style="margin: 1.5rem 0;" />

      <!-- 2. Datos devueltos por el Microservicio Docker en el puerto 8001 -->
      <h3>Respuesta de la API (Docker :8001):</h3>
      <div *ngIf="backendProfile; else loading">
        <pre>{{ backendProfile | json }}</pre>
      </div>
      <ng-template #loading>
        <p>Consultando /api/v1/users/me en el microservicio...</p>
      </ng-template>

      <button (click)="onLogout()" style="margin-top: 1rem;">Cerrar Sesión</button>
    </div>
  `
})
export class DashboardComponent implements OnInit {
  private authService = inject(AuthService);
  private userService = inject(UserService);

  user: any = null;
  backendProfile: any = null;

  ngOnInit(): void {
    // Lee la sesión activa en el navegador
    this.user = this.authService.getAccount();

    // Dispara la llamada HTTP que intercepta el JWT
    this.userService.getUserProfile().subscribe({
      next: (data) => {
        console.log('Respuesta recibida del backend:', data);
        this.backendProfile = data;
      },
      error: (err) => console.error('Error de autenticación con el backend:', err)
    });
  }

  onLogout(): void {
    this.authService.logout();
  }
}