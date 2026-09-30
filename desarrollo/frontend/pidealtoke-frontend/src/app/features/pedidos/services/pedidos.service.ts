import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
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
    return this.http.post<Pedido>(`${this.apiUrl}/`, payload);
  }

  obtenerPedido(id: number): Observable<Pedido> {
    return this.http.get<Pedido>(`${this.apiUrl}/${id}`);
  }
}
