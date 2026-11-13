import { Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { HttpErrorResponse } from '@angular/common/http';
import { Observable, catchError, forkJoin, of, switchMap, tap, timer } from 'rxjs';
import { AnaliticaService } from './services/analitica.service';
import { AuthService } from '../../core/auth/auth.service';
import {
  AlertaStock, MetricasConsumo, Notificacion, ProductoTop, ResumenVentas, StockSku, VentasHora
} from './models/analitica.model';

export const INTERVALO_REFRESCO_MS = 5000;
const TOTAL_CONSULTAS = 7;

@Component({
  selector: 'app-analitica',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './analitica.component.html',
  styleUrl: './analitica.component.css'
})
export class AnaliticaComponent implements OnInit {
  private analitica = inject(AnaliticaService);
  private authService = inject(AuthService);
  private destroyRef = inject(DestroyRef);

  resumen = signal<ResumenVentas | null>(null);
  porHora = signal<VentasHora[]>([]);
  top = signal<ProductoTop[]>([]);
  stock = signal<StockSku[]>([]);
  alertas = signal<AlertaStock[]>([]);
  notificaciones = signal<Notificacion[]>([]);
  metricas = signal<MetricasConsumo | null>(null);

  cargando = signal(true);
  error = signal<string | null>(null);
  enVivo = signal(true);                       // el refresco automatico se puede pausar
  actualizadoEn = signal<Date | null>(null);

  get esAdmin(): boolean {
    return this.authService.isAdmin();
  }

  // Altura relativa de cada barra del grafico de ventas por hora (la mayor = 100%).
  barras = computed(() => {
    const horas = this.porHora();
    const maximo = Math.max(1, ...horas.map(h => h.ingresos));
    return horas.map(h => ({ ...h, altura: Math.max(4, Math.round((h.ingresos / maximo) * 100)) }));
  });

  stockBajo = computed(() => this.stock().filter(s => s.bajo_umbral));

  totalConsumidos = computed(() =>
    Object.values(this.metricas()?.mensajes_consumidos ?? {}).reduce((a, b) => a + b, 0)
  );
  totalDescartados = computed(() => {
    const m = this.metricas();
    const suma = (r: Record<string, number> | undefined) => Object.values(r ?? {}).reduce((a, b) => a + b, 0);
    return suma(m?.mensajes_invalidos) + suma(m?.mensajes_fallidos);
  });

  ngOnInit(): void {
    if (!this.esAdmin) {
      // Sin el rol, el backend respondera 403 en todo: se avisa sin lanzar 7 peticiones inutiles.
      this.cargando.set(false);
      return;
    }
    // Sondeo: cada 5 s se piden las cifras. switchMap cancela la peticion anterior si se atrasa, y
    // takeUntilDestroyed detiene el sondeo al salir de la pagina.
    timer(0, INTERVALO_REFRESCO_MS).pipe(
      switchMap(() => (this.enVivo() ? this.cargarTodo() : of(null))),
      takeUntilDestroyed(this.destroyRef)
    ).subscribe();
  }

  toggleEnVivo(): void {
    this.enVivo.set(!this.enVivo());
  }

  refrescar() {
    return this.cargarTodo().subscribe();
  }

  // Cada consulta es INDEPENDIENTE: si una falla (p. ej. ms-notificaciones/RabbitMQ caido) las demas se
  // siguen actualizando. Con un forkJoin simple, un solo error cancelaba las otras 6 y congelaba todo.
  private cargarTodo() {
    const fallos: HttpErrorResponse[] = [];
    const seguro = <T>(obs: Observable<T>): Observable<T | null> =>
      obs.pipe(catchError((err: HttpErrorResponse) => {
        console.error('Error cargando analitica:', err);
        fallos.push(err);
        return of(null);
      }));

    return forkJoin({
      resumen: seguro(this.analitica.getResumenVentas()),
      porHora: seguro(this.analitica.getVentasPorHora()),
      top: seguro(this.analitica.getProductosTop(5)),
      stock: seguro(this.analitica.getEstadoStock()),
      alertas: seguro(this.analitica.getAlertasStock()),
      notificaciones: seguro(this.analitica.getNotificaciones(10)),
      metricas: seguro(this.analitica.getMetricas())
    }).pipe(
      tap(d => {
        // Solo se reemplaza lo que SI llego: lo que fallo conserva su ultimo valor.
        if (d.resumen) this.resumen.set(d.resumen);
        if (d.porHora) this.porHora.set(d.porHora);
        if (d.top) this.top.set(d.top);
        if (d.stock) this.stock.set(d.stock);
        if (d.alertas) this.alertas.set(d.alertas);
        if (d.notificaciones) this.notificaciones.set(d.notificaciones);
        if (d.metricas) this.metricas.set(d.metricas);
        if (fallos.length < TOTAL_CONSULTAS) this.actualizadoEn.set(new Date());
        this.error.set(fallos.length ? this.mensajeDeError(fallos[0], fallos.length) : null);
        this.cargando.set(false);
      })
    );
  }

  private mensajeDeError(err: HttpErrorResponse, cuantas: number): string {
    if (err.status === 403) return 'Tu cuenta no tiene el rol ADMIN: no puedes ver la analitica.';
    if (err.status === 401) return 'La sesion expiro. Vuelve a iniciar sesion.';
    if (cuantas < TOTAL_CONSULTAS) {
      return `${cuantas} de ${TOTAL_CONSULTAS} fuentes no respondieron: se muestran los ultimos datos de esas secciones. Se reintentara automaticamente.`;
    }
    return 'No se pudo conectar con ms-analitica o ms-notificaciones. Se reintentara automaticamente.';
  }

  etiquetaTipo(tipo: Notificacion['tipo']): string {
    return { pedido_confirmado: 'Pedido confirmado', pedido_cancelado: 'Pedido cancelado', stock_bajo: 'Stock bajo' }[tipo];
  }

  horaCorta(iso: string): string {
    return iso.slice(11, 16);   // "2026-11-04T15:00:00Z" -> "15:00" (UTC)
  }
}
