import { Component, inject } from '@angular/core';
import { MsalService } from '@azure/msal-angular';
import { environment } from '../../../../../environments/environment';

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
    this.msalService.instance.initialize().then(() => {
      this.msalService.loginRedirect({
        scopes: [environment.azure.apiScope]
      });
    }).catch(error => {
      console.error('Error al inicializar MSAL:', error);
    });
  }
}