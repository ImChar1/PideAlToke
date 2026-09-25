# PideAlToke — Guía de levantamiento local (Docker Compose)

Esta guía levanta **todo el sistema en tu máquina**, sin tocar AWS ni Azure ni el pipeline de CI/CD: base de datos, los 4 microservicios backend, un gateway local (nginx) que simula el API Gateway de AWS, y el frontend Angular.

## 1. Prerrequisitos

- [Docker](https://docs.docker.com/get-docker/) y Docker Compose v2 (viene incluido con Docker Desktop).
- Verifica que los tengas:
  ```bash
  docker --version
  docker compose version
  ```
- Puertos libres en tu máquina: `3306`, `4200`, `8001`, `8002`, `8003`, `8004`, `8080`. Si alguno ya lo usa otro programa (por ejemplo un MySQL local en el 3306), cámbialo en el `.env` (ver paso 3).

## 2. Antes de levantar: revisa que estos archivos existan

Por errores de copiado que fuimos arreglando, hay dos archivos que a veces faltan en el repo. Antes de correr nada, confirma que existan:

- `desarrollo/infra/local-gateway.conf`
- `desarrollo/.env.example`

Si no están, copia los que vienen junto a este README en sus mismas rutas (`desarrollo/infra/local-gateway.conf` y `desarrollo/.env.example`).

**Importante:** además, en `desarrollo/docker-compose.yml`, el servicio `gateway` debe montar `./infra/local-gateway.conf` (NO `./frontend/pidealtoke-frontend/nginx.conf`). Busca este bloque:

```yaml
  gateway:
    image: nginx:alpine
    container_name: pidealtoke-gateway
    ports:
      - "${PORT_GATEWAY}:80"
    volumes:
      - ./infra/local-gateway.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - ms-usuarios
      - ms-catalogo
      - ms-inventario
      - ms-pedidos
```

Si en tu copia dice `./frontend/pidealtoke-frontend/nginx.conf` en vez de `./infra/local-gateway.conf`, corrígelo — si no, el gateway monta la config equivocada y no arranca (nginx tira `host not found in upstream`).

## 3. Configura las variables de entorno

```bash
cd desarrollo
cp .env.example .env
```

Los valores por defecto de `.env.example` ya están pensados para que todo funcione sin tocar nada. Ábrelo solo si necesitas cambiar algún puerto por conflicto local.

## 4. Levanta todo

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

## 5. Accede a la aplicación

| Servicio | URL | Qué es |
|---|---|---|
| **Frontend (Angular)** | http://localhost:4200 | La app que vas a usar desde el navegador |
| Gateway local | http://localhost:8080 | Reverse proxy que enruta `/api/v1/...` a cada microservicio (lo usa el frontend internamente, no necesitas abrirlo a mano) |
| ms-usuarios | http://localhost:8001/api/v1/users/me | Directo, para debug |
| ms-catalogo | http://localhost:8002/api/v1/productos | Directo, para debug |
| ms-inventario | http://localhost:8003/api/v1/inventario | Directo, para debug |
| ms-pedidos | http://localhost:8004/api/v1/pedidos | Directo, para debug |
| MariaDB | localhost:3306 | Usuario `root`, password la que pusiste en `DB_ROOT_PASSWORD` |

Abre **http://localhost:4200** en el navegador — ahí debería cargar el frontend normalmente.

> **Nota sobre el login:** la app usa Azure Entra ID (MSAL) para autenticar, con el mismo `clientId`/`tenantId` que en producción (están hardcodeados en `environment.ts`). Necesitas una cuenta válida de ese tenant de Azure para poder loguearte y que las llamadas autenticadas funcionen — esto no es algo que dependa de tu entorno local, es igual en AWS.

## 6. Verifica que el catálogo tenga datos de ejemplo

Los 20 productos de ejemplo se cargan automáticamente la **primera vez** que se crea el volumen de la base de datos, vía `desarrollo/init-db/init-01.sql` (crea las 4 bases y tablas) e `init-02-seed.sql` (inserta los productos). Puedes confirmarlo con:

```bash
curl http://localhost:8002/api/v1/productos
```

Si ya habías levantado el proyecto antes con datos distintos y quieres reiniciar la base desde cero (borra todo lo que tengas guardado):
```bash
docker compose down -v
docker compose up --build
```
El flag `-v` borra el volumen `mariadb_data`, así los scripts de `init-db` se vuelven a ejecutar.

## 7. Comandos útiles

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
docker exec -it pidealtoke-db mariadb -u root -p
```

## 8. Solución de problemas comunes

**`nginx: [emerg] host not found in upstream "ms-usuarios"` en el contenedor `gateway` o `frontend`**
El `nginx.conf` del frontend (`desarrollo/frontend/pidealtoke-frontend/nginx.conf`) tiene mezclado el contenido del gateway. El frontend solo debe servir archivos estáticos (`try_files $uri $uri/ /index.html`), sin ningún `proxy_pass`. El `local-gateway.conf` (con los `proxy_pass` a `ms-usuarios`, etc.) va aparte, en `desarrollo/infra/local-gateway.conf`, y solo lo usa el servicio `gateway`.

**El frontend carga pero las peticiones a la API fallan / CORS**
Revisa en la consola del navegador (F12) el error exacto. Si dice CORS, confirma que los 4 `main.py` de los microservicios tengan `allow_origins=["*"]` en el `CORSMiddleware`. Si dice `ERR_CONNECTION_REFUSED` hacia `localhost:8080`, confirma que el contenedor `gateway` esté corriendo (`docker compose ps`).

**`docker compose up` falla porque un puerto ya está en uso**
Cambia el puerto en tu `.env` (por ejemplo `PORT_MS_USUARIOS=8011` en vez de `8001`) y vuelve a levantar. No hace falta tocar ningún otro archivo — todos los puertos se toman de `.env`.

**La base de datos tarda en estar lista y los microservicios se reinician al principio**
Es normal: `db` tiene un `healthcheck` y los demás servicios usan `depends_on: condition: service_healthy`, así que Compose espera a que MariaDB esté realmente lista antes de arrancarlos. Si de todas formas ves reintentos al principio, dale unos segundos más.

Las variables de entorno se leen al levantar los contenedores. Después de editar `.env`, corre:
```bash
docker compose down
docker compose up --build
```

## 9. Qué NO cubre esta guía

Esto es solo para desarrollo local. Para desplegar a AWS (Terraform + ECR + EC2 + API Gateway) el flujo es distinto y corre automáticamente vía GitHub Actions al pushear a la rama `release/1.0` (`.github/workflows/deploy.yml`). La configuración de Terraform para AWS y Azure vive en `desarrollo/infra/terraform_aws/` y `desarrollo/infra/terraform_azure/`, y no se ejecuta como parte de este flujo local.
