# Retorna los valores que necesitarás copiar en el frontend y backend
output "client_id" {
  value       = azuread_application.pidealtoke_spa.client_id
  description = "Client ID asignado a la aplicación en Azure"
}

output "tenant_id" {
  value       = var.azure_tenant_id
  description = "Tenant ID de Azure utilizado"
}