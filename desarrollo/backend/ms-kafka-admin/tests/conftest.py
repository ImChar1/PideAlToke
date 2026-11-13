# Configuracion comun de tests: se ejecuta ANTES de importar app.main, asi los tests
# no dependen de un .env local ni tocan un cluster de Kafka real.
import os

os.environ.setdefault("AZURE_TENANT_ID", "test-tenant")
os.environ.setdefault("AZURE_CLIENT_ID", "test-client")
# Se fuerza (no setdefault): un host invalido garantiza que ningun test llegue a un broker real.
os.environ["KAFKA_BOOTSTRAP_SERVERS"] = "kafka.invalid:9092"
