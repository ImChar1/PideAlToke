import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { AnaliticaComponent } from './analitica.component';
import { AuthService } from '../../core/auth/auth.service';
import { environment } from '../../../environments/environment';

const A = `${environment.apiGatewayUrl}/api/v1/analitica`;
const N = `${environment.apiGatewayUrl}/api/v1/notificaciones`;

const RESUMEN = {
  pedidos_pendientes: 1, pedidos_confirmados: 3, pedidos_cancelados: 1, pedidos_totales: 5,
  ingresos_confirmados: 47970, ticket_promedio: 15990, ultimo_evento_en: '2026-11-04T15:30:00Z'
};

const DATOS = (): Record<string, object> => ({
  [`${A}/ventas/resumen`]: RESUMEN,
  [`${A}/ventas/por-hora`]: [
    { hora: '2026-11-04T15:00:00Z', pedidos: 2, ingresos: 30000 },
    { hora: '2026-11-04T16:00:00Z', pedidos: 1, ingresos: 15000 }
  ],
  [`${A}/productos/top`]: [{ sku: 'SKU-001', unidades_vendidas: 5, ingresos: 39975 }],
  [`${A}/stock/estado`]: [
    { sku: 'SKU-001', stock_disponible: 4, stock_reservado: 0, stock_vendible: 4, umbral_minimo: 5, bajo_umbral: true, actualizado_en: '2026-11-04T15:31:00Z' },
    { sku: 'SKU-002', stock_disponible: 40, stock_reservado: 2, stock_vendible: 38, umbral_minimo: 5, bajo_umbral: false, actualizado_en: '2026-11-04T15:31:00Z' }
  ],
  [`${A}/stock/alertas`]: [{ sku: 'SKU-001', stock_disponible: 4, umbral_minimo: 5, ocurrido_en: '2026-11-04T15:31:00Z' }],
  [N]: [{ id: 'n1', tipo: 'stock_bajo', titulo: 'Stock bajo: SKU-001', mensaje: 'El SKU SKU-001 quedo con 4 unidades', referencia: 'sku:SKU-001', creada_en: '2026-11-04T15:31:01Z' }],
  [`${A}/metricas`]: {
    iniciado_en: '2026-11-04T15:00:00Z', mensajes_consumidos: { 'pedidos.eventos': 8, 'inventario.movimientos': 5 },
    mensajes_invalidos: { 'pedidos.eventos': 1 }, mensajes_fallidos: {}, movimientos_por_tipo: {},
    ultimo_offset_por_particion: {}, ultimo_movimiento_en: null
  }
});

describe('AnaliticaComponent', () => {
  let http: HttpTestingController;

  function crear(admin: boolean) {
    TestBed.configureTestingModule({
      imports: [AnaliticaComponent],
      providers: [
        provideHttpClient(), provideHttpClientTesting(),
        { provide: AuthService, useValue: { isAdmin: () => admin } }
      ]
    });
    http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(AnaliticaComponent);
    fixture.detectChanges();
    return fixture;
  }

  afterEach(() => { http?.match(() => true); TestBed.resetTestingModule(); });

  it('un usuario sin rol ADMIN ve el aviso y NO hace ninguna peticion', () => {
    const fixture = crear(false);
    http.expectNone(() => true);
    expect(fixture.nativeElement.textContent).toContain('solo para cuentas con el rol');
  });

  // timer(0, ...) dispara en el siguiente tick del event loop: se espera ese tick antes de mirar las peticiones.
  const siguienteTick = () => new Promise(r => setTimeout(r, 5));

  it('un ADMIN carga las 7 consultas y muestra las cifras', async () => {
    const fixture = crear(true);
    await siguienteTick();
    const pendientes = http.match(() => true);
    expect(pendientes.length).toBe(7);
    const datos = DATOS();
    pendientes.forEach(req => req.flush(datos[req.request.url]));
    fixture.detectChanges();

    const c = fixture.componentInstance;
    expect(c.resumen()?.pedidos_confirmados).toBe(3);
    expect(c.stockBajo().map(s => s.sku)).toEqual(['SKU-001']);
    expect(c.totalConsumidos()).toBe(13);
    expect(c.totalDescartados()).toBe(1);
    expect(c.barras().map(b => b.altura)).toEqual([100, 50]);   // la hora de mayor venta = 100%
    const texto = fixture.nativeElement.textContent;
    expect(texto).toContain('47,970');
    expect(texto).toContain('SKU-001');
    expect(texto).toContain('Stock bajo');
    expect(c.error()).toBeNull();
  });

  it('403 muestra el aviso de rol y no deja la pantalla en "Cargando"', async () => {
    const fixture = crear(true);
    await siguienteTick();
    http.match(() => true).forEach(req => req.flush({ detail: 'Requiere el rol: ADMIN' }, { status: 403, statusText: 'Forbidden' }));
    fixture.detectChanges();
    expect(fixture.componentInstance.error()).toContain('rol ADMIN');
    expect(fixture.componentInstance.cargando()).toBe(false);
  });

  it('con todo caido muestra el error pero CONSERVA los datos anteriores y se recupera en el siguiente ciclo', async () => {
    const fixture = crear(true);
    await siguienteTick();
    const datos = DATOS();
    http.match(() => true).forEach(req => req.flush(datos[req.request.url]));
    expect(fixture.componentInstance.resumen()).not.toBeNull();

    fixture.componentInstance.refrescar();                       // segundo ciclo: todo caido
    http.match(() => true).forEach(req => req.error(new ProgressEvent('error'), { status: 0 }));
    expect(fixture.componentInstance.error()).toContain('No se pudo conectar');
    expect(fixture.componentInstance.resumen()?.pedidos_confirmados).toBe(3);   // no se borra nada

    fixture.componentInstance.refrescar();                       // tercer ciclo: vuelve
    http.match(() => true).forEach(req => req.flush(datos[req.request.url]));
    expect(fixture.componentInstance.error()).toBeNull();
  });

  it('si solo cae ms-notificaciones (RabbitMQ), las cifras de Kafka SIGUEN actualizandose', async () => {
    const fixture = crear(true);
    await siguienteTick();
    const datos = DATOS();
    http.match(() => true).forEach(req => req.flush(datos[req.request.url]));

    // el siguiente ciclo trae ventas nuevas, pero el servicio de notificaciones esta caido
    fixture.componentInstance.refrescar();
    http.match(() => true).forEach(req => {
      if (req.request.url === N) { req.error(new ProgressEvent('error'), { status: 502 }); return; }
      req.flush(req.request.url === `${A}/ventas/resumen` ? { ...RESUMEN, pedidos_confirmados: 4 } : datos[req.request.url]);
    });
    const c = fixture.componentInstance;
    expect(c.resumen()?.pedidos_confirmados).toBe(4);            // se actualizo
    expect(c.notificaciones().length).toBe(1);                   // conserva las anteriores
    expect(c.error()).toContain('1 de 7 fuentes');
  });

  it('pausar detiene el refresco automatico', () => {
    const fixture = crear(true);
    const c = fixture.componentInstance;
    expect(c.enVivo()).toBe(true);
    c.toggleEnVivo();
    expect(c.enVivo()).toBe(false);
  });

  it('etiquetas y hora corta', () => {
    const c = crear(false).componentInstance;
    expect(c.etiquetaTipo('stock_bajo')).toBe('Stock bajo');
    expect(c.etiquetaTipo('pedido_confirmado')).toBe('Pedido confirmado');
    expect(c.horaCorta('2026-11-04T15:00:00Z')).toBe('15:00');
  });
});
