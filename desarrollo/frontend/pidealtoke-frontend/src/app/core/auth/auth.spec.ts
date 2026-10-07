import { TestBed } from '@angular/core/testing';
import { MsalService } from '@azure/msal-angular';
import { AuthService } from './auth.service';

describe('AuthService', () => {
  let activeAccount: any = null;
  let allAccounts: any[] = [];
  const msalMock = {
    instance: {
      getActiveAccount: () => activeAccount,
      getAllAccounts: () => allAccounts,
    },
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
});
