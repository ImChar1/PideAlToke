# Variable para hacer el código ejecutable en cualquier cuenta o tenant
variable "azure_tenant_id" {
  type        = string
  description = "ID del Tenant de Azure Entra ID creado en el portal"
}

variable "app_name" {
  type        = string
  default     = "PideAlToke-SPA"
  description = "Nombre para mostrar del registro de aplicación"
}

variable "frontend_redirect_url" {
  type        = string
  default     = "http://localhost:4200"
  description = "URL local de Angular donde Azure redirigirá tras autenticar"
}