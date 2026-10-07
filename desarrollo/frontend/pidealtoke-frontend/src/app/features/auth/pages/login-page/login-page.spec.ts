import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AuthService } from '../../../../core/auth/auth.service';
import { LoginPageComponent } from './login-page';

describe('LoginPageComponent', () => {
  const authMock = { login: vi.fn() };

  beforeEach(async () => {
    vi.clearAllMocks();
    await TestBed.configureTestingModule({
      imports: [LoginPageComponent],
      providers: [provideRouter([]), { provide: AuthService, useValue: authMock }],
    }).compileComponents();
  });

  it('should create', () => {
    const fixture = TestBed.createComponent(LoginPageComponent);
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('onLogin delega en AuthService.login', () => {
    const fixture = TestBed.createComponent(LoginPageComponent);
    fixture.componentInstance.onLogin();
    expect(authMock.login).toHaveBeenCalledTimes(1);
  });
});
