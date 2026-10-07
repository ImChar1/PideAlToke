import { TestBed } from '@angular/core/testing';
import { MsalService } from '@azure/msal-angular';
import { LoginForm } from './login-form';

describe('LoginForm', () => {
  const loginRedirect = vi.fn();
  const msalMock = {
    instance: { initialize: vi.fn(() => Promise.resolve()) },
    loginRedirect,
  };

  beforeEach(async () => {
    vi.clearAllMocks();
    await TestBed.configureTestingModule({
      imports: [LoginForm],
      providers: [{ provide: MsalService, useValue: msalMock }],
    }).compileComponents();
  });

  it('should create', () => {
    const fixture = TestBed.createComponent(LoginForm);
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('login inicializa MSAL y lanza el loginRedirect', async () => {
    const fixture = TestBed.createComponent(LoginForm);
    fixture.componentInstance.login();
    await Promise.resolve(); // deja resolver el initialize()
    await Promise.resolve();
    expect(msalMock.instance.initialize).toHaveBeenCalled();
    expect(loginRedirect).toHaveBeenCalledTimes(1);
  });
});
