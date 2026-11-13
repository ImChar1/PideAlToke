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

# --- Mensajeria (EC2 con RabbitMQ en cluster + Kafka + Kafka-UI) ---

variable "messaging_instance_type" {
  type        = string
  description = "Tipo de la EC2 de mensajeria (3 Zookeeper + 3 brokers + 2 nodos RabbitMQ + Kafka-UI necesitan ~4.5 GB de RAM: usa t3.large o mayor)"
  default     = "t3.large"
}

variable "backend_instance_type" {
  type        = string
  description = "Tipo de la EC2 del backend (8 contenedores Python; una t2.micro de 1 GB no alcanza)"
  default     = "t3.small"
}

variable "messaging_admin_cidr" {
  type        = string
  description = "CIDR con acceso a las consolas web (RabbitMQ 15672/15673 y Kafka-UI 8090). El default abre a Internet (piden usuario y clave): para algo mas serio, pon tu IP/32."
  default     = "0.0.0.0/0"
}

variable "rabbitmq_user" {
  type        = string
  description = "Usuario administrador de RabbitMQ"
  default     = "admin"
}

# Solo letras y numeros: estos valores se escriben en un .env, en YAML y en scripts de shell sin escapar.
# Genera uno con:  openssl rand -hex 16
variable "rabbitmq_password" {
  type        = string
  description = "Clave de RabbitMQ (la usan los microservicios y la consola web)"
  sensitive   = true

  validation {
    condition     = can(regex("^[A-Za-z0-9]{12,}$", var.rabbitmq_password))
    error_message = "rabbitmq_password debe tener al menos 12 caracteres y solo letras/numeros (ej. openssl rand -hex 16)."
  }
}

variable "rabbitmq_erlang_cookie" {
  type        = string
  description = "Cookie de Erlang compartida por los 2 nodos del cluster RabbitMQ"
  sensitive   = true

  validation {
    condition     = can(regex("^[A-Za-z0-9]{16,}$", var.rabbitmq_erlang_cookie))
    error_message = "rabbitmq_erlang_cookie debe tener al menos 16 caracteres y solo letras/numeros (ej. openssl rand -hex 16)."
  }
}

variable "kafka_ui_user" {
  type        = string
  description = "Usuario de Kafka-UI"
  default     = "admin"
}

variable "kafka_ui_password" {
  type        = string
  description = "Clave de Kafka-UI"
  sensitive   = true

  validation {
    condition     = can(regex("^[A-Za-z0-9]{12,}$", var.kafka_ui_password))
    error_message = "kafka_ui_password debe tener al menos 12 caracteres y solo letras/numeros (ej. openssl rand -hex 16)."
  }
}
