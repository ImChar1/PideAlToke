import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../../../core/auth/auth.service';

@Component({
  selector: 'app-register-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './register-page.html',
  styleUrl: './register-page.css'
})
export class RegisterPageComponent {
  private authService = inject(AuthService);

  onRegister(): void {
    // Redirige a Microsoft Entra ID donde el usuario se autentica o registra en el Tenant
    this.authService.login();
  }
}