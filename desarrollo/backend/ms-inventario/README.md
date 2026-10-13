# Microservicio de Inventario (`ms-inventario`) - PideAlToke

Parte del ecosistema Cloud Native **PideAlToke**. Según el ADD: *"Inventario: Control de stock disponible en tiempo real"*. Construido en **FastAPI** (Python) con **Arquitectura Hexagonal (Ports and Adapters)**, igual que `ms-pedidos` y `ms-catalogo`.

---

## 🎯 Responsabilidad de este microservicio

Controla las **cantidades** de cada producto: `cantidad_disponible`, `cantidad_reservada` y `umbral_minimo`. **No duplica** información del Catálogo (nombre, precio, descripción) — eso vive en `ms-catalogo`. La comunicación entre ambos se hace referenciando el **`sku`** del producto (patrón *Database per Servicio* del ADD, sin FK cruzada entre bases de datos).

**Concepto clave de negocio — stock vendible:**
```
stock_vendible = cantidad_disponible - cantidad_reservada
```
Un pedido en curso **reserva** stock (no lo descuenta aún). Si el pedido se cancela, se **libera** la reserva. Si el pedido se confirma/paga, se **confirma la salida** (ahí sí se descuenta `cantidad_disponible` en firme).

---

## 🏛️ Estructura de Capas

Igual que `ms-catalogo`: `core` (config + seguridad JWT, compartida/reutilizada), `domain` (models/ports/services), `schemas` (DTOs Pydantic), `infrastructure` (db/repositories), `adapters` (routers HTTP).

---

## ✅ Endpoints implementados

Prefijo `/api/v1`. Las respuestas incluyen `stock_vendible` (`disponible - reservada`).

| Método | Ruta | Requiere | Descripción |
|---|---|---|---|
| GET | `/inventario` | token válido | lista inventario (`?bajo_umbral=true` filtra alertas) |
| GET | `/inventario/{sku}` | token válido | detalle de un producto |
| POST | `/inventario` | `ADMIN` | crea el registro de inventario de un producto nuevo |
| PUT | `/inventario/{sku}/umbral` | `ADMIN` | actualiza el umbral mínimo de alerta |
| POST | `/inventario/{sku}/reponer` | `ADMIN` | ingreso de mercadería (aumenta disponible) |
| POST | `/inventario/{sku}/reservar` | token + **clave interna** | reserva stock (lo llama `ms-pedidos` al crear un pedido) |
| POST | `/inventario/{sku}/liberar` | token + **clave interna** | libera una reserva (pedido cancelado) |
| POST | `/inventario/{sku}/confirmar-salida` | token + **clave interna** | descuenta stock en firme (pedido confirmado) |

### Uso interno de reservar / liberar / confirmar-salida

Solo `ms-pedidos` puede llamarlos: deben llevar el header `X-Internal-Key` con el valor de `INTERNAL_API_KEY`. Un usuario con JWT válido (incluso ADMIN) pero sin esa clave recibe **403**. Si `INTERNAL_API_KEY` queda vacía, esos endpoints rechazan todo (falla cerrado). El gateway local además los bloquea hacia afuera.

### Sin sobreventa

`reservar`, `confirmar-salida`, `reponer` y `liberar` son **una sola sentencia `UPDATE` condicional** (la guarda de stock y el ajuste son atómicos en la base). Hay tests con hilos concurrentes contra el repositorio real que lo comprueban.

---

## 🧪 Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Reglas de negocio con repositorio en memoria, endpoints con JWT simulado (`dependency_overrides`), la clave interna, y **concurrencia real** (`test_inventario_concurrencia.py`). Usan una SQLite temporal; con `TEST_DATABASE_URL` puedes correrlos contra MariaDB.

---

## ▶️ Cómo correrlo localmente

```bash
cp .env.example .env     # completa AZURE_TENANT_ID, AZURE_CLIENT_ID e INTERNAL_API_KEY
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Luego `http://localhost:8000/docs` para el Swagger.

---

## 🐳 Docker

```bash
docker build -t ms-inventario .
docker run --env-file .env -p 8003:8000 ms-inventario
```
El contenedor escucha en el **8000**; docker compose y Terraform lo publican en el 8003.

---

## 🔗 Quién lo llama

`ms-pedidos` reserva al crear un pedido, libera al cancelarlo y confirma la salida cuando un ADMIN lo confirma (ver el README de `ms-pedidos`).
