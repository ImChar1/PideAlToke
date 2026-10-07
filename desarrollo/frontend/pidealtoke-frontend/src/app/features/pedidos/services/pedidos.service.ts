import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { CrearPedidoPayload, Pedido } from '../models/pedido.model';
import { environment } from '../../../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class PedidosService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiGatewayUrl}/api/v1/pedidos`;

  crearPedido(payload: CrearPedidoPayload): Observable<Pedido> {
    return this.http.post<Pedido>(this.apiUrl, payload);
  }

  obtenerPedido(id: number): Observable<Pedido> {
    return this.http.get<Pedido>(`${this.apiUrl}/${id}`);
  }

  /** Mis pedidos; con todos=true (solo ADMIN) los de todos los clientes. */
  listarPedidos(todos = false): Observable<Pedido[]> {
    const params = todos ? new HttpParams().set('todos', 'true') : undefined;
    return this.http.get<Pedido[]>(this.apiUrl, { params });
  }

  /** Cancela un pedido PENDIENTE y libera su stock reservado. */
  cancelarPedido(id: number): Observable<Pedido> {
    return this.http.post<Pedido>(`${this.apiUrl}/${id}/cancelar`, {});
  }

  /** Solo ADMIN: confirma el pedido y descuenta en firme el stock. */
  confirmarPedido(id: number): Observable<Pedido> {
    return this.http.post<Pedido>(`${this.apiUrl}/${id}/confirmar`, {});
  }
}
