#!/usr/bin/env bash
# Levanta TODO el sistema en el orden correcto: red -> RabbitMQ (cluster) -> Kafka -> Kafka-UI -> aplicacion.
# Uso:   ./levantar-todo.sh            (construye y levanta)
#        ./levantar-todo.sh down       (apaga todo; agrega -v para borrar tambien los volumenes)
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] || { echo "Falta .env: ejecuta  cp .env.example .env"; exit 1; }

COMPOSES=(docker-compose.rabbitmq.yml docker-compose.kafka.yml docker-compose.kafka-ui.yml docker-compose.yml)

if [ "${1:-}" = "down" ]; then
  shift
  for ((i=${#COMPOSES[@]}-1; i>=0; i--)); do docker compose -f "${COMPOSES[i]}" down "$@"; done
  exit 0
fi

# La red compartida se crea una sola vez (si ya existe, no pasa nada).
docker network inspect pidealtoke-net >/dev/null 2>&1 || docker network create pidealtoke-net

docker compose -f docker-compose.rabbitmq.yml up -d
docker compose -f docker-compose.kafka.yml up -d
docker compose -f docker-compose.kafka-ui.yml up -d
docker compose -f docker-compose.yml up --build -d

cat <<MSG

Listo. Consolas:
  Frontend            http://localhost:4200
  RabbitMQ nodo 1     http://localhost:15672   (nodo 2: :15673)   usuario/clave: RABBITMQ_USER / RABBITMQ_PASSWORD
  Kafka-UI            http://localhost:8090                       usuario/clave: KAFKA_UI_USER / KAFKA_UI_PASSWORD
  Admin RabbitMQ      http://localhost:8005/docs
  Admin Kafka         http://localhost:8006/docs
Estado:  docker ps --format 'table {{.Names}}\t{{.Status}}'
MSG
