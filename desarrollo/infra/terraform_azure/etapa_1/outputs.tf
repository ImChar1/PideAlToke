# Retorna los valores que necesitarás copiar en el frontend y backend
output "client_id" {
  value       = azuread_application.pidealtoke_spa.client_id
  description = "Client ID asignado a la aplicación en Azure (secreto de CI AZURE_CLIENT_ID y environment.ts del frontend)"
}

output "tenant_id" {
  value       = var.azure_tenant_id
  description = "Tenant ID de Azure utilizado"
}

output "api_scope" {
  value       = "api://${azuread_application.pidealtoke_spa.client_id}/access_as_user"
  description = "Scope que pide el frontend (debe coincidir con environment.azure.apiScope)"
}
