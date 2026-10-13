# Las variables sin "default" son OBLIGATORIAS: no hay IDs de cuenta, tenant, cliente ni
# contrasenas escritos en el repositorio. En CI llegan como TF_VAR_* desde los secretos de
# GitHub (ver .github/workflows/deploy.yml); en local copia terraform.tfvars.example a
# terraform.tfvars (ignorado por git) y completalo.

variable "aws_region" {
  type        = string
  description = "Región de AWS donde se desplegará la infraestructura"
  default     = "us-east-1"
}

variable "aws_account_id" {
  type        = string
  description = "ID de la cuenta de AWS (12 dígitos)"

  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "aws_account_id debe tener exactamente 12 dígitos."
  }
}

variable "vpc_id" {
  type        = string
  description = "ID de la VPC donde residirán los recursos (salida de la Etapa 1)"
}

variable "public_subnet_id" {
  type        = string
  description = "ID de la subred pública para el frontend y el backend (salida de la Etapa 1)"
}

variable "private_subnet_id" {
  type        = string
  description = "ID de la subred privada para la base de datos MariaDB (salida de la Etapa 1)"
}

variable "azure_tenant_id" {
  type        = string
  description = "ID del Tenant de Azure Entra ID"
}

variable "azure_client_id" {
  type        = string
  description = "ID de la Aplicación/Cliente en Azure Entra ID"
}

variable "ecr_frontend_repo" {
  type        = string
  description = "Nombre del repositorio ECR para el frontend"
  default     = "repo-frontend"
}

variable "ecr_backend_repo" {
  type        = string
  description = "Nombre del repositorio ECR para las imágenes del backend"
  default     = "repo-backend"
}

variable "db_password" {
  type        = string
  description = "Contraseña de root de MariaDB. También se usa para derivar la contraseña de cada microservicio (ningún servicio se conecta como root)."
  sensitive   = true
}

variable "internal_api_key" {
  type        = string
  description = "Clave compartida entre ms-pedidos y ms-inventario para los movimientos de stock internos"
  sensitive   = true

  validation {
    condition     = length(var.internal_api_key) >= 16
    error_message = "internal_api_key debe tener al menos 16 caracteres (usa un valor aleatorio)."
  }
}
