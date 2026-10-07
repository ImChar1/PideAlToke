import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { MsalService } from '@azure/msal-angular';
import { of } from 'rxjs';
import { AppComponent } from './app';

describe('AppComponent', () => {
  const setActiveAccount = vi.fn();
  const msalMock = {
    handleRedirectObservable: vi.fn(() => of(null)),
    instance: { setActiveAccount },
  };

  beforeEach(async () => {
    vi.clearAllMocks();
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [provideRouter([{ path: 'dashboard', children: [] }]), { provide: MsalService, useValue: msalMock }],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(AppComponent);
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('procesa la redireccion de MSAL al iniciar', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    expect(msalMock.handleRedirectObservable).toHaveBeenCalledTimes(1);
  });

  it('marca la cuenta activa cuando MSAL devuelve un resultado de login', () => {
    const account = { username: 'a@b.com' };
    msalMock.handleRedirectObservable.mockReturnValueOnce(of({ account }) as any);
    const fixture = TestBed.createComponent(AppComponent);
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate');
    fixture.detectChanges();
    expect(setActiveAccount).toHaveBeenCalledWith(account);
    expect(navigate).toHaveBeenCalledWith(['/dashboard']);
  });
});
