# ms-notificaciones — Notificaciones (consumidor RabbitMQ)

Consume **dos colas** de RabbitMQ, cada una con su DLQ, y genera notificaciones (hoy: log + `GET /api/v1/notificaciones`, rol `ADMIN`).

| Cola | Exchange / routing key | DLQ | Handler |
|---|---|---|---|
| `notificaciones.pedidos` | `pedidos.events` (TOPIC) · `pedido.confirmado`, `pedido.cancelado` | `notificaciones.pedidos.dlq` | `manejar_notificacion_pedido` |
| `alertas.stock` | `pidealtoke.alertas` (DIRECT) · `stock.bajo` | `alertas.stock.dlq` | `manejar_alerta_stock` |

- **Topología** en `app/infrastructure/messaging/rabbitmq_config.py` (datos, no código imperativo); **todos los nombres** en `app/core/config.py` / variables `RABBITMQ_*`. Los mensajes rechazados salen por `pidealtoke.dlx` (DIRECT) hacia la DLQ de su cola.
- **Consumo:** `@RabbitListener` equivalente en Python (`ConsumerManager` + `basic_consume`), **ACK manual**, `prefetch` y concurrencia configurables, reintentos con backoff y `basic_nack(requeue=False)` → DLQ. Payload inválido → DLQ directo (`NonRetryableError`).
- **Idempotente** por `event_id` (RabbitMQ entrega al menos una vez).
- Un manager (y sus hilos) por cola; handlers separados por dominio funcional; lógica en `NotificacionService`, sin pika.

Sin `RABBITMQ_ENABLED=true` no toca el broker.

Tests: `pip install -r requirements-dev.txt && python -m pytest -q`.
