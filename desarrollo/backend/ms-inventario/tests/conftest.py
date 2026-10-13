# Configuracion comun de tests: se ejecuta ANTES de importar app.main, asi los tests
# no dependen de un .env local ni tocan una base de datos real.
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="pidealtoke-tests-")
# Se fuerza (no setdefault): los tests nunca deben apuntar a una DB real por accidente aunque
# haya un DATABASE_URL exportado en la terminal. Para correrlos a proposito contra una MariaDB
# real (ej. verificar la atomicidad en InnoDB) define TEST_DATABASE_URL de forma explicita.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_tmp}/test.db"
os.environ.setdefault("AZURE_TENANT_ID", "test-tenant")
os.environ.setdefault("AZURE_CLIENT_ID", "test-client")
os.environ["INTERNAL_API_KEY"] = "clave-interna-de-test"
# Los tests nunca deben conectarse a un RabbitMQ real aunque haya un .env con RABBITMQ_ENABLED=true.
os.environ["RABBITMQ_ENABLED"] = "false"
