# PideAlToke — Guía de levantamiento local (Docker Compose)

Esta guía levanta **todo el sistema en tu máquina**, sin tocar AWS ni Azure ni el pipeline de CI/CD: base de datos, los microservicios backend (4 de negocio + administradores, analítica y notificaciones), un cluster de RabbitMQ (2 nodos), un cluster de Kafka (3 Zookeeper + 3 brokers) con Kafka-UI, un gateway local (nginx) que simula el API Gateway de AWS, y el frontend Angular.

## 1. Prerrequisitos

- [Docker](https://docs.docker.com/get-docker/) y Docker Compose v2 (viene incluido con Docker Desktop).
- Verifica que los tengas:
  ```bash
  docker --version
  docker compose version
  ```
- Puertos libres en tu máquina: `3306`, `4200`, `5672`, `5673`, `8001`-`8008`, `8080`, `8090`, `9092`-`9094`, `15672`, `15673`. Memoria: el cluster de Kafka + RabbitMQ necesita unos 4 GB libres para Docker. Si alguno ya lo usa otro programa (por ejemplo un MySQL local en el 3306), cámbialo en el `.env` (ver paso 3).

## 2. Configura las variables de entorno

```bash
cd desarrollo
cp .env.example .env
```

Los valores de `.env.example` sirven tal cual para probar en local, pero **conviene cambiar las claves** (`DB_PASS_*` e `INTERNAL_API_KEY`) por valores propios, por ejemplo con `openssl rand -hex 16`. Usa solo letras y números: las contraseñas van dentro de una URL de conexión. También puedes cambiar algún puerto si hay conflicto local.

- `DB_ROOT_PASSWORD`: solo para administrar la base. **Ningún microservicio usa `root`**: cada uno se conecta con su propio usuario (`svc_usuarios`, `svc_catalogo`, `svc_inventario`, `svc_pedidos`), que solo tiene permisos sobre su propia base y no puede hacer `DROP` ni crear usuarios.
- `INTERNAL_API_KEY`: clave compartida entre `ms-pedidos` y `ms-inventario` (ver "Seguridad entre microservicios").

## 3. Levanta todo

El sistema se reparte en **cuatro archivos compose** que comparten la red externa `pidealtoke-net`:

| Archivo | Qué levanta |
|---|---|
| `docker-compose.rabbitmq.yml` | Cluster RabbitMQ de 2 nodos (`rabbit1`, `rabbit2`) con colas espejadas |
| `docker-compose.kafka.yml` | 3 Zookeeper + 3 brokers Kafka + creación de los 2 tópicos (3 particiones, 3 réplicas) |
| `docker-compose.kafka-ui.yml` | Kafka-UI (administración y monitoreo de brokers, tópicos y consumer groups) |
| `docker-compose.yml` | Base de datos, microservicios, gateway y frontend |

Lo más simple es el script, que crea la red y los levanta en orden:

```bash
cd desarrollo
./levantar-todo.sh
```

Equivale a:

```bash
docker network create pidealtoke-net          # una sola vez
docker compose -f docker-compose.rabbitmq.yml up -d
docker compose -f docker-compose.kafka.yml up -d
docker compose -f docker-compose.kafka-ui.yml up -d
docker compose -f docker-compose.yml up --build -d
```

La primera vez tarda varios minutos (imágenes de Kafka/RabbitMQ, build de las imágenes de backend y de Angular). Los microservicios reintentan la conexión a los brokers, así que el orden de arranque no es crítico; si solo quieres la app sin mensajería, `docker compose up` del archivo principal funciona igual (los productores no bloquean las peticiones; los consumidores reintentan en segundo plano).

Para apagar: `./levantar-todo.sh down` (agrega `-v` para borrar también los volúmenes).

## 4. Accede a la aplicación

| Servicio | URL | Qué es |
|---|---|---|
| **Frontend (Angular)** | http://localhost:4200 | La app que vas a usar desde el navegador |
| Gateway local | http://localhost:8080 | Reverse proxy que enruta `/api/v1/...` a cada microservicio (lo usa el frontend internamente, no necesitas abrirlo a mano) |
| ms-usuarios | http://localhost:8001/api/v1/users/me | Directo, para debug |
| ms-catalogo | http://localhost:8002/api/v1/productos | Directo, para debug |
| ms-inventario | http://localhost:8003/api/v1/inventario | Directo, para debug |
| ms-pedidos | http://localhost:8004/api/v1/pedidos | Directo, para debug |
| RabbitMQ (consola web) | http://localhost:15672 (nodo 2: :15673) | Usuario/clave `RABBITMQ_USER` / `RABBITMQ_PASSWORD` (por defecto `admin` / `admin123`, solo en loopback). *Overview → Nodes* muestra el cluster |
| Kafka-UI | http://localhost:8090 | Usuario/clave `KAFKA_UI_USER` / `KAFKA_UI_PASSWORD` (por defecto `admin` / `admin123`, solo en loopback) |
| ms-kafka-admin | http://localhost:8006/docs | Administración de Kafka (`/api/kafka/...`); exige JWT con rol `ADMIN` |
| ms-analitica | http://localhost:8007/api/v1/analitica/ventas/resumen | Analítica en tiempo real desde Kafka; rol `ADMIN` |
| ms-notificaciones | http://localhost:8008/api/v1/notificaciones | Notificaciones desde RabbitMQ; rol `ADMIN` |
| ms-mensajeria | http://localhost:8005/docs | Administración de RabbitMQ (`/api/rabbitmq/...`); exige JWT con rol `ADMIN` |
| MariaDB | localhost:3306 | Administración: usuario `root` (`DB_ROOT_PASSWORD`). Los servicios usan `svc_*` |

Abre **http://localhost:4200** en el navegador. En `localhost` el frontend se sirve por HTTP; en cualquier otro host (la IP pública de AWS) nginx redirige a HTTPS, porque MSAL necesita un contexto seguro.

> **Nota sobre el login:** la app usa Azure Entra ID (MSAL) para autenticar, con el mismo `clientId`/`tenantId` que en producción (están hardcodeados en `environment.ts`). Necesitas una cuenta válida de ese tenant de Azure para poder loguearte y que las llamadas autenticadas funcionen — esto no es algo que dependa de tu entorno local, es igual en AWS.

## 5. Verifica que el catálogo tenga datos de ejemplo

Los 20 productos de ejemplo se cargan automáticamente la **primera vez** que se crea el volumen de la base de datos, vía `desarrollo/init-db/`: `init-01.sql` (crea las 4 bases y tablas), `init-02-seed.sql` (productos y stock inicial de cada SKU) e `init-03-users.sh` (usuarios por microservicio). Estos mismos archivos los usa Terraform para la base de AWS: son la única fuente de verdad. Puedes confirmarlo con:

```bash
curl http://localhost:8002/api/v1/productos
```

Si ya habías levantado el proyecto antes con datos distintos y quieres reiniciar la base desde cero (borra todo lo que tengas guardado):
```bash
docker compose down -v
docker compose up --build
```
El flag `-v` borra el volumen `mariadb_data`, así los scripts de `init-db` se vuelven a ejecutar.

## 6. Comandos útiles

```bash
# Ver logs de un servicio en particular
docker compose logs -f ms-usuarios

# Ver logs de todo
docker compose logs -f

# Reconstruir solo un servicio (por ejemplo, después de tocar código del frontend)
docker compose up --build frontend

# Parar todo (sin borrar datos)
docker compose down

# Parar todo y borrar también la base de datos
docker compose down -v

# Entrar a la base de datos directamente
docker exec -it pidealtoke-db mariadb -u root -p   # administración (root)
```

## 7. Solución de problemas comunes

**El frontend carga pero las peticiones a la API fallan / CORS**
Revisa en la consola del navegador (F12) el error exacto. Si dice CORS, confirma que los `main.py` de los microservicios tengan configurado el `CORSMiddleware`. Si dice `ERR_CONNECTION_REFUSED` hacia `localhost:8080`, confirma que el contenedor `gateway` esté corriendo (`docker compose ps`).

**`docker compose up` falla porque un puerto ya está en uso**
Cambia el puerto en tu `.env` (por ejemplo `PORT_MS_USUARIOS=8011` en vez de `8001`) y vuelve a levantar. No hace falta tocar ningún otro archivo — todos los puertos se toman de `.env`.

**`docker compose up` dice `Falta DB_PASS_... en .env`**
Tu `.env` es de una versión anterior. Copia de nuevo las variables nuevas desde `.env.example` (`DB_PASS_*`, `INTERNAL_API_KEY`). Si ya tenías la base creada, haz `docker compose down -v` para que se ejecute `init-03-users.sh`.

**La base de datos tarda en estar lista y los microservicios se reinician al principio**
Es normal: `db` tiene un `healthcheck` y los demás servicios usan `depends_on: condition: service_healthy`, así que Compose espera a que MariaDB esté realmente lista antes de arrancarlos. Si de todas formas ves reintentos al principio, dale unos segundos más.

Las variables de entorno se leen al levantar los contenedores. Después de editar `.env`, corre:
```bash
docker compose down
docker compose up --build
```

## 8. Tests

```bash
# Backend (por servicio): usa una SQLite temporal, no necesita .env ni Docker
cd backend/ms-pedidos
pip install -r requirements-dev.txt
python -m pytest -q

# Opcional: correr los tests contra una MariaDB real (por ejemplo para verificar la atomicidad en InnoDB)
TEST_DATABASE_URL="mysql+pymysql://svc_inventario:CLAVE@127.0.0.1:3306/inventario_db" python -m pytest -q

# Frontend
cd frontend/pidealtoke-frontend
npm ci && npx ng test --watch=false
```

En CI (`deploy.yml`) los tests corren antes del despliegue; si fallan, no se despliega.

## 9. Despliegue a AWS y Azure

Corre automáticamente con GitHub Actions al pushear a `release/1.0` (`.github/workflows/deploy.yml`): tests de los 8 servicios, Terraform (etapa 1: red; etapa 2: EC2 de frontend, backend, base de datos y mensajería, y API Gateway), subida de imágenes a ECR y reinicio de contenedores por SSM.

**Secretos de GitHub necesarios** (Settings → Secrets and variables → Actions):

| Secreto | Para qué |
|---|---|
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_REGION`, `AWS_ACCOUNT_ID` | Credenciales y cuenta de AWS |
| `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` | Validación de tokens (API Gateway y microservicios) |
| `ECR_BACKEND_REPO`, `ECR_FRONTEND_REPO` | Nombres de los repositorios ECR |
| `DB_PASSWORD` | Root de MariaDB; de ella se derivan las contraseñas `svc_*` de cada servicio |
| `INTERNAL_API_KEY` | Clave entre `ms-pedidos` y `ms-inventario` (mínimo 16 caracteres, aleatoria) |
| `RABBITMQ_PASSWORD`, `RABBITMQ_ERLANG_COOKIE`, `KAFKA_UI_PASSWORD` | Claves de la EC2 de mensajería. **Solo letras y números, mínimo 12 (cookie: 16)**; genera cada una con `openssl rand -hex 16` |
| `TF_STATE_BUCKET` *(opcional, recomendado)* | Bucket S3 para el estado de Terraform |

> **Estado de Terraform:** sin `TF_STATE_BUCKET`, el estado vive solo en el runner y se pierde al terminar: cada push crearía una VPC, NAT y EC2 nuevas, y la infraestructura no se podría actualizar ni destruir desde CI. Con el bucket, cada push actualiza la misma infraestructura. Si un paso falla, el workflow destruye lo creado (primero la etapa 2 y luego la 1); con estado remoto solo lo hace si falló un `apply`.

**Azure (`infra/terraform_azure/etapa_1`)** crea el registro de la app con todo lo que el login necesita: scope `access_as_user` ("Expose an API"), App Role `ADMIN`, tokens v2 y redirect URIs. Pasos:

1. `az login`, `cd infra/terraform_azure/etapa_1`, copia `terraform.tfvars.example` a `terraform.tfvars` y complétalo (`admin_user_object_ids` asigna el rol ADMIN sin pasar por el portal).
2. Si la app ya existía, **impórtala antes** del primer `apply` (ver comentarios en `main.tf`); si no, se creará una app nueva con otro `client_id`.
3. Tras cada despliegue en AWS, agrega `https://<IP del frontend>` a `extra_redirect_urls` y vuelve a aplicar: la IP pública de una EC2 cambia en cada despliegue nuevo.

El `client_id` y el `tenant_id` de `environment.ts` no son secretos (son públicos en cualquier SPA), pero deben coincidir con tu app de Azure.

**Mensajería en AWS (`etapa_2/mensajeria.tf`):** una EC2 aparte (`mensajeria-ec2`, `t3.large`, 30 GB) levanta con Docker los **mismos** 3 compose que en local (`docker-compose.rabbitmq.yml`, `.kafka.yml`, `.kafka-ui.yml`; Terraform los lee de este repo, no hay copias): cluster RabbitMQ de 2 nodos, 3 Zookeeper + 3 brokers Kafka con los 2 tópicos (3 particiones, 3 réplicas) y Kafka-UI. El backend (`backend-ec2`, ahora `t3.small`) corre los 8 microservicios y se conecta a los brokers por la **IP privada** de esa EC2.

- **Por qué t3.large:** los clusters usan ~4,5 GB de RAM; en una `t2.micro` no arrancan. Si tu cuenta no permite ese tipo, baja a `t3.medium` solo si aceptas ir justo (`messaging_instance_type`).
- **Seguridad:** AMQP (5672) y Kafka (9092-9094) solo se aceptan desde el security group del backend. Las consolas web (RabbitMQ 15672/15673, Kafka-UI 8090) piden usuario y clave y se abren a `messaging_admin_cidr` (por defecto todo Internet para la demo; pon tu IP/32 si puedes). `ms-mensajeria` (8005) y `ms-kafka-admin` (8006) no se publican: úsalos por SSM (`aws ssm start-session --target <id> --document-name AWS-StartPortForwardingSession --parameters portNumber=8006,localPortNumber=8006`).
- **URLs:** el resumen del workflow muestra la consola de RabbitMQ y Kafka-UI (`terraform output rabbitmq_ui_url kafka_ui_url`). Tras el despliegue, los clusters tardan unos minutos más en estar listos; el log de arranque está en `/var/log/mensajeria-setup.log` de la EC2.
- **Reemplazo de instancias:** `user_data` solo corre una vez por instancia, así que `backend-ec2` y `mensajeria-ec2` tienen `user_data_replace_on_change`: cambiar los compose o las claves **reemplaza** la instancia y se pierden los datos de Kafka/RabbitMQ (ms-analitica los reconstruye relevendo Kafka solo si el log sigue existiendo).
- **Costo:** t3.large corre ~US$0,08/h. En AWS Academy apaga el laboratorio al terminar; las EC2 se detienen, y al reiniciar el lab las IP públicas cambian (revisa los outputs y `extra_redirect_urls` en Azure).

**Red en AWS:** el API Gateway no usa VPC Link, así que llega al backend por su IP pública y los puertos 8001-8004 y 8007-8008 quedan abiertos (8005 y 8006, administrativos, no). Cada microservicio valida el JWT por su cuenta y los endpoints internos de stock exigen `X-Internal-Key`. Para cerrar esos puertos hace falta mover el backend a la subred privada con un VPC Link (puede estar restringido en AWS Academy).

## Seguridad entre microservicios (INTERNAL_API_KEY)

Los movimientos de stock `reservar`, `liberar` y `confirmar-salida` de `ms-inventario` son de uso
interno: solo `ms-pedidos` puede llamarlos, enviando el header `X-Internal-Key`. Un usuario con JWT
valido pero sin esa clave recibe 403.

- **Local:** define `INTERNAL_API_KEY` en tu `.env` (ver `.env.example`). Debe llegar igual a `ms-inventario` y `ms-pedidos` (el compose ya lo hace).
- **AWS / CI:** crea el secreto de GitHub `INTERNAL_API_KEY` (minimo 16 caracteres, aleatorio). El workflow lo pasa a Terraform (`internal_api_key`).
- Si la variable queda vacia, `ms-inventario` rechaza esos endpoints (falla cerrado).

## Ciclo de vida de un pedido

`PENDIENTE` (stock reservado) → `CONFIRMADO` (`POST /pedidos/{id}/confirmar`, rol ADMIN, descuenta stock en firme)
o `CANCELADO` (`POST /pedidos/{id}/cancelar`, dueño o ADMIN, libera la reserva).
El precio de cada item sale de `ms-catalogo` y el cliente del JWT; el body solo lleva `sku` y `cantidad`.

## Mensajería: RabbitMQ y Kafka

Los dos brokers conviven y **cada uno hace lo que mejor sabe hacer**; Kafka se suma sin cambiar las integraciones previas con RabbitMQ (si uno falla, el otro igual recibe el evento).

- **RabbitMQ = trabajo y notificaciones.** Mensajes que alguien debe *procesar una vez* (ACK manual, reintentos, DLQ): colas con consumidor.
- **Kafka = historial de eventos y analítica.** Un log ordenado y retenido que varios consumidores leen a su ritmo (cada *consumer group* recibe todo) y que se puede **releer** (reconstruir estadísticas tras un reinicio).

### RabbitMQ (cluster de 2 nodos)

3 colas de trabajo, cada una con su DLQ (`pidealtoke.dlx`, DIRECT), sobre exchanges TOPIC y DIRECT:

| Cola (DLQ = `<cola>.dlq`) | Exchange (tipo) | Routing key | Productor → Consumidor |
|---|---|---|---|
| `inventario.pedidos` | `pedidos.events` (TOPIC) | `pedido.*` | `ms-pedidos` → `ms-inventario` |
| `notificaciones.pedidos` | `pedidos.events` (TOPIC) | `pedido.confirmado`, `pedido.cancelado` | `ms-pedidos` → `ms-notificaciones` |
| `alertas.stock` | `pidealtoke.alertas` (DIRECT) | `stock.bajo` | `ms-inventario` → `ms-notificaciones` |

| Servicio | Rol |
|---|---|
| `ms-pedidos` | **Productor.** Publica `pedido.creado/confirmado/cancelado` en `pedidos.events` con *Publisher Confirms*. Mejor esfuerzo: un broker caído no rompe el pedido. |
| `ms-inventario` | **Consumidor** de `inventario.pedidos` (ACK manual, reintentos con backoff, DLQ; hoy solo registra el evento) y **productor** de la alerta `stock.bajo` cuando una salida deja el stock en o bajo `umbral_minimo` (solo al *cruzar* el umbral, sin repetir). |
| `ms-notificaciones` | **Consumidor** de `notificaciones.pedidos` y `alertas.stock` (un manager por cola, handlers separados por dominio). Genera la notificación (hoy: log + `GET /api/v1/notificaciones`), descarta duplicados por `event_id`, y manda payloads inválidos a la DLQ. |
| `ms-mensajeria` | **Administrador** REST de colas, exchanges y bindings (`/api/rabbitmq/...`, rol `ADMIN`). |

Cada servicio declara la topología que le pertenece (`app/infrastructure/messaging/rabbitmq_config.py`); los nombres salen de `app/core/config.py` / variables `RABBITMQ_*`. El cluster (`docker-compose.rabbitmq.yml`) forma los 2 nodos por `classic_config` y `rabbitmq-setup` aplica una política de espejado (`ha-mode: all`) a las colas `inventario.*`, `notificaciones.*` y `alertas.*`, DLQ incluidas.

Para ver la DLQ en acción: publica un mensaje inválido en `pedidos.events` con routing key `pedido.confirmado` desde la consola web y mira cómo termina en `notificaciones.pedidos.dlq`.

### Dashboard de analítica (Angular)

La vista **Analítica** (`/analitica`, solo se muestra a cuentas con rol `ADMIN`) refresca cada 5 s y junta las dos mensajerías: ventas, productos top, stock y alertas (de Kafka, `ms-analitica`) y las últimas notificaciones (de RabbitMQ, `ms-notificaciones`). Cada fuente es independiente: si una cae, las demás siguen actualizándose y la sección afectada conserva su último dato. Para verla en la demo: crea un pedido, confírmalo y mira cómo cambian las cifras sin recargar.

### Kafka (3 Zookeeper + 3 brokers)

| Tópico | Particiones / réplicas | Key | Retención | Productor → Consumidor (consumer group) |
|---|---|---|---|---|
| `pedidos.eventos` | 3 / 3 | `pedido_id` | 30 días | `ms-pedidos` → `ms-analitica` (`analitica-ventas`) |
| `inventario.movimientos` | 3 / 3 | `sku` | 7 días | `ms-inventario` → `ms-analitica` (`alertas-stock`) |

Ambos con `cleanup.policy=delete` y `min.insync.replicas=2`; productores con `acks=all` + idempotencia. La *key* fija la partición, así los eventos de un mismo pedido o SKU llegan en orden. Diseño completo (casos de uso, modelo JSON de cada mensaje, justificación de particiones/réplicas): [`docs/EP3-kafka-diseno.md`](docs/EP3-kafka-diseno.md).

| Servicio | Rol |
|---|---|
| `ms-pedidos` / `ms-inventario` | **Productores** (`KAFKA_ENABLED=true`): cada cambio de pedido / movimiento de stock se publica como evento JSON (DTO tipado). |
| `ms-analitica` | **Consumidor** (2 consumer groups, `KAFKA_CONSUMER_CONCURRENCY=3` consumidores por grupo = 1 partición cada uno). Commit manual, reintentos con backoff, mensajes inválidos descartados con log y contados en `/api/v1/analitica/metricas`. Mantiene en memoria ventas, top de productos, stock y alertas; al arrancar relee el log (idempotente por offset). |
| `ms-kafka-admin` | **Administrador** REST (`/api/kafka/...`, rol `ADMIN`): crear / listar / describir / modificar configuración / aumentar particiones / eliminar tópicos, y listar consumer groups con su **lag**. |

Sin `KAFKA_ENABLED=true` (valor por defecto fuera de compose) los servicios no tocan el cluster.

