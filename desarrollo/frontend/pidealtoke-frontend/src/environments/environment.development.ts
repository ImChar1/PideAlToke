const clientId = 'f3e5ef16-7ccb-4c9f-bfdd-2b965ecec91d';

export const environment = {
  production: false,
  azure: {
    clientId,
    tenantId: 'ea69d1fe-64a8-46fa-a274-47a2f05244ad',
    authority: 'https://login.microsoftonline.com/ea69d1fe-64a8-46fa-a274-47a2f05244ad',
    redirectUri: 'http://localhost:4200',
    // Scope de NUESTRA API (definido en Azure como "Expose an API"). Es el unico scope que
    // se usa en toda la app (login, guard e interceptor), asi el access token que se envia
    // a los microservicios es siempre el mismo y esta emitido para ellos (no para Graph).
    apiScope: `api://${clientId}/access_as_user`
  },
  apiGatewayUrl: 'http://localhost:8080'
};
