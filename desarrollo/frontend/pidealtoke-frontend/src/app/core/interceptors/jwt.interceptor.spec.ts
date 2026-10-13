import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { MsalService } from '@azure/msal-angular';
import { jwtInterceptor } from './jwt.interceptor';
import { environment } from '../../../environments/environment';

describe('jwtInterceptor', () => {
  let http: HttpClient;
  let controller: HttpTestingController;
  const acquireTokenSilent = vi.fn();
  const cuenta = { username: 'ana@x.com' };

  beforeEach(() => {
    acquireTokenSilent.mockReset();
    acquireTokenSilent.mockResolvedValue({ accessToken: 'token-api' });
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([jwtInterceptor])),
        provideHttpClientTesting(),
        {
          provide: MsalService,
          useValue: {
            instance: {
              getActiveAccount: () => cuenta,
              getAllAccounts: () => [],
              acquireTokenSilent,
            },
          },
        },
      ],
    });
    http = TestBed.inject(HttpClient);
    controller = TestBed.inject(HttpTestingController);
  });

  afterEach(() => controller.verify());

  it('adjunta el access token de la API a las llamadas al gateway', async () => {
    http.get(`${environment.apiGatewayUrl}/api/v1/productos`).subscribe();
    await vi.waitFor(() => expect(acquireTokenSilent).toHaveBeenCalled());

    expect(acquireTokenSilent).toHaveBeenCalledWith({
      scopes: [environment.azure.apiScope],
      account: cuenta,
    });
    const req = controller.expectOne(`${environment.apiGatewayUrl}/api/v1/productos`);
    expect(req.request.headers.get('Authorization')).toBe('Bearer token-api');
    req.flush([]);
  });

  it('no adjunta el token a URLs ajenas al backend', () => {
    http.get('https://otro-sitio.example.com/datos').subscribe();
    const req = controller.expectOne('https://otro-sitio.example.com/datos');
    expect(req.request.headers.has('Authorization')).toBe(false);
    expect(acquireTokenSilent).not.toHaveBeenCalled();
    req.flush({});
  });
});
