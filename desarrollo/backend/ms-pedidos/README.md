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

## 🚀 Componentes Desarrollados en esta Fase

1. **Configuración Base (`core/config.py` & `infrastructure/db/session.py`)**: Lectura del archivo `.env` y creación de la sesión ORM dinámicamente.
2. **Entidad Pedido (`domain/models/pedido.py`)**: Mapeo relacional con timestamp compatible mediante `func.now()`. Persiste `items` como JSON (sku, cantidad, precio_unitario) para poder liberar stock reservado si el pedido se cancela.
3. **DTOs de Transferencia (`schemas/schema_pedido.py`)**: Esquemas de validación para entrada (`CrearPedidoSchema`) y salida (`PedidoResponseSchema`). Los items se identifican por **`sku`** (no por id numérico), para calzar con `ms-catalogo` y `ms-inventario`.
4. **Puerto y Repositorio (`domain/ports/` & `infrastructure/repositories/`)**: Contrato e implementación concreta utilizando SQLAlchemy.
5. **Servicio de Dominio (`domain/services/pedido_service.py`)**: Calcula el monto total, **reserva stock en `ms-inventario` item por item**, y si algo falla a mitad de camino, **libera lo ya reservado** (compensación) antes de fallar — el pedido nunca se persiste si no hay stock.
6. **Cliente HTTP a Inventario (`infrastructure/clients/inventario_client.py` + `domain/ports/inventario_client_port.py`)**: Adaptador de salida (Outbound Adapter) que llama a `POST /inventario/{sku}/reservar` y `/liberar` en `ms-inventario`, **reenviando el JWT del usuario** para propagar la identidad entre microservicios.
7. **Seguridad JWT (`core/security.py`)**: Validación real contra Azure AD (JWKS, issuer, audience) — antes este archivo estaba vacío y el endpoint no exigía token.
8. **Enrutador HTTP (`adapters/api/v1/routers/pedidos_router.py`)**: `POST /pedidos/` (crea pedido, requiere JWT) y `GET /pedidos/{id}` (consulta).

### 🐛 Bugs corregidos en esta fase
- `PedidoModel.cleinte_id` (typo) no calzaba con `PedidoModel(cliente_id=...)` en el service → el endpoint de crear pedido nunca había funcionado.
- `PedidoResponseSchema.Config` estaba mal indentado (fuera de la clase) → faltaba `from_attributes`, necesario para serializar el objeto SQLAlchemy como respuesta.
- `core/security.py` estaba vacío → el endpoint no validaba JWT en absoluto.

---

## 🔗 Integración con ms-inventario

Al crear un pedido:
1. Por cada item, se llama a `POST {INVENTARIO_SERVICE_URL}/inventario/{sku}/reservar`.
2. Si algún item no tiene stock suficiente (`409`) o el sku no existe (`404`), se libera lo ya reservado en los items anteriores y se responde `409`/`503` al cliente — **el pedido no se crea**.
3. Solo si todas las reservas se realizan con éxito, el pedido se persiste en estado `PENDIENTE`.

Configura la URL de Inventario en `.env`:
```
INVENTARIO_SERVICE_URL="http://localhost:8001"
```

---

## 🧪 Tests

```bash
pip install -r requirements-dev.txt
pytest
```
7 tests: reglas de negocio del `PedidoService` (reserva, compensación, cálculo de monto) con fakes en memoria, e integración del router con JWT y cliente de Inventario simulados.

---

## 🐳 Docker

```bash
docker build -t ms-pedidos .
docker run --env-file .env -p 8080:8080 ms-pedidos
```

---

## 🐳 Próxima Etapa: Migración a MariaDB

Actualmente, el microservicio está preparado para pruebas locales inmediatas usando **SQLite**. Sin embargo, siguiendo los lineamientos de despliegue en producción:

1. **Persistencia en MariaDB**: Se migrará el motor de datos a un contenedor de **MariaDB**, actualizando únicamente las variables del archivo `.env` (`DATABASE_URL="mysql+pymysql://..."`) sin alterar ninguna línea de la lógica de negocio ni del dominio gracias a la Arquitectura Hexagonal.
2. **Despliegue AWS**: La infraestructura final será provisionada con **Terraform** sobre instancias **AWS EC2** y expuesta públicamente mediante **Amazon API Gateway**.
3. **Siguiente integración**: conectar con `ms-pagos` para llamar a `confirmar-salida` en Inventario cuando el pago sea aprobado.