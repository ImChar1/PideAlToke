# Carga de variables que provienen del .env, tipada con pydantic-settings

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Microservicio de Analitica"
    ENVIRONMENT: str = "local"

    # Credenciales para validar JWT de Azure AD
    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_ID: str = ""

    # --- Kafka: este servicio CONSUME. Apagado por defecto (sin cluster el API responde en vacio). ---
    KAFKA_ENABLED: bool = False
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"          # lista separada por comas
    KAFKA_CLIENT_ID: str = "ms-analitica"

    # Topicos que consume (los crea el administrador: ms-kafka-admin / script de compose).
    KAFKA_TOPIC_PEDIDOS: str = "pedidos.eventos"
    KAFKA_TOPIC_MOVIMIENTOS: str = "inventario.movimientos"

    # Un consumer group por responsabilidad: cada grupo recibe TODOS los mensajes de su topico y, dentro
    # del grupo, las particiones se reparten entre los consumidores (balanceo de carga).
    KAFKA_GROUP_VENTAS: str = "analitica-ventas"             # lee pedidos.eventos
    KAFKA_GROUP_STOCK: str = "alertas-stock"                 # lee inventario.movimientos
    # Consumidores (hilos) por grupo. Con 3 particiones, 3 consumidores = una particion cada uno.
    KAFKA_CONSUMER_CONCURRENCY: int = Field(3, ge=1, le=12)

    # Errores: reintentos con backoff exponencial (DESPUES del primer intento) antes de descartar el mensaje.
    KAFKA_MAX_RETRIES: int = Field(3, ge=0)
    KAFKA_RETRY_BASE_SECONDS: float = Field(1.0, gt=0)
    KAFKA_RETRY_MAX_SECONDS: float = Field(30.0, gt=0)
    KAFKA_RECONNECT_MAX_SECONDS: float = Field(30.0, gt=0)

    # El estado de la analitica vive en memoria. Al arrancar se relee cada particion desde el
    # principio del log (reconstruccion): asi un reinicio no pierde las estadisticas. Es idempotente
    # (se ignoran offsets ya procesados), por eso es seguro tambien tras un rebalanceo.
    KAFKA_REBUILD_ON_START: bool = True
    KAFKA_SESSION_TIMEOUT_MS: int = Field(10000, ge=1000)
    KAFKA_MAX_POLL_INTERVAL_MS: int = Field(300000, ge=1000)


settings = Settings()

# Sin estos valores no se puede validar NINGUN token. Mejor fallar al arrancar con un mensaje claro.
if not settings.AZURE_TENANT_ID or not settings.AZURE_CLIENT_ID:
    raise RuntimeError(
        "Configuracion incompleta: define AZURE_TENANT_ID y AZURE_CLIENT_ID "
        "(variables de entorno o archivo .env)."
    )

if settings.KAFKA_ENABLED and not settings.KAFKA_BOOTSTRAP_SERVERS.strip():
    raise RuntimeError("Configuracion incompleta: KAFKA_ENABLED=true requiere KAFKA_BOOTSTRAP_SERVERS.")
