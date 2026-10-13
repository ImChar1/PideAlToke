# PideAlToke — Guía de levantamiento local (Docker Compose)

Esta guía levanta **todo el sistema en tu máquina**, sin tocar AWS ni Azure ni el pipeline de CI/CD: base de datos, los 4 microservicios backend, un gateway local (nginx) que simula el API Gateway de AWS, y el frontend Angular.

## 1. Prerrequisitos

- [Docker](https://docs.docker.com/get-docker/) y Docker Compose v2 (viene incluido con Docker Desktop).
- Verifica que los tengas:
  ```bash
  docker --version
  docker compose version
  ```
- Puertos libres en tu máquina: `3306`, `4200`, `5672`, `8001`, `8002`, `8003`, `8004`, `8005`, `8080`, `15672`. Si alguno ya lo usa otro programa (por ejemplo un MySQL local en el 3306), cámbialo en el `.env` (ver paso 3).

## 2. Configura las variables de entorno

```bash
cd desarrollo
cp .env.example .env
```

Los valores de `.env.example` sirven tal cual para probar en local, pero **conviene cambiar las claves** (`DB_PASS_*` e `INTERNAL_API_KEY`) por valores propios, por ejemplo con `openssl rand -hex 16`. Usa solo letras y números: las contraseñas van dentro de una URL de conexión. También puedes cambiar algún puerto si hay conflicto local.

- `DB_ROOT_PASSWORD`: solo para administrar la base. **Ningún microservicio usa `root`**: cada uno se conecta con su propio usuario (`svc_usuarios`, `svc_catalogo`, `svc_inventario`, `svc_pedidos`), que solo tiene permisos sobre su propia base y no puede hacer `DROP` ni crear usuarios.
- `INTERNAL_API_KEY`: clave compartida entre `ms-pedidos` y `ms-inventario` (ver "Seguridad entre microservicios").

## 3. Levanta todo

Desde `desarrollo/` (donde está `docker-compose.yml`):

```bash
docker compose up --build
```

La primera vez tarda varios minutos (build de las 4 imágenes de backend + build de Angular). Vas a ver en la consola cómo van levantando, en este orden:

1. `db` (MariaDB) — espera a pasar su healthcheck antes de que arranque lo demás.
2. `ms-usuarios`, `ms-catalogo`, `ms-inventario` (en paralelo).
3. `ms-pedidos` (depende de `ms-inventario` para reservar/liberar stock).
4. `gateway` (nginx reverse-proxy local).
5. `frontend` (build de Angular + nginx sirviendo el build).

Si prefieres dejarlo corriendo en segundo plano:
```bash
docker compose up --build -d
```

## 4. Accede a la aplicación

| Servicio | URL | Qué es |
|---|---|---|
| **Frontend (Angular)** | http://localhost:4200 | La app que vas a usar desde el navegador |
| Gateway local | http://localhost:8080 | Reverse proxy que enruta `/api/v1/...` a cada microservicio (lo usa el frontend internamente, no necesitas abrirlo a mano) |
| ms-usuarios | http://localhost:8001/api/v1/users/me | Directo, para debug |
| ms-catalogo | http://localhost:8002/api/v1/productos | Directo, para debug |
| ms-inventario | http://localhost:8003/api/v1/inventario | Directo, para debug |
| ms-pedidos | http://localhost:8004/api/v1/pedidos | Directo, para debug |
| RabbitMQ (consola web) | http://localhost:15672 | Usuario/clave `RABBITMQ_USER` / `RABBITMQ_PASSWORD` (por defecto `admin` / `admin123`, solo en loopback) |
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

Corre automáticamente con GitHub Actions al pushear a `release/1.0` (`.github/workflows/deploy.yml`): tests, Terraform (etapa 1: red; etapa 2: EC2, API Gateway), subida de imágenes a ECR y reinicio de contenedores por SSM.

**Secretos de GitHub necesarios** (Settings → Secrets and variables → Actions):

| Secreto | Para qué |
|---|---|
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_REGION`, `AWS_ACCOUNT_ID` | Credenciales y cuenta de AWS |
| `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` | Validación de tokens (API Gateway y microservicios) |
| `ECR_BACKEND_REPO`, `ECR_FRONTEND_REPO` | Nombres de los repositorios ECR |
| `DB_PASSWORD` | Root de MariaDB; de ella se derivan las contraseñas `svc_*` de cada servicio |
| `INTERNAL_API_KEY` | Clave entre `ms-pedidos` y `ms-inventario` (mínimo 16 caracteres, aleatoria) |
| `TF_STATE_BUCKET` *(opcional, recomendado)* | Bucket S3 para el estado de Terraform |

> **Estado de Terraform:** sin `TF_STATE_BUCKET`, el estado vive solo en el runner y se pierde al terminar: cada push crearía una VPC, NAT y EC2 nuevas, y la infraestructura no se podría actualizar ni destruir desde CI. Con el bucket, cada push actualiza la misma infraestructura. Si un paso falla, el workflow destruye lo creado (primero la etapa 2 y luego la 1); con estado remoto solo lo hace si falló un `apply`.

**Azure (`infra/terraform_azure/etapa_1`)** crea el registro de la app con todo lo que el login necesita: scope `access_as_user` ("Expose an API"), App Role `ADMIN`, tokens v2 y redirect URIs. Pasos:

1. `az login`, `cd infra/terraform_azure/etapa_1`, copia `terraform.tfvars.example` a `terraform.tfvars` y complétalo (`admin_user_object_ids` asigna el rol ADMIN sin pasar por el portal).
2. Si la app ya existía, **impórtala antes** del primer `apply` (ver comentarios en `main.tf`); si no, se creará una app nueva con otro `client_id`.
3. Tras cada despliegue en AWS, agrega `https://<IP del frontend>` a `extra_redirect_urls` y vuelve a aplicar: la IP pública de una EC2 cambia en cada despliegue nuevo.

El `client_id` y el `tenant_id` de `environment.ts` no son secretos (son públicos en cualquier SPA), pero deben coincidir con tu app de Azure.

**Red en AWS:** el API Gateway no usa VPC Link, así que llega al backend por su IP pública y los puertos 8001-8004 quedan abiertos. Cada microservicio valida el JWT por su cuenta y los endpoints internos de stock exigen `X-Internal-Key`. Para cerrar esos puertos hace falta mover el backend a la subred privada con un VPC Link (puede estar restringido en AWS Academy).

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

## Mensajería (RabbitMQ)

`docker compose up` levanta un RabbitMQ (`rabbitmq:3.12-management-alpine`, volumen `rabbitmq_data`, misma red que el resto) y tres servicios lo usan:

| Servicio | Rol |
|---|---|
| `ms-pedidos` | **Productor.** Tras guardar un pedido publica `pedido.creado`, `pedido.confirmado` o `pedido.cancelado` en el exchange `pedidos.events` (TOPIC) con *Publisher Confirms*. Es mejor esfuerzo: si el broker está caído el pedido se completa igual y se registra el error. |
| `ms-inventario` | **Consumidor.** Cola `inventario.pedidos` (binding `pedido.*`), ACK manual, `prefetch` y concurrencia configurables, reintentos con backoff exponencial y, si fallan, `basic_nack(requeue=False)` hacia la DLQ `inventario.pedidos.dlq` (vía `pidealtoke.dlx`, DIRECT). **Hoy solo registra el evento**: el stock sigue moviéndose por HTTP síncrono. |
| `ms-mensajeria` | **Administrador** REST de colas, exchanges y bindings (`/api/rabbitmq/...`, rol `ADMIN`). Ver su README. |

Cada servicio declara la topología que le pertenece (`app/infrastructure/messaging/rabbitmq_config.py`): `ms-pedidos` el exchange; `ms-inventario` su cola, DLQ y bindings. Todos los nombres salen de `app/core/config.py` / variables de entorno (`RABBITMQ_*`); si cambias uno, cámbialo igual en los servicios que lo comparten. Sin `RABBITMQ_ENABLED=true` (valor por defecto fuera de compose) los servicios no tocan el broker.

Para ver la DLQ en acción: publica un mensaje inválido en `pedidos.events` con routing key `pedido.creado` desde la consola web y mira cómo termina en `inventario.pedidos.dlq` (un JSON roto va directo a la DLQ; un fallo transitorio se reintenta antes).

