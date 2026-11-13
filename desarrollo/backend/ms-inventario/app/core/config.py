# Carga de variables que provienen del .env, tipada con pydantic-settings

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Microservicio de Inventario"
    ENVIRONMENT: str = "local"
    DATABASE_URL: str

    # Credenciales para validar JWT de Azure AD
    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_ID: str = ""

    # Clave compartida SOLO entre microservicios (ms-pedidos -> ms-inventario).
    # Protege reservar / liberar / confirmar-salida: si queda vacia, esos endpoints
    # rechazan todo (falla cerrado) en vez de quedar abiertos por un olvido.
    INTERNAL_API_KEY: str = ""

    # --- RabbitMQ: ms-inventario es CONSUMIDOR de los eventos de pedido ---
    # Apagado por defecto (tests / `uvicorn` local sin broker). docker compose lo enciende.
    RABBITMQ_ENABLED: bool = False
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_VHOST: str = "/"
    RABBITMQ_USER: str = ""
    RABBITMQ_PASSWORD: str = ""
    RABBITMQ_HEARTBEAT: int = 60
    RABBITMQ_CONNECTION_TIMEOUT: float = 5.0

    # Topologia (nombres). Este servicio es DUENO de su cola, su DLQ y sus bindings.
    # El exchange de pedidos lo posee ms-pedidos: aqui se redeclara igual (idempotente) para poder bindear.
    RABBITMQ_EXCHANGE_PEDIDOS: str = "pedidos.events"        # TOPIC
    RABBITMQ_EXCHANGE_DLX: str = "pidealtoke.dlx"            # DIRECT: recibe los mensajes rechazados
    RABBITMQ_QUEUE_PEDIDOS: str = "inventario.pedidos"
    RABBITMQ_QUEUE_PEDIDOS_DLQ: str = "inventario.pedidos.dlq"
    RABBITMQ_BINDING_PEDIDOS: str = "pedido.*"               # patron de routing keys que escucha la cola

    # Consumo: prefetch por consumidor, hilos consumidores y politica de reintentos.
    RABBITMQ_CONSUMER_PREFETCH: int = Field(10, ge=1)        # mensajes sin ACK permitidos por consumidor
    RABBITMQ_CONSUMER_CONCURRENCY: int = Field(2, ge=1, le=32)  # hilos (cada uno con su conexion)
    RABBITMQ_MAX_RETRIES: int = Field(3, ge=0)               # reintentos DESPUES del primer intento
    RABBITMQ_RETRY_BASE_SECONDS: float = Field(1.0, gt=0)    # espera = base * 2^(intento-1) ...
    RABBITMQ_RETRY_MAX_SECONDS: float = Field(30.0, gt=0)    # ... con este tope
    RABBITMQ_RECONNECT_MAX_SECONDS: float = Field(30.0, gt=0)  # tope del backoff al reconectar

    # --- Alertas de stock por RabbitMQ: ms-inventario PUBLICA en un exchange DIRECT ---
    # direct porque la alerta tiene un destino exacto (routing key `stock.bajo`), sin patrones.
    # La cola `alertas.stock` (y su DLQ) las declara el consumidor: ms-notificaciones.
    RABBITMQ_EXCHANGE_ALERTAS: str = "pidealtoke.alertas"    # DIRECT
    RABBITMQ_RK_STOCK_BAJO: str = "stock.bajo"
    RABBITMQ_PUBLISH_COOLDOWN_SECONDS: float = Field(10.0, ge=0)  # sin reintentar tras un fallo reciente

    # --- Kafka: ms-inventario es PRODUCTOR del topico `inventario.movimientos` ---
    # Cada movimiento de stock (reservado, liberado, confirmado, repuesto, stock_bajo) queda en el
    # log de Kafka, con key = sku: todos los movimientos de un producto llegan en orden.
    # Apagado por defecto: sin cluster (tests, `uvicorn` local) el servicio funciona igual.
    KAFKA_ENABLED: bool = False
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"          # lista separada por comas
    KAFKA_TOPIC_MOVIMIENTOS: str = "inventario.movimientos"
    KAFKA_CLIENT_ID: str = "ms-inventario"
    KAFKA_ACKS: str = "all"
    KAFKA_ENABLE_IDEMPOTENCE: bool = True
    KAFKA_COMPRESSION: str = "lz4"
    KAFKA_LINGER_MS: int = Field(5, ge=0)
    KAFKA_DELIVERY_TIMEOUT_MS: int = Field(15000, ge=1000)
    KAFKA_FLUSH_TIMEOUT_SECONDS: float = Field(5.0, gt=0)

settings = Settings()

# Sin estos dos valores no se puede validar NINGUN token (la URL de claves quedaria mal formada y
# cada peticion respondería un 401 confuso). Es mejor fallar al arrancar, con un mensaje claro.
if not settings.AZURE_TENANT_ID or not settings.AZURE_CLIENT_ID:
    raise RuntimeError(
        "Configuracion incompleta: define AZURE_TENANT_ID y AZURE_CLIENT_ID "
        "(variables de entorno o archivo .env)."
    )

# Con RabbitMQ encendido hacen falta credenciales: mejor fallar al arrancar con un mensaje claro.
if settings.RABBITMQ_ENABLED and not (settings.RABBITMQ_USER and settings.RABBITMQ_PASSWORD):
    raise RuntimeError(
        "Configuracion incompleta: RABBITMQ_ENABLED=true requiere RABBITMQ_USER y RABBITMQ_PASSWORD."
    )

if settings.KAFKA_ENABLED and not settings.KAFKA_BOOTSTRAP_SERVERS.strip():
    raise RuntimeError("Configuracion incompleta: KAFKA_ENABLED=true requiere KAFKA_BOOTSTRAP_SERVERS.")
