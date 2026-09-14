import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { CrearProductoPayload, Producto } from '../models/producto.model';

@Injectable({ providedIn: 'root' })
export class CatalogoService {
  private http = inject(HttpClient);
  private apiUrl = 'http://localhost:8002/api/v1/productos';

  getProducts(): Observable<Producto[]> {
    return this.http.get<Producto[]>(this.apiUrl);
  }

  // Alta de un producto nuevo en el catalogo. Requiere rol ADMIN en el JWT.
  crearProducto(payload: CrearProductoPayload): Observable<Producto> {
    return this.http.post<Producto>(this.apiUrl, payload);
  }

  // Baja logica: el backend marca el producto como inactivo (no lo borra fisicamente).
  // Requiere rol ADMIN en el JWT.
  eliminarProducto(id: number): Observable<Producto> {
    return this.http.delete<Producto>(`${this.apiUrl}/${id}`);
  }
}