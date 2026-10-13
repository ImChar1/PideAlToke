# ms-mensajeria — Administrador de RabbitMQ

API REST (FastAPI) para administrar colas, exchanges y bindings de RabbitMQ sin entrar a la consola web. Misma arquitectura hexagonal que el resto de microservicios; la lógica vive en `RabbitAdminService` y el router solo valida, autoriza y delega.

## Seguridad
Todos los endpoints exigen un **JWT válido de Azure con el rol `ADMIN`** (son operaciones destructivas: borrar colas, purgar mensajes). Cada operación queda en el log con el `oid` de quien la hizo. No está enrutado por el gateway local ni tiene CORS: es de uso operativo.

## Endpoints (`/api/rabbitmq`)
| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/queues` | Declara una cola (`durable`, `auto_delete`, `queue_type`, `message_ttl_ms`, `max_length`, `dead_letter_exchange`, `dead_letter_routing_key`) → 201 |
| GET | `/queues/{name}` | Mensajes listos y consumidores |
| DELETE | `/queues/{name}?if_unused=&if_empty=` | Elimina la cola (409 si una guarda lo impide) |
| POST | `/queues/{name}/purge` | Descarta los mensajes listos |
| POST | `/exchanges` | Declara un exchange `direct` / `topic` / `fanout` / `headers` → 201 |
| POST | `/bindings` | Enlaza cola ↔ exchange con una routing key → 201 |

Errores: `404` recurso inexistente · `409` argumentos distintos a los existentes o guarda `if_*` · `422` validación o rechazo del broker · `503` broker inalcanzable.

Ejemplo (DLQ para una cola nueva):
```bash
curl -X POST http://localhost:8005/api/rabbitmq/queues -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"demo","message_ttl_ms":60000,"dead_letter_exchange":"pidealtoke.dlx","dead_letter_routing_key":"demo.dlq"}'
```

## Ejecutar
`.env` (ver `.env.example`) y `uvicorn app.main:app --port 8005`, o `docker compose up` desde `desarrollo/`. Tests: `pip install -r requirements-dev.txt && python -m pytest -q`.
