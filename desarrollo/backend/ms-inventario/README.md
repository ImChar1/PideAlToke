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

| Método | Ruta | Rol requerido | Descripción |
|---|---|---|---|
| GET | `/inventario/` | token válido | lista inventario (`?bajo_umbral=true` filtra alertas) |
| GET | `/inventario/{sku}` | token válido | detalle de un producto |
| POST | `/inventario/` | `ADMIN` | crea el registro de inventario de un producto nuevo |
| PUT | `/inventario/{sku}/umbral` | `ADMIN` | actualiza el umbral mínimo de alerta |
| POST | `/inventario/{sku}/reponer` | `ADMIN` | ingreso de mercadería (aumenta disponible) |
| POST | `/inventario/{sku}/reservar` | token válido | reserva stock (llamado por `ms-pedidos` al crear un pedido) |
| POST | `/inventario/{sku}/liberar` | token válido | libera una reserva (pedido cancelado) |
| POST | `/inventario/{sku}/confirmar-salida` | token válido | descuenta stock en firme (pedido pagado) |

> ⚠️ En producción, `reservar` / `liberar` / `confirmar-salida` deberían restringirse además a llamadas internas desde `ms-pedidos` (resource policy del API Gateway o un rol de servicio dedicado), no exponerse directo al frontend.

---

## 🧪 Tests

```bash
pip install -r requirements-dev.txt
pytest
```

21 tests: reglas de negocio (`test_inventario_service.py`) con repositorio en memoria, e integración de endpoints (`test_inventario_router.py`) con JWT simulado vía `dependency_overrides`.

---

## ▶️ Cómo correrlo localmente

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Luego `http://localhost:8000/docs` para el Swagger.

---

## 🐳 Docker

```bash
docker build -t ms-inventario .
docker run --env-file .env -p 8080:8080 ms-inventario
```
Puerto **8080**, igual que `ms-catalogo`, alineado al Security Group `sg-backend` de `infra/terraform/etapa_2`.

---

## 🐳 Próxima etapa

Cuando `ms-pedidos` cree un pedido, debe llamar a `POST /inventario/{sku}/reservar` antes de confirmar la compra, y a `confirmar-salida` cuando el pago sea aprobado por `ms-pagos`.
