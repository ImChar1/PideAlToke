import { ApplicationConfig, importProvidersFrom } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, HTTP_INTERCEPTORS, withInterceptors } from '@angular/common/http';
import { routes } from './app.routes';
import { environment } from '../environments/environment';
import { 
  IPublicClientApplication, 
  PublicClientApplication, 
  InteractionType,
  Configuration 
} from '@azure/msal-browser';
import { 
  MsalModule, 
  MsalService, 
  MsalGuard, 
  MsalInterceptor, 
  MSAL_INSTANCE, 
  MSAL_GUARD_CONFIG, 
  MSAL_INTERCEPTOR_CONFIG, 
  MsalGuardConfiguration, 
  MsalInterceptorConfiguration 
} from '@azure/msal-angular';
import { jwtInterceptor } from './core/interceptors/jwt.interceptor';

export function MSALInstanceFactory(): IPublicClientApplication {
  const msalConfig: Configuration = {
    auth: {
      clientId: environment.azure.clientId,
      authority: environment.azure.authority,
      // Se calcula en tiempo de ejecución (funciona igual en localhost:4200
      // que en la IP pública de turno, sin tocar código en cada deploy)
      redirectUri: window.location.origin,
      postLogoutRedirectUri: window.location.origin
    },
    cache: {
      cacheLocation: 'localStorage'
    }
  };

  return new PublicClientApplication(msalConfig);
}

export function MSALGuardConfigFactory(): MsalGuardConfiguration {
  return {
    interactionType: InteractionType.Redirect,
    authRequest: {
      scopes: ['user.read']
    }
  };
}

export function MSALInterceptorConfigFactory(): MsalInterceptorConfiguration {
  const protectedResourceMap = new Map<string, Array<string>>();
  protectedResourceMap.set(`${environment.apiGatewayUrl}/*`, ['user.read']);

  return {
    interactionType: InteractionType.Redirect,
    protectedResourceMap
  };
}

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(withInterceptors([jwtInterceptor])),
    importProvidersFrom(MsalModule),
    {
      provide: MSAL_INSTANCE,
      useFactory: MSALInstanceFactory
    },
    {
      provide: MSAL_GUARD_CONFIG,
      useFactory: MSALGuardConfigFactory
    },
    MsalService,
    MsalGuard,
  ]
};