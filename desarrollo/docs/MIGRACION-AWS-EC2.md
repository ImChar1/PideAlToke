# Migración de Kafka, RabbitMQ y Kafka-UI a AWS EC2

## Qué corre dónde

| EC2 | Qué corre | Creada por |
|---|---|---|
| `mensajeria-ec2` (t3.large, 30 GB) | RabbitMQ (2 nodos), 3 Zookeeper, 3 brokers Kafka, `kafka-init` (crea los 2 tópicos) y Kafka-UI | `terraform_aws/etapa_2/mensajeria.tf` |
| `backend-ec2` (t3.small) | Los 8 microservicios (imágenes de ECR) | `terraform_aws/etapa_2/main.tf` |
| `db-ec2` (subred privada) | MariaDB | `terraform_aws/etapa_2/main.tf` |
| `frontend-ec2` | Angular (nginx) | `terraform_aws/etapa_2/main.tf` |

Terraform **lee los mismos archivos compose del repositorio** (`docker-compose.rabbitmq.yml`, `docker-compose.kafka.yml`, `docker-compose.kafka-ui.yml`) y los instala en `mensajeria-ec2`. Por eso **no los borres**: son la única fuente de verdad, para local y para la nube. El backend se conecta a los brokers por la IP privada de esa EC2 (`KAFKA_BOOTSTRAP_SERVERS` y `RABBITMQ_HOST` se inyectan solos).

Seguridad: AMQP y Kafka solo aceptan conexiones del security group del backend. Las consolas web (RabbitMQ `15672/15673` y Kafka-UI `8090`) piden usuario y clave y se abren al CIDR `messaging_admin_cidr`.

## Desplegar desde Git Bash (una sola vía: elige A o B)

**No mezcles las dos vías.** El workflow de GitHub Actions también ejecuta Terraform; sin `TF_STATE_BUCKET` crearía una segunda copia de la infraestructura.

### Vía A: GitHub Actions (recomendada)

1. Crea los secretos de GitHub (lista y cómo obtener cada uno en `docs/COMO-OBTENER-VALORES.md`).
2. Crea el bucket de estado y agrega `TF_STATE_BUCKET`.
3. Haz push a la rama `release/1.0`. El workflow ejecuta las pruebas, Terraform (etapas 1 y 2), sube las imágenes a ECR y reinicia los contenedores.

### Vía B: script local

```bash
cd /c/Users/<TU_USUARIO>/<CARPETA>/PideAlToke/desarrollo
aws sts get-caller-identity                 # credenciales vigentes
terraform -version
./infra/scripts/desplegar-aws.sh            # etapa 1 + etapa 2 (pide confirmar con "yes")
```

El script saca el ID de cuenta de tus credenciales y pasa a la etapa 2 la VPC y las subredes de la etapa 1. Los secretos salen de `infra/terraform_aws/etapa_2/terraform.tfvars` (ya viene completado; no se sube a git).

Después de `terraform apply` hay que subir las imágenes (el workflow lo hace solo en la vía A). A mano:

```bash
REGION=us-east-1
CUENTA=$(aws sts get-caller-identity --query Account --output text)
ECR=$CUENTA.dkr.ecr.$REGION.amazonaws.com
aws ecr create-repository --repository-name repo-backend  2>/dev/null || true
aws ecr create-repository --repository-name repo-frontend 2>/dev/null || true
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR
for s in ms-usuarios ms-catalogo ms-inventario ms-pedidos ms-mensajeria ms-kafka-admin ms-analitica ms-notificaciones; do
  docker build -t $ECR/repo-backend:$s ./backend/$s && docker push $ECR/repo-backend:$s
done
API=$(cd infra/terraform_aws/etapa_2 && terraform output -raw api_gateway_endpoint)
docker build --build-arg API_GATEWAY_URL=$API -t $ECR/repo-frontend:latest ./frontend/pidealtoke-frontend
docker push $ECR/repo-frontend:latest
```

Luego reinicia los contenedores del backend y del frontend (el workflow lo hace por SSM) o reemplaza las instancias con `terraform apply`.

## Verificar

```bash
cd infra/terraform_aws/etapa_2
terraform output kafka_ui_url rabbitmq_ui_url frontend_public_ip api_gateway_endpoint
```

- Kafka-UI (`kafka_ui_url`, usuario `kafka_ui_user`): *Brokers* = 3, *Topics* = `pedidos.eventos` e `inventario.movimientos` con 3 particiones y 3 réplicas, *Consumers* = `analitica-ventas` y `alertas-stock`.
- RabbitMQ (`rabbitmq_ui_url`): *Overview > Nodes* = 2 nodos; colas con sus DLQ.
- Los clusters tardan unos minutos tras el `apply`. Log de arranque: `/var/log/mensajeria-setup.log` en `mensajeria-ec2`.

## Administradores (ms-kafka-admin y ms-mensajeria)

Sus puertos (8006 y 8005) no están abiertos a internet a propósito. Para usarlos desde tu PC (requiere el plugin *Session Manager* de AWS CLI):

```bash
cd infra/terraform_aws/etapa_2
$(terraform output -raw ssm_port_forward_kafka_admin)       # deja abierto: http://localhost:8006/docs
```

Las rutas exigen un JWT de Entra ID con rol `ADMIN`.

## Apagar y borrar

```bash
./infra/scripts/desplegar-aws.sh destroy    # etapa 2 y luego etapa 1
```

Aviso: si cambias los compose o las claves, Terraform **reemplaza** `mensajeria-ec2` (`user_data_replace_on_change`) y se pierden los datos de Kafka y RabbitMQ.

## Desarrollo local

`./levantar-todo.sh` sigue levantando todo en tu PC con los mismos compose; sirve para desarrollar y probar sin gastar créditos de AWS.
