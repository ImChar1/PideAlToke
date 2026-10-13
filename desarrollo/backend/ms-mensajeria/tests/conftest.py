# Configuracion comun de tests: se ejecuta ANTES de importar app.main, asi los tests
# no dependen de un .env local ni tocan un RabbitMQ real.
import os

os.environ.setdefault("AZURE_TENANT_ID", "test-tenant")
os.environ.setdefault("AZURE_CLIENT_ID", "test-client")
# Se fuerza (no setdefault): un host invalido garantiza que ningun test llegue a un broker real
# aunque haya variables RABBITMQ_* exportadas en la terminal.
os.environ["RABBITMQ_HOST"] = "rabbitmq.invalid"
os.environ["RABBITMQ_USER"] = "usuario-de-test"
os.environ["RABBITMQ_PASSWORD"] = "clave-de-test"
