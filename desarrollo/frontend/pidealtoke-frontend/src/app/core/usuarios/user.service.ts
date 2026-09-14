import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class UserService {
  private http = inject(HttpClient);

  // Llama al microservicio de usuarios en el puerto 8001
  getUserProfile(): Observable<any> {
    return this.http.get('http://localhost:8001/api/v1/users/me');
  }
}