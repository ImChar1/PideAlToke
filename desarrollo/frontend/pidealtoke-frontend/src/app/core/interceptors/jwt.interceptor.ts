import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { MsalService } from '@azure/msal-angular';
import { from, switchMap, catchError, throwError } from 'rxjs';
import { environment } from '../../../environments/environment';

export const jwtInterceptor: HttpInterceptorFn = (req, next) => {
  const msalService = inject(MsalService);
  const account = msalService.instance.getAllAccounts()[0];

  // Filtra y adjunta token solo para solicitudes dirigidas a nuestro API Gateway
  if (req.url.startsWith(environment.apiGatewayUrl) && account) {
    return from(
      msalService.instance.acquireTokenSilent({
        scopes: ['user.read'],
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