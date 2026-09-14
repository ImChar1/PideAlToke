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
    return this.getAccount() !== null;
  }

  getAccount() {
    // Prioriza la cuenta activa (la que MSAL marcó tras el último login exitoso,
    // ver app.ts -> setActiveAccount). Si por algún motivo no hay cuenta activa
    // marcada, cae a la primera del cache como respaldo.
    const activa = this.msalService.instance.getActiveAccount();
    if (activa) return activa;

    const accounts = this.msalService.instance.getAllAccounts();
    return accounts.length > 0 ? accounts[0] : null;
  }

  // Los endpoints de escritura de ms-catalogo y ms-inventario exigen el rol
  // "ADMIN" dentro del JWT (App Role asignado en Azure AD Enterprise Application).
  // Si el usuario no tiene ese rol asignado, el backend responde 403 aunque el
  // token sea válido.
  getRoles(): string[] {
    const account = this.getAccount();
    const claims = account?.idTokenClaims as { roles?: string[] } | undefined;
    return claims?.roles ?? [];
  }

  isAdmin(): boolean {
    return this.getRoles().includes('ADMIN');
  }
}