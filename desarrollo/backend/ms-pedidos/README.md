# Microservicio de Pedidos (`ms-pedidos`) - PideAlToke

Este microservicio forma parte del ecosistema Cloud Native **PideAlToke**. Está encargado de procesar la creación, consulta y ciclo de vida de los pedidos comerciales de la plataforma, construido sobre **FastAPI** (Python) y siguiendo el patrón de **Arquitectura Hexagonal (Ports and Adapters)**.

---

## 🏛️ Patrón de Diseño y Arquitectura

El microservicio utiliza **Arquitectura Hexagonal** para desacoplar completamente las reglas de negocio de las tecnologías externas (bases de datos, frameworks web, controladores).

### Estructura de Capas
* **Core (`app/core`)**: Configuración global de variables de entorno mediante `pydantic-settings` y gestión de seguridad JWT.
* **Domain (`app/domain`)**: El centro del hexágono. Contiene la lógica pura sin dependencias de frameworks.
  * `models/`: Entidades persistentes de la aplicación.
  * `ports/`: Interfaces abstractas (`ABC`) que definen contratos para interactuar con capas externas.
  * `services/`: Casos de uso y reglas de negocio (ej. cálculo automático de montos de pedidos).
* **Schemas (`app/schemas`)**: DTOs (Data Transfer Objects) definidos con **Pydantic** para la validación estricta de entrada y salida de datos.
* **Infrastructure (`app/infrastructure`)**: Adaptadores de salida (*Outbound Adapters*).
  * `db/`: Gestión de sesiones y conexiones ORM mediante **SQLAlchemy**.
  * `repositories/`: Implementación concreta de los puertos usando la base de datos.
* **Adapters (`app/adapters`)**: Adaptadores de entrada (*Inbound Adapters*).
  * `api/v1/routers/`: Enrutadores de FastAPI (`APIRouter`) que reciben las peticiones HTTP y las delegan al servicio de dominio.

---

## 🚀 Qué hace

Prefijo `/api/v1`. Cada ruta de colección acepta con y sin `/` final.

| Método | Ruta | Requiere | Descripción |
|---|---|---|---|
| POST | `/pedidos` | token válido | crea un pedido (reserva stock) |
| GET | `/pedidos` | token válido | mis pedidos; con `?todos=true` (solo `ADMIN`) los de todos |
| GET | `/pedidos/{id}` | dueño o `ADMIN` | detalle (un pedido ajeno responde 404) |
| POST | `/pedidos/{id}/cancelar` | dueño o `ADMIN` | cancela un pedido `PENDIENTE` y **libera** su stock |
| POST | `/pedidos/{id}/confirmar` | `ADMIN` | confirma un pedido `PENDIENTE` y **descuenta** el stock en firme |

### Qué envía el cliente y qué decide el servidor

El body de `POST /pedidos` solo lleva los items (`sku` y `cantidad`):

```json
{ "items": [ { "sku": "PROD-HAMB-001", "cantidad": 2 } ] }
```

- **El precio** de cada item lo toma el servidor de `ms-catalogo` (`GET /productos/sku/{sku}`). Si el body trae `precio_unitario`, se ignora.
- **El cliente** sale del JWT (`oid`, o `sub`). Si el body trae `cliente_id`, se ignora.
- Un SKU repetido se consolida en una línea. Un producto inexistente o inactivo responde 422.

### Ciclo de vida

`PENDIENTE` (stock reservado) → `CONFIRMADO` o `CANCELADO`. Confirmar y cancelar son idempotentes y **reintentables**: si `ms-inventario` falla a mitad, el progreso por item queda guardado y al reintentar no se libera ni confirma dos veces lo ya procesado.

### Creación con compensación

1. Se consulta el precio de cada SKU a `ms-catalogo` (falla rápido, antes de reservar nada).
2. Se reserva stock item por item en `ms-inventario`.
3. Si algo falla (sin stock, inventario caído, error al guardar), se **libera lo ya reservado** y se propaga el error original; un fallo al compensar se registra en el log pero nunca lo tapa.
4. Errores: 409 sin stock o estado inválido, 422 producto no disponible, 404 pedido inexistente, 503 si Catálogo o Inventario no responden. Cualquier otro error es un 500 real (antes se convertía en un 400 engañoso).

---

## 🔗 Integración con otros servicios

Variables en `.env` (ver `.env.example`):

```
INVENTARIO_SERVICE_URL="http://localhost:8003"
CATALOGO_SERVICE_URL="http://localhost:8002"
INTERNAL_API_KEY="..."    # debe ser idéntica a la de ms-inventario
```

Las llamadas reenvían el **JWT del usuario** (propagación de identidad). Las de stock llevan además `X-Internal-Key`; si `ms-inventario` la rechaza, el error indica revisar `INTERNAL_API_KEY` en ambos servicios.

---

## 🧪 Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Servicio (precio real, compensación, cancelar/confirmar, reintentos), router con JWT y clientes simulados, y los clientes HTTP de Inventario y Catálogo. Usan una SQLite temporal.

---

## 🐳 Docker

```bash
docker build -t ms-pedidos .
docker run --env-file .env -p 8004:8000 ms-pedidos
```

El contenedor escucha en el **8000**; docker compose y Terraform lo publican en el 8004.

---

## 🔜 Pendiente

Hoy las llamadas a `ms-catalogo` y `ms-inventario` son **síncronas por HTTP**. `ms-pedidos` ya **publica eventos** de cambio de estado en RabbitMQ (ver README de `desarrollo/`), pero reservar, confirmar y cancelar stock sigue siendo HTTP síncrono. Migrar ese flujo a mensajería queda pendiente (requiere decidir idempotencia y qué ve el cliente cuando no hay stock), y además permitiría expirar reservas de pedidos que nunca se confirman ni se cancelan.
