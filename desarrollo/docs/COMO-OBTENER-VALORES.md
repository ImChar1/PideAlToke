# De dónde sale cada valor (paso a paso)

Todos los comandos son para Git Bash. Ya completé en `desarrollo/.env` y en los `terraform.tfvars` todo lo que se podía generar o copiar. Lo que sigue es lo que **debes conseguir tú**.

## Lo que ya está completado

| Valor | Dónde | Cómo se resolvió |
|---|---|---|
| `DB_ROOT_PASSWORD`, `DB_PASS_*`, `INTERNAL_API_KEY` | `.env` | Se conservó tu valor si ya era real; si era de ejemplo se generó uno aleatorio (`openssl rand -hex 16`). |
| `RABBITMQ_PASSWORD`, `RABBITMQ_ERLANG_COOKIE`, `KAFKA_UI_PASSWORD` | `.env` y `etapa_2/terraform.tfvars` | Igual; solo letras y números, como exige Terraform. |
| `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` | `.env`, tfvars | Copiados de tu `.env` (no son secretos). |
| ID de cuenta, VPC y subredes de AWS | no se escriben | `desplegar-aws.sh` los obtiene de tus credenciales y de la etapa 1. |
| Repositorios ECR | no se escriben | El workflow los crea si no existen. |

Si ya tenías volúmenes de Docker con las claves anteriores (MariaDB, RabbitMQ), ejecuta una vez `./levantar-todo.sh down -v` para que arranquen con las nuevas.

## Lo que falta y cómo conseguirlo

### 1. Credenciales de AWS (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_REGION`)

- **AWS Academy (Learner Lab):** inicia el laboratorio, pulsa *AWS Details* y luego *AWS CLI: Show*. Copia los tres valores. Caducan cada pocas horas: cada vez que reinicies el lab hay que actualizarlos (también los secretos de GitHub).
- **Cuenta normal:** consola AWS > tu usuario > *Security credentials* > *Create access key*.
- Cárgalas en tu terminal:

```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...        # solo en Academy
export AWS_DEFAULT_REGION=us-east-1
aws sts get-caller-identity         # debe mostrar tu cuenta
```

### 2. `AWS_ACCOUNT_ID` (secreto de GitHub)

```bash
aws sts get-caller-identity --query Account --output text
```

### 3. `ECR_BACKEND_REPO` y `ECR_FRONTEND_REPO` (secretos de GitHub)

Son nombres que tú eliges. Usa `repo-backend` y `repo-frontend` (los valores por defecto de Terraform). No hay que crearlos: el workflow los crea.

### 4. `TF_STATE_BUCKET` (opcional, recomendado en la vía A)

```bash
CUENTA=$(aws sts get-caller-identity --query Account --output text)
aws s3 mb s3://pidealtoke-tfstate-$CUENTA --region us-east-1
aws s3api put-bucket-versioning --bucket pidealtoke-tfstate-$CUENTA --versioning-configuration Status=Enabled
```

El valor del secreto es `pidealtoke-tfstate-<tu cuenta>`.

### 5. Secretos de GitHub (vía A)

Con la interfaz: repositorio > *Settings > Secrets and variables > Actions > New repository secret*. O con la CLI de GitHub (`gh auth login` una vez):

```bash
cd desarrollo
V() { grep "^$1" infra/terraform_aws/etapa_2/terraform.tfvars | cut -d'"' -f2; }
gh secret set DB_PASSWORD            --body "$(V db_password)"
gh secret set INTERNAL_API_KEY       --body "$(V internal_api_key)"
gh secret set RABBITMQ_PASSWORD      --body "$(V rabbitmq_password)"
gh secret set RABBITMQ_ERLANG_COOKIE --body "$(V rabbitmq_erlang_cookie)"
gh secret set KAFKA_UI_PASSWORD      --body "$(V kafka_ui_password)"
gh secret set AZURE_TENANT_ID        --body "$(V azure_tenant_id)"
gh secret set AZURE_CLIENT_ID        --body "$(V azure_client_id)"
gh secret set AWS_REGION             --body "us-east-1"
gh secret set ECR_BACKEND_REPO       --body "repo-backend"
gh secret set ECR_FRONTEND_REPO      --body "repo-frontend"
# y los de AWS (paso 1 y 2):
gh secret set AWS_ACCESS_KEY_ID      --body "$AWS_ACCESS_KEY_ID"
gh secret set AWS_SECRET_ACCESS_KEY  --body "$AWS_SECRET_ACCESS_KEY"
gh secret set AWS_SESSION_TOKEN      --body "$AWS_SESSION_TOKEN"
gh secret set AWS_ACCOUNT_ID         --body "$(aws sts get-caller-identity --query Account --output text)"
```

### 6. Tu IP para las consolas (opcional, más seguro)

Por defecto las consolas de RabbitMQ y Kafka-UI quedan abiertas a internet (piden usuario y clave). Para cerrarlas a tu IP, agrega a `etapa_2/terraform.tfvars`:

```bash
echo "messaging_admin_cidr = \"$(curl -s https://checkip.amazonaws.com)/32\"" >> infra/terraform_aws/etapa_2/terraform.tfvars
```

Si tu IP cambia, actualiza esa línea y vuelve a aplicar.

### 7. Azure: tenant, client ID y rol ADMIN

```bash
az login
az account show --query tenantId -o tsv                    # AZURE_TENANT_ID
cd infra/terraform_azure/etapa_1
terraform init && terraform apply                          # registra la app en Entra ID
terraform output client_id                                 # AZURE_CLIENT_ID (si cambió, actualiza .env, tfvars y secretos)
```

Tu usuario como administrador (rol `ADMIN`): obtén su *object id* y agrégalo a `etapa_1/terraform.tfvars`:

```bash
az ad user show --id TU_CORREO@dominio.com --query id -o tsv
# en terraform.tfvars:  admin_user_object_ids = ["<ese id>"]
terraform apply
```

Si en la etapa 1 ya existía la app creada a mano, impórtala antes (ver el encabezado de `etapa_1/main.tf`) o Terraform creará una nueva con otro `client_id`.

### 8. Redirect URI del frontend desplegado

Tras el despliegue, el frontend tiene IP pública (`terraform output frontend_public_ip` en `terraform_aws/etapa_2`). Agrégala para que el login con Microsoft funcione:

```bash
cd infra/terraform_azure/etapa_1
# en terraform.tfvars:  extra_redirect_urls = ["http://<IP_DEL_FRONTEND>"]
terraform apply
```

La IP pública de una EC2 cambia si la reemplazas; hay que repetir este paso (o usar una Elastic IP).

### 9. Cuenta de usuario para entrar a la aplicación

El login es con Microsoft Entra ID: el usuario debe existir en tu directorio (portal de Azure > Microsoft Entra ID > *Users*). Ese mismo usuario es el que recibe el rol `ADMIN` (paso 7).
