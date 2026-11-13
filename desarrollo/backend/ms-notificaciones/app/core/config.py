# Carga de variables que provienen del .env, tipada con pydantic-settings.
# TODOS los nombres de exchanges, colas y bindings viven aqui (nunca escritos en el codigo).

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Microservicio de Notificaciones"
    ENVIRONMENT: str = "local"

    # Credenciales para validar JWT de Azure AD
    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_ID: str = ""

    # --- RabbitMQ: ms-notificaciones es CONSUMIDOR. Apagado por defecto. ---
    RABBITMQ_ENABLED: bool = False
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_VHOST: str = "/"
    RABBITMQ_USER: str = ""
    RABBITMQ_PASSWORD: str = ""
    RABBITMQ_HEARTBEAT: int = 60
    RABBITMQ_CONNECTION_TIMEOUT: float = 5.0

    # Exchanges. Los dos de negocio los DUENOS son sus productores (ms-pedidos, ms-inventario); aqui se
    # redeclaran igual (idempotente) para poder bindear. El DLX es compartido por todos los servicios.
    RABBITMQ_EXCHANGE_PEDIDOS: str = "pedidos.events"        # TOPIC  (productor: ms-pedidos)
    RABBITMQ_EXCHANGE_ALERTAS: str = "pidealtoke.alertas"    # DIRECT (productor: ms-inventario)
    RABBITMQ_EXCHANGE_DLX: str = "pidealtoke.dlx"            # DIRECT: recibe los mensajes rechazados

    # Cola 1 (dominio: notificaciones de pedidos). Dos bindings: solo interesan los estados finales.
    RABBITMQ_QUEUE_NOTIF_PEDIDOS: str = "notificaciones.pedidos"
    RABBITMQ_QUEUE_NOTIF_PEDIDOS_DLQ: str = "notificaciones.pedidos.dlq"
    RABBITMQ_BINDING_PEDIDO_CONFIRMADO: str = "pedido.confirmado"
    RABBITMQ_BINDING_PEDIDO_CANCELADO: str = "pedido.cancelado"

    # Cola 2 (dominio: alertas de stock).
    RABBITMQ_QUEUE_ALERTAS_STOCK: str = "alertas.stock"
    RABBITMQ_QUEUE_ALERTAS_STOCK_DLQ: str = "alertas.stock.dlq"
    RABBITMQ_BINDING_STOCK_BAJO: str = "stock.bajo"

    # Consumo: prefetch por consumidor, hilos por cola y politica de reintentos.
    RABBITMQ_CONSUMER_PREFETCH: int = Field(10, ge=1)
    RABBITMQ_CONSUMER_CONCURRENCY: int = Field(2, ge=1, le=32)
    RABBITMQ_MAX_RETRIES: int = Field(3, ge=0)
    RABBITMQ_RETRY_BASE_SECONDS: float = Field(1.0, gt=0)
    RABBITMQ_RETRY_MAX_SECONDS: float = Field(30.0, gt=0)
    RABBITMQ_RECONNECT_MAX_SECONDS: float = Field(30.0, gt=0)


settings = Settings()

# Sin estos valores no se puede validar NINGUN token. Mejor fallar al arrancar con un mensaje claro.
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
