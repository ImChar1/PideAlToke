# ms-analitica — Analítica en tiempo real (consumidor Kafka)

Consume los dos tópicos de Kafka y mantiene en memoria estadísticas de ventas y stock. Endpoints bajo `/api/v1/analitica` (JWT con rol `ADMIN`; también por el gateway local).

| Ruta | Respuesta |
|---|---|
| `GET /ventas/resumen` | Pedidos pendientes/confirmados/cancelados, ingresos confirmados, ticket promedio |
| `GET /ventas/por-hora` | Ventas confirmadas por hora (UTC) |
| `GET /productos/top?limite=5` | Más vendidos (unidades e ingresos) |
| `GET /stock/estado?bajo_umbral=false` | Último stock conocido por SKU |
| `GET /stock/alertas` | Últimas alertas de stock bajo |
| `GET /metricas` | Mensajes aplicados / inválidos / fallidos y último offset por partición |

## Consumo
- **Dos consumer groups:** `analitica-ventas` ← `pedidos.eventos`; `alertas-stock` ← `inventario.movimientos`. `KAFKA_CONSUMER_CONCURRENCY` (3) consumidores por grupo = una partición cada uno; rebalanceo `cooperative-sticky`.
- **Commit manual** después de procesar (al menos una vez). Reintentos con backoff exponencial (`KAFKA_MAX_RETRIES`); un payload inválido o que agota los reintentos se registra con tópico/partición/offset, se cuenta en `/metricas` y se salta: **nunca detiene el consumo**.
- **Idempotente por offset:** cada evento se aplica una sola vez por `(tópico, partición, offset)`.
- **Reconstrucción:** al arrancar (`KAFKA_REBUILD_ON_START=true`) cada consumidor relee sus particiones desde el principio del log; así el estado en memoria sobrevive a un reinicio. Como el estado vive en el proceso, se despliega **una sola réplica**.
- Capas: `adapters/messaging` (valida bytes → DTO) → `domain/services/AnaliticaService` (reglas, sin Kafka) ; `infrastructure/kafka` (consumidor).

Sin `KAFKA_ENABLED=true` no toca el cluster y el API responde en vacío.

Tests: `pip install -r requirements-dev.txt && python -m pytest -q` (Consumer falso, sin cluster).
