# Evaluación Parcial 3 — Diseño de la integración con Kafka (PideAlToke)

Documento de apoyo para la presentación (DSY1107). Responde los pasos 1 y 2 del plan: casos de uso y modelo de mensajes.

## 1. Cómo se complementan RabbitMQ y Kafka

| | RabbitMQ (ya existente) | Kafka (nuevo) |
|---|---|---|
| Modelo | Cola: el mensaje se **consume y desaparece** | Log: el mensaje **se conserva** (retención) y se puede releer |
| Consumidores | Compiten por los mensajes de una cola | Cada *consumer group* recibe **todos** los mensajes |
| Uso en PideAlToke | Trabajo y avisos que alguien debe procesar una vez: reservas de inventario, notificaciones, alertas | Historial de eventos para analítica en tiempo real |
| Fallos | ACK manual, reintentos, **DLQ** | Commit manual, reintentos, descarte con log y métrica |

Los productores publican en ambos (`CompositeEventPublisher`): si Kafka falla, RabbitMQ sigue recibiendo el evento y viceversa. Los consumidores de RabbitMQ no se modificaron.

## 2. Casos de uso (uno por tópico)

### Caso de uso 1 — Analítica de ventas en tiempo real → tópico `pedidos.eventos`
- **Necesidad:** el administrador quiere ver, sin consultar la base de datos de pedidos, cuántos pedidos hay pendientes/confirmados/cancelados, los ingresos, el ticket promedio, las ventas por hora y los productos más vendidos, actualizados al instante.
- **Flujo:** `ms-pedidos` publica un evento por cada cambio de estado → `ms-analitica` (consumer group `analitica-ventas`) actualiza los agregados → el dashboard los lee en `GET /api/v1/analitica/ventas/*`.
- **Por qué streaming:** la analítica no debe cargar la base transaccional, y al ser un log retenido 30 días `ms-analitica` puede **reconstruir** su estado releyendo el tópico después de un reinicio.
- **Key = `pedido_id`:** `creado → confirmado/cancelado` de un mismo pedido caen en la misma partición y se procesan en orden (necesario para no contar un pedido confirmado como pendiente).

### Caso de uso 2 — Monitoreo de stock y alertas → tópico `inventario.movimientos`
- **Necesidad:** ver el stock de cada SKU según sus movimientos y detectar cuándo cae bajo el umbral mínimo.
- **Flujo:** `ms-inventario` publica un evento por cada movimiento (`reservado`, `liberado`, `confirmado`, `repuesto`) y un `stock_bajo` cuando una salida en firme cruza `umbral_minimo` → `ms-analitica` (consumer group `alertas-stock`) mantiene el último estado por SKU y las últimas alertas (`GET /api/v1/analitica/stock/*`). El `stock_bajo` además viaja por RabbitMQ (`alertas.stock`) para generar la notificación accionable en `ms-notificaciones`.
- **Key = `sku`:** todos los movimientos de un producto llegan en orden y el "último estado" nunca retrocede.
- **Retención 7 días:** dato operativo de alto volumen; basta el corto plazo.

## 3. Modelo de mensajes (JSON)

Contratos entre microservicios: el productor define el DTO; los consumidores tienen su copia de **lectura** con `extra="ignore"` (campos nuevos del productor no los rompen). Un mensaje que no cumple el contrato es *inválido*: se registra, se cuenta y se salta (nunca detiene el consumo).

### `pedidos.eventos` (key = `pedido_id`, value = JSON, headers: `event_id`, `tipo`, `content-type`)

```json
{
  "event_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "tipo": "confirmado",
  "ocurrido_en": "2026-11-04T15:30:00Z",
  "pedido_id": 101,
  "cliente_id": "b1f0c9a2-0000-0000-0000-000000000000",
  "estado": "CONFIRMADO",
  "monto_total": 15990.0,
  "items": [{"sku": "SKU-001", "cantidad": 2, "precio_unitario": 7995.0}]
}
```

