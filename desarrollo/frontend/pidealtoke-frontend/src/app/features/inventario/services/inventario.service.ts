import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { CrearInventarioPayload, ItemInventario } from '../models/inventario.model';

@Injectable({
  providedIn: 'root'
})
export class InventarioService {
  private http = inject(HttpClient);
  // Revisa en tu docker-compose.yml si el puerto mapeado de ms-inventario es el 8003
  private apiUrl = 'http://localhost:8003/api/v1/inventario';

  getInventario(): Observable<ItemInventario[]> {
    return this.http.get<ItemInventario[]>(this.apiUrl);
  }

  // Da de alta el registro de stock para un SKU nuevo. Requiere rol ADMIN en el JWT.
  crearInventario(payload: CrearInventarioPayload): Observable<ItemInventario> {
    return this.http.post<ItemInventario>(this.apiUrl, payload);
  }
}