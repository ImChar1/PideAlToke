import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { CrearPedidoPayload, Pedido } from '../models/pedido.model';

@Injectable({
  providedIn: 'root'
})
export class PedidosService {
  private http = inject(HttpClient);
  // ms-pedidos: sigue la misma convencion de puertos que usuarios(8001)/catalogo(8002)/inventario(8003)
  private apiUrl = 'http://localhost:8004/api/v1/pedidos';

  crearPedido(payload: CrearPedidoPayload): Observable<Pedido> {
    return this.http.post<Pedido>(`${this.apiUrl}/`, payload);
  }

  obtenerPedido(id: number): Observable<Pedido> {
    return this.http.get<Pedido>(`${this.apiUrl}/${id}`);
  }
}
