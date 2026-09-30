import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class UserService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiGatewayUrl}/api/v1/users`;

  getUserProfile(): Observable<any> {
    return this.http.get(`${this.apiUrl}/me`);
  }
}