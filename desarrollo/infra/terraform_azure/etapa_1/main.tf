# Comandos para autenticarse y desplegar desde cualquier cuenta
# az login

# Para verificar el Tenant ID activo:
# az account show --query tenantID -o tsv

# Para inicializar y aplicar Terraform
# cd infra/terraform_azure/etapa_1
# terraform init
# terraform apply -var="azure_tenant_id=TU_TENANT_ID_AQUI"

terraform {
  required_version = ">= 1.0.0"
  required_providers {
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.47.0"
    }
  }
}

# Configuración del proveedor de Microsoft Entra ID (Azure AD)
provider "azuread" {
  tenant_id = var.azure_tenant_id
}

# 1. Registro de la aplicación en Azure AD
resource "azuread_application" "pidealtoke_spa" {
  display_name     = var.app_name
  sign_in_audience = "AzureADMyOrg" # Solo cuentas de este directorio organizativo

  # Configuración tipo SPA (Single Page Application) requerida por MSAL Angular
  single_page_application {
    redirect_uris = [
      var.frontend_redirect_url
    ]
  }

  # Habilita la emisión explícita de tokens ID y Access Tokens si se requiere
  web {
    implicit_grant {
      access_token_issuance_enabled = true
      id_token_issuance_enabled     = true
    }
  }
}

# 2. Service Principal necesario para la gestión de la app en el directorio
resource "azuread_service_principal" "pidealtoke_sp" {
  client_id                    = azuread_application.pidealtoke_spa.client_id
  app_role_assignment_required = false
}
# id de aplicación (cliente) Cliente ID: f3e5ef16-7ccb-4c9f-bfdd-2b965ecec91d
# id de directorio(inquilino) Tenant ID: ea69d1fe-64a8-46fa-a274-47a2f05244ad