| Campo | Tipo | Para qué sirve |
|---|---|---|
| `event_id` | uuid | Identifica el evento (deduplicación, trazabilidad) |
| `tipo` | `creado` \| `confirmado` \| `cancelado` | Decide cómo cambia el estado del pedido en la analítica |
| `ocurrido_en` | ISO-8601 UTC | Agrupar ventas por hora |
| `pedido_id` | int | Identidad del pedido (también es la *key*) |
| `cliente_id` | string | Quién compró (viene del JWT, nunca del body) |
| `estado` | string | Estado del pedido tras el cambio |
| `monto_total` | número ≥ 0 | Ingresos y ticket promedio |
| `items[]` | `sku`, `cantidad` > 0, `precio_unitario` ≥ 0 | Productos más vendidos e ingresos por producto |

### `inventario.movimientos` (key = `sku`, value = JSON, headers: `event_id`, `tipo`, `content-type`)

```json
{
  "event_id": "0b3f6f2e-52c1-4d6f-9f55-3f2b7e6e1a11",
  "tipo": "stock_bajo",
  "ocurrido_en": "2026-11-04T15:31:02Z",
  "sku": "SKU-001",
  "cantidad": 0,
  "stock_disponible": 4,
  "stock_reservado": 0,
  "stock_vendible": 4,
  "umbral_minimo": 5,
  "pedido_id": null
}
```

| Campo | Tipo | Para qué sirve |
|---|---|---|
| `tipo` | `reservado` \| `liberado` \| `confirmado` \| `repuesto` \| `stock_bajo` | Qué pasó con el stock |
| `sku` | string | Producto (también es la *key*) |
| `cantidad` | int ≥ 0 | Unidades del movimiento (0 en `stock_bajo`) |
| `stock_disponible` / `stock_reservado` / `stock_vendible` | int | Estado del SKU **después** del movimiento: el consumidor no necesita consultar a `ms-inventario` |
| `umbral_minimo` | int \| null | Permite marcar "bajo umbral" sin otro servicio |
| `pedido_id` | int \| null | Correlación con el pedido cuando el origen la conoce |

## 4. Particiones, réplicas y consumer groups (justificación)

- **3 particiones:** es el máximo paralelismo de lectura de un consumer group (hasta 3 consumidores en paralelo); la *key* reparte la carga y conserva el orden por entidad.
- **3 réplicas con 3 brokers:** cada partición tiene copia en todos los brokers. Con `min.insync.replicas=2` + `acks=all` el sistema sigue escribiendo si cae **1** broker sin perder mensajes confirmados; si caen 2, las escrituras se rechazan antes que arriesgar datos (consistencia sobre disponibilidad).
- **3 Zookeeper:** el ensemble necesita mayoría; con 3 tolera la caída de 1.
- **Dos consumer groups sobre tópicos distintos** (`analitica-ventas`, `alertas-stock`): cada responsabilidad avanza a su propio ritmo y con su propio *lag*. Dentro de cada grupo, 3 consumidores se reparten las 3 particiones; si uno cae, Kafka reasigna su partición (rebalanceo cooperativo).
- **Commit manual después de procesar:** semántica "al menos una vez"; el estado es idempotente por `(tópico, partición, offset)`, así releer o reasignar nunca cuenta dos veces un evento.

## 5. Qué mirar en Kafka-UI para la presentación

- *Brokers:* 3 en línea. *Topics:* `pedidos.eventos` e `inventario.movimientos` con 3 particiones y 3 réplicas (todas *in sync*).
- *Topics → Messages:* ver el JSON y la key de cada evento tras crear/confirmar un pedido.
- *Consumers:* `analitica-ventas` y `alertas-stock`, miembros, particiones asignadas y **lag** por partición (0 = al día). Detener `ms-analitica` y crear pedidos hace subir el lag; al reiniciar baja a 0.
- Mismo dato por API: `GET /api/kafka/consumer-groups/{grupo}/lag` (ms-kafka-admin).
