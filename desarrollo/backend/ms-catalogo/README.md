# Microservicio de Catalogo de Productos (`ms-catalogo`) - PideAlToke

Parte del ecosistema Cloud Native **PideAlToke**. Encargado de la consulta y mantención de productos, construido en **FastAPI** (Python) con **Arquitectura Hexagonal (Ports and Adapters)**, igual que `ms-pedidos`.

---

## 🏛️ Estructura de Capas

* **Core (`app/core`)**: configuración vía `pydantic-settings` y validación de JWT contra Azure AD (JWKS, issuer, audience, RBAC por rol).
* **Domain (`app/domain`)**:
  * `models/producto.py`: entidad ORM (SQLAlchemy).
  * `ports/producto_repository_port.py`: contrato abstracto de persistencia.
  * `services/producto_service.py`: reglas de negocio (SKU único, producto no encontrado).
* **Schemas (`app/schemas`)**: DTOs Pydantic (`CrearProductoSchema`, `ActualizarProductoSchema`, `ProductoResponseSchema`).
* **Infrastructure (`app/infrastructure`)**: `session.py` (conexión SQLAlchemy) y `producto_repository.py` (implementación concreta del Port).
* **Adapters (`app/adapters`)**: `productos_router.py` con los endpoints HTTP.

---

## ✅ Implementado en esta fase

1. **Modelo `ProductoModel`**: id, sku (único), nombre, descripción, precio (`Numeric`), categoría, imagen_url, activo (soft-delete), fecha_creación, fecha_actualización. El **stock no vive aquí**: según el ADD (patrón *Database per Servicio*), esa responsabilidad es del microservicio de **Inventario**; este catálogo solo expone el `sku` como referencia cruzada.
2. **DTOs**: validación de precio > 0, actualización parcial vía `ActualizarProductoSchema`.
3. **Port + Repository**: CRUD completo (crear, obtener por id/sku, listar con filtro por categoría, actualizar, desactivar).
4. **Service**: valida SKU duplicado al crear y lanza excepciones de dominio (`ProductoNoEncontradoError`, `SkuDuplicadoError`) que el router traduce a códigos HTTP (404/409).
5. **Endpoints**:
   - `GET /productos/` (lista, filtro opcional `?categoria=`)
   - `GET /productos/{id}`
   - `POST /productos/` (requiere rol `ADMIN`)
   - `PUT /productos/{id}` (requiere rol `ADMIN`)
   - `DELETE /productos/{id}` → desactiva (soft-delete), requiere rol `ADMIN`
6. **Seguridad JWT (`core/security.py`)**: descarga y cachea JWKS de Azure AD, valida firma RS256, `issuer` y `audience`, y expone `requerir_rol()` para RBAC en endpoints de escritura. Lectura (`GET`) requiere solo un token válido; escritura requiere rol `ADMIN`.

---

## ▶️ Cómo correrlo localmente

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Luego entra a `http://localhost:8000/docs` para probar los endpoints (Swagger).

> Nota: sin un token real de Azure AD los endpoints protegidos devolverán 401. Para pruebas locales sin IDaaS real, se puede comentar temporalmente la dependencia `Depends(validar_jwt)` — **nunca subir ese cambio a la rama principal**.

---

## 🐳 Próxima etapa

Migración a **MariaDB** vía Docker y despliegue en **AWS EC2** con **Terraform**, expuesto por **Amazon API Gateway** — igual que el resto de los microservicios del proyecto.
