# Microservicio de Pedidos (`ms-pedidos`) - PideAlToke

Este microservicio forma parte del ecosistema Cloud Native **PideAlToke**[cite: 1]. Está encargado de procesar la creación, consulta y ciclo de vida de los pedidos comerciales de la plataforma, construido sobre **FastAPI** (Python) y siguiendo el patrón de **Arquitectura Hexagonal (Ports and Adapters)**.

---

## 🏛️ Patrón de Diseño y Arquitectura

El microservicio utiliza **Arquitectura Hexagonal** para desacoplar completamente las reglas de negocio de las tecnologías externas (bases de datos, frameworks web, controladores).

### Estructura de Capas
* **Core (`app/core`)**: Configuración global de variables de entorno mediante `pydantic-settings` y gestión de seguridad JWT[cite: 1].
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
2. **Entidad Pedido (`domain/models/pedido.py`)**: Mapeo relacional con timestamp compatible mediante `func.now()`.
3. **DTOs de Transferencia (`schemas/pedido_schema.py`)**: Esquemas de validación para entrada (`CrearPedidoSchema`) y salida (`PedidoResponseSchema`).
4. **Puerto y Repositorio (`domain/ports/` & `infrastructure/repositories/`)**: Contrato e implementación concreta utilizando SQLAlchemy.
5. **Servicio de Dominio (`domain/services/pedido_service.py`)**: Lógica para calcular el costo total e iniciar el pedido en estado `PENDIENTE`.
6. **Enrutador HTTP (`adapters/api/v1/routers/pedidos_router.py`)**: Endpoint `POST /pedidos/` inyectando dependencias.

---

## 🐳 Próxima Etapa: Migración a MariaDB con Docker

Actualmente, el microservicio está preparado para pruebas locales inmediatas usando **SQLite**. Sin embargo, siguiendo los lineamientos de despliegue en producción:

1. **Contenerización**: El servicio se empaquetará dentro de una imagen Docker mediante un `Dockerfile`.
2. **Persistencia en MariaDB**: Se migrará el motor de datos a un contenedor de **MariaDB**, actualizando únicamente las variables del archivo `.env` (`DATABASE_URL="mysql+pymysql://..."`) sin alterar ninguna línea de la lógica de negocio ni del dominio gracias a la Arquitectura Hexagonal.
3. **Despliegue AWS**: La infraestructura final será provisionada con **Terraform** sobre instancias **AWS EC2** y expuesta públicamente mediante **Amazon API Gateway**[cite: 1].