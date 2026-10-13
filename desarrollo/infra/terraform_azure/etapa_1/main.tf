# Comandos para autenticarse y desplegar desde cualquier cuenta
# az login
#
# Para verificar el Tenant ID activo:
# az account show --query tenantId -o tsv
#
# Para inicializar y aplicar Terraform
# cd infra/terraform_azure/etapa_1
# terraform init
# terraform apply -var="azure_tenant_id=TU_TENANT_ID_AQUI"
#
# IMPORTANTE: si la app de Azure ya existia (creada a mano o por otra ejecucion) y no esta en el
# estado de Terraform, "apply" creara una NUEVA app con otro client_id. Importala primero:
#   terraform import azuread_application.pidealtoke_spa /applications/<OBJECT_ID_DE_LA_APP>
#   terraform import azuread_service_principal.pidealtoke_sp <OBJECT_ID_DEL_SERVICE_PRINCIPAL>

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

locals {
  # IDs fijos (no cambian entre ejecuciones): identifican el scope y el App Role dentro de la app.
  scope_access_as_user_id = "216005e3-2386-497f-a566-70944df91813"
  app_role_admin_id       = "579c4c6c-4dec-4b0e-ba1c-88344d02198d"
}

# 1. Registro de la aplicación en Azure AD
resource "azuread_application" "pidealtoke_spa" {
  display_name     = var.app_name
  sign_in_audience = "AzureADMyOrg" # Solo cuentas de este directorio organizativo

  # --- "Expose an API": el frontend pide el scope api://<client_id>/access_as_user ---
  # Sin esto el login falla (AADSTS70011: el scope no existe).
  api {
    # Tokens v2: el claim "aud" es el client id (GUID), que es lo que validan el API Gateway y los microservicios.
    requested_access_token_version = 2

    oauth2_permission_scope {
      id                         = local.scope_access_as_user_id
      value                      = "access_as_user"
      type                       = "User"
      enabled                    = true
      admin_consent_display_name = "Acceder a PideAlToke en nombre del usuario"
      admin_consent_description  = "Permite a la aplicación llamar a la API de PideAlToke con la identidad del usuario."
      user_consent_display_name  = "Acceder a PideAlToke en tu nombre"
      user_consent_description   = "Permite a la aplicación llamar a la API de PideAlToke con tu identidad."
    }
  }

  # --- App Role "ADMIN": viaja en el claim "roles" del token y habilita escribir catalogo/inventario ---
  app_role {
    id                   = local.app_role_admin_id
    allowed_member_types = ["User"]
    display_name         = "ADMIN"
    description          = "Administrador: gestiona catalogo e inventario"
    value                = "ADMIN"
    enabled              = true
  }

  # Configuración tipo SPA (Single Page Application) requerida por MSAL Angular (flujo code + PKCE).
  # Ya no se habilita implicit grant: MSAL Browser v2+ no lo usa y es un flujo desaconsejado.
  single_page_application {
    redirect_uris = concat([var.frontend_redirect_url], var.extra_redirect_urls)
  }

  # El identifier URI (api://<client_id>) referencia al propio client_id, asi que se crea con un
  # recurso aparte; sin ignore_changes Terraform lo intentaria borrar en cada plan.
  lifecycle {
    ignore_changes = [identifier_uris]
  }
}

resource "azuread_application_identifier_uri" "api" {
  application_id = azuread_application.pidealtoke_spa.id
  identifier_uri = "api://${azuread_application.pidealtoke_spa.client_id}"

  # Se crea DESPUES del service principal: si no, en la primera ejecucion puede fallar con un
  # error de "dominio no verificado" (hashicorp/terraform-provider-azuread#1392).
  depends_on = [azuread_service_principal.pidealtoke_sp]
}

# 2. Service Principal necesario para la gestión de la app en el directorio
resource "azuread_service_principal" "pidealtoke_sp" {
  client_id                    = azuread_application.pidealtoke_spa.client_id
  app_role_assignment_required = false
}

# 3. (Opcional) Asigna el rol ADMIN a usuarios concretos: reemplaza el paso manual de
# Azure Portal -> Enterprise applications -> Users and groups.
resource "azuread_app_role_assignment" "admins" {
  for_each            = toset(var.admin_user_object_ids)
  app_role_id         = local.app_role_admin_id
  principal_object_id = each.value
  resource_object_id  = azuread_service_principal.pidealtoke_sp.object_id
}
