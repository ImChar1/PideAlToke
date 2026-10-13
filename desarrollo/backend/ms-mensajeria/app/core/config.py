# Carga de variables que provienen del .env, tipada con pydantic-settings

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore": docker compose comparte variables RABBITMQ_* con otros servicios (p. ej. RABBITMQ_ENABLED).
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Microservicio de Mensajeria"
    ENVIRONMENT: str = "local"

    # Credenciales para validar JWT de Azure AD
    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_ID: str = ""

    # Conexion a RabbitMQ (sin credenciales por defecto: ver validacion al final del archivo)
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_VHOST: str = "/"
    RABBITMQ_USER: str = ""
    RABBITMQ_PASSWORD: str = ""
    RABBITMQ_HEARTBEAT: int = 60
    # Timeout corto: es un API administrativo, si el broker no responde se informa 503 rapido.
    RABBITMQ_CONNECTION_TIMEOUT: float = 5.0


settings = Settings()

# Sin estos valores no se puede validar NINGUN token. Mejor fallar al arrancar con un mensaje claro.
if not settings.AZURE_TENANT_ID or not settings.AZURE_CLIENT_ID:
    raise RuntimeError(
        "Configuracion incompleta: define AZURE_TENANT_ID y AZURE_CLIENT_ID "
        "(variables de entorno o archivo .env)."
    )

# Este servicio no sirve de nada sin conexion al broker.
if not settings.RABBITMQ_USER or not settings.RABBITMQ_PASSWORD:
    raise RuntimeError(
        "Configuracion incompleta: define RABBITMQ_USER y RABBITMQ_PASSWORD "
        "(variables de entorno o archivo .env)."
    )
