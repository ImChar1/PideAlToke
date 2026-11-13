import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  AlertaStock, MetricasConsumo, Notificacion, ProductoTop, ResumenVentas, StockSku, VentasHora
} from '../models/analitica.model';
import { environment } from '../../../../environments/environment';

// Lectura de la analitica en tiempo real. Todos los endpoints exigen el rol ADMIN en el JWT (el
// interceptor adjunta el token); sin el rol, el backend responde 403.
@Injectable({ providedIn: 'root' })
export class AnaliticaService {
  private http = inject(HttpClient);
  private analiticaUrl = `${environment.apiGatewayUrl}/api/v1/analitica`;
  private notificacionesUrl = `${environment.apiGatewayUrl}/api/v1/notificaciones`;

  // --- ms-analitica (consume Kafka) ---

  getResumenVentas(): Observable<ResumenVentas> {
    return this.http.get<ResumenVentas>(`${this.analiticaUrl}/ventas/resumen`);
  }

  getVentasPorHora(): Observable<VentasHora[]> {
    return this.http.get<VentasHora[]>(`${this.analiticaUrl}/ventas/por-hora`);
  }

  getProductosTop(limite = 5): Observable<ProductoTop[]> {
    return this.http.get<ProductoTop[]>(`${this.analiticaUrl}/productos/top`, {
      params: new HttpParams().set('limite', limite)
    });
  }

  getEstadoStock(soloBajoUmbral = false): Observable<StockSku[]> {
    return this.http.get<StockSku[]>(`${this.analiticaUrl}/stock/estado`, {
      params: new HttpParams().set('bajo_umbral', soloBajoUmbral)
    });
  }

  getAlertasStock(): Observable<AlertaStock[]> {
    return this.http.get<AlertaStock[]>(`${this.analiticaUrl}/stock/alertas`);
  }

  getMetricas(): Observable<MetricasConsumo> {
    return this.http.get<MetricasConsumo>(`${this.analiticaUrl}/metricas`);
  }

  // --- ms-notificaciones (consume RabbitMQ) ---
  // Sin barra final a proposito: el API Gateway define la ruta base sin ella.

  getNotificaciones(limite = 10): Observable<Notificacion[]> {
    return this.http.get<Notificacion[]>(this.notificacionesUrl, {
      params: new HttpParams().set('limite', limite)
    });
  }
}
