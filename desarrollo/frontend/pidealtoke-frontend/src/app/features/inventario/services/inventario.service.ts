import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ItemInventario } from '../models/inventario.model';

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
}