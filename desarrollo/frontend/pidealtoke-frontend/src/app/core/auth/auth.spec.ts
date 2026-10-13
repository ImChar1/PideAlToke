import { TestBed } from '@angular/core/testing';
import { MsalService } from '@azure/msal-angular';
import { AuthService } from './auth.service';
import { environment } from '../../../environments/environment';

describe('AuthService', () => {
  let activeAccount: any = null;
  let allAccounts: any[] = [];
  const loginRedirect = vi.fn();
  const msalMock = {
    instance: {
      getActiveAccount: () => activeAccount,
      getAllAccounts: () => allAccounts,
      initialize: () => Promise.resolve(),
    },
    loginRedirect,
  };

  let service: AuthService;

  beforeEach(() => {
    activeAccount = null;
    allAccounts = [];
    TestBed.configureTestingModule({
      providers: [{ provide: MsalService, useValue: msalMock }],
    });
    service = TestBed.inject(AuthService);
  });

  it('sin cuentas: no esta logueado y no es admin', () => {
    expect(service.isLoggedIn()).toBe(false);
    expect(service.getRoles()).toEqual([]);
    expect(service.isAdmin()).toBe(false);
  });

  it('prioriza la cuenta activa sobre la primera del cache', () => {
    activeAccount = { username: 'activa@x.com' };
    allAccounts = [{ username: 'vieja@x.com' }];
    expect(service.getAccount()?.username).toBe('activa@x.com');
  });

  it('cae a la primera cuenta del cache si no hay activa', () => {
    allAccounts = [{ username: 'primera@x.com' }];
    expect(service.getAccount()?.username).toBe('primera@x.com');
    expect(service.isLoggedIn()).toBe(true);
  });

  it('isAdmin es true solo con el rol ADMIN en el token', () => {
    activeAccount = { idTokenClaims: { roles: ['CLIENTE'] } };
    expect(service.isAdmin()).toBe(false);
    activeAccount = { idTokenClaims: { roles: ['ADMIN'] } };
    expect(service.isAdmin()).toBe(true);
  });

  it('login pide el scope de la API (el mismo que usa el interceptor), no scopes de Graph', async () => {
    service.login();
    await Promise.resolve();
    await Promise.resolve();
    expect(loginRedirect).toHaveBeenCalledWith({ scopes: [environment.azure.apiScope] });
  });

  it('el scope de la API apunta al client id de la app', () => {
    expect(environment.azure.apiScope).toBe(`api://${environment.azure.clientId}/access_as_user`);
  });
});
