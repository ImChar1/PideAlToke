import { Injectable, inject } from '@angular/core';
import { MsalService } from '@azure/msal-angular';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private msalService = inject(MsalService);

  login(): void {
  this.msalService.instance.initialize().then(() => {
    this.msalService.loginRedirect({
      scopes: ['api://f3e5ef16-7ccb-4c9f-bfdd-2b965ecec91d/access_as_user']
    });
  });
}

  logout(): void {
    this.msalService.logoutRedirect({
      postLogoutRedirectUri: 'http://localhost:4200'
    });
  }

  isLoggedIn(): boolean {
    return this.msalService.instance.getAllAccounts().length > 0;
  }

  getAccount() {
    const accounts = this.msalService.instance.getAllAccounts();
    return accounts.length > 0 ? accounts[0] : null;
  }
}