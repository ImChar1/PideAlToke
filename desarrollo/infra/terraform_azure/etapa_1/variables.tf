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

variable "extra_redirect_urls" {
  type        = list(string)
  default     = []
  description = <<-EOT
    URLs adicionales permitidas como redirect URI de la SPA. Agrega aqui la URL del frontend
    desplegado en AWS (https://<IP publica>, ver output "frontend_public_ip" de la Etapa 2).
    Ojo: la IP publica de una EC2 cambia en cada despliegue nuevo, hay que actualizar esta lista
    (o usar un dominio / Elastic IP fija).
  EOT
}

variable "admin_user_object_ids" {
  type        = list(string)
  default     = []
  description = "Object IDs (Entra ID) de los usuarios a los que se asigna el rol ADMIN (az ad user show --id <correo> --query id -o tsv)."
}
