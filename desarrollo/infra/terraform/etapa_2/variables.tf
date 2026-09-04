variable "aws_region" {
  type = string
  default = "us-east-1"
}

# Variables que se llenan con los outputs de la Etapa 1
variable "vpc_id" {
  type = string
}

variable "public_subnet_id" {
  type = string
}

variable "private_subnet_id" {
    type = string
}

# Variables para Azure Entra ID
variable "azure_tenant_id" {
  type = string
}

variable "azure_client_id" {
    type = string
}

variable "azure_tenant_name" {
    type = string
}