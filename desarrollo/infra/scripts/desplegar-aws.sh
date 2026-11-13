#!/usr/bin/env bash
# Despliega (o destruye) TODO en AWS con Terraform, desde Git Bash:
#   etapa 1: red (VPC, subredes, NAT)
#   etapa 2: EC2 frontend + backend + base de datos + MENSAJERIA (RabbitMQ, Kafka, Kafka-UI) + API Gateway
#
# Uso (desde la carpeta desarrollo/):
#   ./infra/scripts/desplegar-aws.sh            -> plan + apply de las dos etapas (pide confirmacion)
#   ./infra/scripts/desplegar-aws.sh plan       -> solo muestra lo que se crearia
#   ./infra/scripts/desplegar-aws.sh destroy    -> borra todo (etapa 2 y luego etapa 1)
#
# Requisitos: terraform y aws CLI instalados, credenciales de AWS vigentes (aws sts get-caller-identity)
# y el archivo infra/terraform_aws/etapa_2/terraform.tfvars (con los secretos; NO se sube a git).
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
E1="$RAIZ/terraform_aws/etapa_1"
E2="$RAIZ/terraform_aws/etapa_2"
MODO="${1:-apply}"

command -v terraform >/dev/null || { echo "Falta terraform en el PATH (terraform -version)."; exit 1; }
command -v aws >/dev/null       || { echo "Falta aws CLI en el PATH (aws --version)."; exit 1; }
[ -f "$E2/terraform.tfvars" ]   || { echo "Falta $E2/terraform.tfvars (copia terraform.tfvars.example y completalo)."; exit 1; }

# El ID de la cuenta sale de tus credenciales: no hace falta escribirlo en ningun archivo.
CUENTA="$(aws sts get-caller-identity --query Account --output text)" \
  || { echo "Credenciales de AWS invalidas o vencidas (en AWS Academy caducan cada pocas horas)."; exit 1; }
echo ">> Cuenta AWS: $CUENTA"

variables_etapa2() {
  # Las salidas de la etapa 1 alimentan a la etapa 2.
  local vpc pub priv
  vpc="$(cd "$E1" && terraform output -raw vpc_id)"
  pub="$(cd "$E1" && terraform output -raw public_subnet_id)"
  priv="$(cd "$E1" && terraform output -raw private_subnet_id)"
  echo "-var=aws_account_id=$CUENTA -var=vpc_id=$vpc -var=public_subnet_id=$pub -var=private_subnet_id=$priv"
}

if [ "$MODO" = "destroy" ]; then
  echo ">> Destruyendo etapa 2 (EC2, API Gateway) y luego etapa 1 (red)"
  (cd "$E2" && terraform init -input=false >/dev/null && terraform destroy $(variables_etapa2))
  (cd "$E1" && terraform destroy)
  exit 0
fi

echo ">> ETAPA 1: red"
(cd "$E1" && terraform init -input=false && terraform validate)
if [ "$MODO" = "plan" ]; then (cd "$E1" && terraform plan); else (cd "$E1" && terraform apply); fi

if [ "$MODO" = "plan" ]; then
  echo ">> El plan de la etapa 2 necesita las salidas de la etapa 1 (hace falta aplicarla antes)."; exit 0
fi

echo ">> ETAPA 2: EC2 (frontend, backend, base de datos y mensajeria) + API Gateway"
(cd "$E2" && terraform init -input=false && terraform validate && terraform apply $(variables_etapa2))

echo
echo ">> Listo. Datos de salida:"
(cd "$E2" && terraform output)
cat <<MSG

Siguientes pasos:
  1) La EC2 de mensajeria tarda unos minutos mas en levantar RabbitMQ, Kafka y Kafka-UI.
     Log de arranque (por SSM):  /var/log/mensajeria-setup.log
  2) Abre Kafka-UI con la URL 'kafka_ui_url' y el usuario/clave de terraform.tfvars (kafka_ui_user / kafka_ui_password).
  3) Sube las imagenes de los servicios a ECR (lo hace GitHub Actions al hacer push a release/1.0).
  4) Agrega la IP del frontend a 'extra_redirect_urls' de Azure (ver docs/COMO-OBTENER-VALORES.md).
MSG
