# Configuracion comun de tests: se ejecuta ANTES de importar app.main, asi los tests
# no dependen de un .env local ni tocan un cluster de Kafka real.
import os

os.environ.setdefault("AZURE_TENANT_ID", "test-tenant")
os.environ.setdefault("AZURE_CLIENT_ID", "test-client")
# Los tests nunca deben conectarse a un Kafka real aunque haya un .env con KAFKA_ENABLED=true.
os.environ["KAFKA_ENABLED"] = "false"
