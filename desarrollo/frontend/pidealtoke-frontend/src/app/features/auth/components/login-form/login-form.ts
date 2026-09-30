import { Component, inject } from '@angular/core';
import { MsalService } from '@azure/msal-angular';

@Component({
  selector: 'app-login-form',
  standalone: true,
  imports: [],
  templateUrl: './login-form.html',
  styleUrl: './login-form.css',
})
export class LoginForm {
  private msalService = inject(MsalService);

  login(): void {
    console.log('---> Clic detectado en el botón de login');
    
    this.msalService.instance.initialize().then(() => {
      this.msalService.loginRedirect({
        scopes: ['user.read']
      });
    }).catch(error => {
      console.error('Error al inicializar MSAL:', error);
    });
  }
}