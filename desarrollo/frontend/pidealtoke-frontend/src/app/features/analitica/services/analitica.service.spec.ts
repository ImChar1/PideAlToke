import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { AnaliticaService } from './analitica.service';
import { environment } from '../../../../environments/environment';

describe('AnaliticaService', () => {
  let service: AnaliticaService;
  let http: HttpTestingController;
  const analitica = `${environment.apiGatewayUrl}/api/v1/analitica`;
  const notificaciones = `${environment.apiGatewayUrl}/api/v1/notificaciones`;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(AnaliticaService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('getResumenVentas hace GET a /analitica/ventas/resumen', () => {
    service.getResumenVentas().subscribe();
    const req = http.expectOne(`${analitica}/ventas/resumen`);
    expect(req.request.method).toBe('GET');
    req.flush({});
  });

  it('getVentasPorHora y getMetricas apuntan a su ruta', () => {
    service.getVentasPorHora().subscribe();
    service.getMetricas().subscribe();
    http.expectOne(`${analitica}/ventas/por-hora`).flush([]);
    http.expectOne(`${analitica}/metricas`).flush({});
  });

  it('getProductosTop envia el limite como query param', () => {
    service.getProductosTop(3).subscribe();
    const req = http.expectOne(r => r.url === `${analitica}/productos/top`);
    expect(req.request.params.get('limite')).toBe('3');
    req.flush([]);
  });

  it('getEstadoStock envia bajo_umbral (false por defecto)', () => {
    service.getEstadoStock().subscribe();
    service.getEstadoStock(true).subscribe();
    const [a, b] = http.match(r => r.url === `${analitica}/stock/estado`);
    expect(a.request.params.get('bajo_umbral')).toBe('false');
    expect(b.request.params.get('bajo_umbral')).toBe('true');
    a.flush([]); b.flush([]);
  });

  it('getAlertasStock hace GET a /analitica/stock/alertas', () => {
    service.getAlertasStock().subscribe();
    http.expectOne(`${analitica}/stock/alertas`).flush([]);
  });

  it('getNotificaciones pide a /notificaciones SIN barra final (la ruta del gateway es sin ella)', () => {
    service.getNotificaciones(7).subscribe();
    const req = http.expectOne(r => r.url === notificaciones);
    expect(req.request.url.endsWith('/')).toBe(false);
    expect(req.request.params.get('limite')).toBe('7');
    req.flush([]);
  });
});
