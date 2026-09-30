import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { MsalService } from '@azure/msal-angular';
import { from, switchMap, catchError, throwError } from 'rxjs';
import { environment } from '../../../environments/environment';

export const jwtInterceptor: HttpInterceptorFn = (req, next) => {
  const msalService = inject(MsalService);
  // OJO: usar siempre la cuenta activa (la del último login), no getAllAccounts()[0].
  // Si quedan varias cuentas en el cache de localStorage (de logins anteriores sin
  // cerrar sesión del todo), getAllAccounts()[0] puede devolver una cuenta vieja y
  // el token adjunto sería el de esa cuenta, no el de la sesión con la que estás
  // trabajando ahora mismo (esto rompe silenciosamente los permisos de ADMIN).
  const account = msalService.instance.getActiveAccount() ?? msalService.instance.getAllAccounts()[0];

  // Evalúa si la llamada va hacia el API Gateway (producción en AWS) 
  // O hacia cualquier microservicio local en Docker (puertos 8001, 8002, 8003, 8004, etc.)
  const isApiTarget = req.url.startsWith(environment.apiGatewayUrl) || req.url.includes('localhost:800');

  if (isApiTarget && account) {
  return from(
    msalService.instance.acquireTokenSilent({
      scopes: ['api://f3e5ef16-7ccb-4c9f-bfdd-2b965ecec91d/access_as_user'],
      account: account
    })
  ).pipe(
      switchMap((result) => {
        const clonedReq = req.clone({
          headers: req.headers.set('Authorization', `Bearer ${result.accessToken}`)
        });
        return next(clonedReq);
      }),
      catchError((error) => throwError(() => error))
    );
  }

  return next(req);
};