import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { PedidosService } from './pedidos.service';
import { environment } from '../../../../environments/environment';

describe('PedidosService', () => {
  let service: PedidosService;
  let http: HttpTestingController;
  const base = `${environment.apiGatewayUrl}/api/v1/pedidos`;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(PedidosService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('crearPedido hace POST a /api/v1/pedidos (sin barra final) enviando solo sku y cantidad', () => {
    const payload = { items: [{ sku: 'S', cantidad: 1 }] };
    service.crearPedido(payload).subscribe();
    const req = http.expectOne(base);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual(payload);
    expect(JSON.stringify(req.request.body)).not.toContain('precio');
    expect(JSON.stringify(req.request.body)).not.toContain('cliente_id');
    req.flush({});
  });

  it('obtenerPedido hace GET a /api/v1/pedidos/{id}', () => {
    service.obtenerPedido(7).subscribe();
    const req = http.expectOne(`${base}/7`);
    expect(req.request.method).toBe('GET');
    req.flush({});
  });

  it('listarPedidos pide solo los propios por defecto', () => {
    service.listarPedidos().subscribe();
    const req = http.expectOne(base);
    expect(req.request.method).toBe('GET');
    expect(req.request.params.has('todos')).toBe(false);
    req.flush([]);
  });

  it('listarPedidos(true) agrega ?todos=true', () => {
    service.listarPedidos(true).subscribe();
    const req = http.expectOne(r => r.url === base && r.params.get('todos') === 'true');
    expect(req.request.method).toBe('GET');
    req.flush([]);
  });

  it('cancelarPedido hace POST a /{id}/cancelar', () => {
    service.cancelarPedido(3).subscribe();
    const req = http.expectOne(`${base}/3/cancelar`);
    expect(req.request.method).toBe('POST');
    req.flush({});
  });

  it('confirmarPedido hace POST a /{id}/confirmar', () => {
    service.confirmarPedido(3).subscribe();
    const req = http.expectOne(`${base}/3/confirmar`);
    expect(req.request.method).toBe('POST');
    req.flush({});
  });
});
