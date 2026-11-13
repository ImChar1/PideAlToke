# Mapa real de colas RabbitMQ y correcciones del tablero (Trello)

Exchange de rechazados (DLX): `pidealtoke.dlx` (DIRECT). Cada cola de trabajo tiene su DLQ.

| Cola | Exchange / binding | Publica | **Consume** | DLQ |
|---|---|---|---|---|
| `inventario.pedidos` | `pedidos.events` (TOPIC) / `pedido.*` | `ms-pedidos` | `ms-inventario` | `inventario.pedidos.dlq` |
| `notificaciones.pedidos` | `pedidos.events` / `pedido.confirmado`, `pedido.cancelado` | `ms-pedidos` | `ms-notificaciones` | `notificaciones.pedidos.dlq` |
| `alertas.stock` | `pidealtoke.alertas` (DIRECT) / `stock.bajo` | `ms-inventario` | `ms-notificaciones` | `alertas.stock.dlq` |
| `pedidos.seguimiento` (nueva) | `pedidos.events` / `pedido.*` | `ms-pedidos` | `ms-pedidos` | `pedidos.seguimiento.dlq` |

## 1. Tarjeta `notificaciones.q` (la consume: ms-usuarios)

**No la marques como está escrita.** En el código la cola se llama **`notificaciones.pedidos`** y quien la consume y procesa es **`ms-notificaciones`** (también consume `alertas.stock`). `ms-usuarios` no usa RabbitMQ.

Qué hacer en la tarjeta: cambia el responsable a `ms-notificaciones` y el nombre a `notificaciones.pedidos`; después márcala como hecha.

## 2. Tarjeta `pedidos.q` (la consume: ms-pedidos)

Antes faltaba el consumidor de `ms-pedidos`. **Ya está implementado**; la cola se llama `pedidos.seguimiento` (sigue el mismo estilo de nombres que `inventario.pedidos` y `notificaciones.pedidos`).

Archivos nuevos en `backend/ms-pedidos`:

- `app/infrastructure/messaging/rabbitmq_consumer.py`: consumidor con ACK manual, reintentos con backoff exponencial y envío a la DLQ.
- `app/infrastructure/messaging/rabbitmq_consumer_config.py`: topología (cola, DLQ, bindings) declarada desde `settings`.
- `app/adapters/messaging/pedido_eventos_handler.py`: valida el evento (`EventoPedidoSchema`), descarta duplicados por `event_id` y registra el seguimiento. Los mensajes malformados van directo a la DLQ.
- `app/main.py`: levanta el consumidor al arrancar (solo si `RABBITMQ_ENABLED=true`) y lo detiene al apagar.
- `tests/test_rabbitmq_consumer.py`, `test_rabbitmq_topologia.py`, `test_pedido_eventos_handler.py` (21 pruebas nuevas; `ms-pedidos` pasa de 102 a 123).

Alcance actual: hoy el handler **solo registra** el evento (igual que el de `ms-inventario`). No cambia pedidos ni stock porque eso ya ocurre de forma síncrona y repetirlo duplicaría efectos. Si el equipo quiere una acción asíncrona concreta (avisar al cliente, recalcular un indicador), la lógica va en ese handler.

Cómo probarlo:

1. Levanta todo y abre la consola de RabbitMQ (`:15672`) con el usuario y la clave de tu `.env`.
2. En *Queues* debe aparecer `pedidos.seguimiento` con 1 consumidor.
3. Crea un pedido desde el frontend. En los logs de `ms-pedidos` aparece `Seguimiento de pedido: tipo=creado ...`.
4. Para ver la DLQ: en *Exchanges > pedidos.events > Publish message* usa routing key `pedido.creado` y un cuerpo que no sea JSON. El mensaje termina en `pedidos.seguimiento.dlq`.

Si prefieres que se llame exactamente `pedidos.q`: define `RABBITMQ_QUEUE_SEGUIMIENTO=pedidos.q` y `RABBITMQ_QUEUE_SEGUIMIENTO_DLQ=pedidos.q.dlq` en el servicio. Si la cola ya existía con otros nombres, bórrala antes con `DELETE /api/rabbitmq/queues/{name}` de `ms-mensajeria`.

## 3. Eventos de pago (`pago.aprobado`, `pago.rechazado`)

Busqué `pago.aprobado`, `pago.rechazado`, `ms-pagos` y `pagos` en el código, los compose, Terraform y la documentación: **no existe nada de pagos**. Como la arquitectura solo maneja pedidos e inventario, **quita esas tarjetas de tus listas de Trello**. Si más adelante se agrega un microservicio de pagos, ahí se vuelven a crear.
