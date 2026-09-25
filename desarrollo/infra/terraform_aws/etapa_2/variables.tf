variable "aws_region" {
  type        = string
  description = "Región de AWS donde se desplegará la infraestructura"
  default     = "us-east-1"
}

variable "aws_account_id" {
  type        = string
  description = "ID de la cuenta de AWS (12 dígitos)"
  default     = "622421579399"
}

variable "vpc_id" {
  type        = string
  description = "ID de la VPC donde residirán los recursos"
  default     = "vpc-0e01d99c2ac4d3073"
}

variable "public_subnet_id" {
  type        = string
  description = "ID de la subred pública para el frontend y backend"
  default     = "subnet-0b1298af91600ad69"
}

variable "private_subnet_id" {
  type        = string
  description = "ID de la subred privada para la base de datos MariaDB"
  # Sin valor por defecto real: siempre debe venir de la Etapa 1
  # (TF_VAR_private_subnet_id).
  default = ""
}

variable "azure_tenant_name" {
  type        = string
  description = "Nombre del Tenant de Azure Entra ID"
  default     = "Carlos Mu"
}

variable "azure_tenant_id" {
  type        = string
  description = "ID del Tenant de Azure Entra ID"
  default     = "ea69d1fe-64a8-46fa-a274-47a2f05244ad"
}

variable "azure_client_id" {
  type        = string
  description = "ID de la Aplicación/Cliente en Azure Entra ID"
  default     = "f3e5ef16-7ccb-4c9f-bfdd-2b965ecec91d"
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
  description = "Contraseña root para la base de datos MariaDB"
  default     = "rootpassword"
  sensitive   = true
}

variable "db_name" {
  type        = string
  description = "Nombre de la base de datos principal"
  default     = "pidealtoke_db"
}