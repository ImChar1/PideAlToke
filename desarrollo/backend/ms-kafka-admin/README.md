# ms-kafka-admin — Administración de Kafka

API REST operativa para administrar el cluster: tópicos, configuraciones y consumer groups. Todos los endpoints exigen JWT válido con el rol `ADMIN` y **no se exponen por el gateway**. Rutas bajo `/api/kafka` (sin `/v1`, igual que `ms-mensajeria`). Swagger: `http://localhost:8006/docs`.

| Método | Ruta | Qué hace |
|---|---|---|
| `POST` | `/api/kafka/topics` | Crea un tópico: `{"name","partitions"=3,"replication_factor"=3,"config":{...}}` |
| `GET` | `/api/kafka/topics` | Lista (oculta los internos `__*`; `?incluir_internos=true`) |
| `GET` | `/api/kafka/topics/{name}` | Particiones (líder, réplicas, ISR) y configuración (`config_personalizada` = lo que se salió del default) |
| `PATCH` | `/api/kafka/topics/{name}/config` | Modifica **solo** las claves enviadas (`incremental_alter_configs`) |
| `PUT` | `/api/kafka/topics/{name}/partitions` | Aumenta particiones (Kafka no permite reducir) |
| `DELETE` | `/api/kafka/topics/{name}` | Elimina un tópico (los internos están protegidos) |
| `GET` | `/api/kafka/topics/config-permitida` | Claves de configuración aceptadas |
| `GET` | `/api/kafka/consumer-groups` | Lista de grupos y su estado |
| `GET` | `/api/kafka/consumer-groups/{id}` | Miembros y particiones asignadas |
| `GET` | `/api/kafka/consumer-groups/{id}/lag` | Offset confirmado, offset final y **lag** por partición |

**Validaciones** (antes de llegar al broker): nombre sin vacío/espacios/`/`; `replication_factor` ≤ brokers vivos; `min.insync.replicas` ≤ `replication_factor`; solo claves de configuración de una lista cerrada (`retention.ms`, `retention.bytes`, `cleanup.policy`, `min.insync.replicas`, `segment.ms`, `segment.bytes`, `max.message.bytes`, `compression.type`, `delete.retention.ms`) con valores válidos. Errores: 404 (no existe), 409 (ya existe), 422 (argumentos), 503 (cluster no responde).

Arquitectura hexagonal: `KafkaAdminService` (reglas) → `KafkaAdminPort` → `ConfluentKafkaAdmin` (adaptador sobre `AdminClient`).

Ejemplo (crear el tópico de pedidos con retención de 30 días):
```bash
curl -X POST http://localhost:8006/api/kafka/topics -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"pedidos.eventos","partitions":3,"replication_factor":3,"config":{"retention.ms":"2592000000","min.insync.replicas":"2"}}'
```

Tests: `pip install -r requirements-dev.txt && python -m pytest -q` (sin cluster: fakes y un `AdminClient` falso).
