import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { CrearInventarioPayload, ItemInventario } from '../models/inventario.model';
import { environment } from '../../../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class InventarioService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiGatewayUrl}/api/v1/inventario`;

  getInventario(): Observable<ItemInventario[]> {
    return this.http.get<ItemInventario[]>(this.apiUrl);
  }

  // Da de alta el registro de stock para un SKU nuevo. Requiere rol ADMIN en el JWT.
  crearInventario(payload: CrearInventarioPayload): Observable<ItemInventario> {
    return this.http.post<ItemInventario>(this.apiUrl, payload);
  }
}