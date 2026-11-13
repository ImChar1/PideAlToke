# Carga de variables que provienen del .env, tipada con pydantic-settings

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore": docker compose comparte variables con otros servicios.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Microservicio de Administracion de Kafka"
    ENVIRONMENT: str = "local"

    # Credenciales para validar JWT de Azure AD
    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_ID: str = ""

    # Lista de brokers separados por coma. Dentro de la red de compose se usa el listener interno
    # (kafka1:29092,...). Con uno solo vivo basta para descubrir el resto del cluster.
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    # Timeout corto: es un API administrativo, si el cluster no responde se informa 503 rapido.
    KAFKA_REQUEST_TIMEOUT_SECONDS: float = Field(10.0, gt=0)


settings = Settings()

# Sin estos valores no se puede validar NINGUN token. Mejor fallar al arrancar con un mensaje claro.
if not settings.AZURE_TENANT_ID or not settings.AZURE_CLIENT_ID:
    raise RuntimeError(
        "Configuracion incompleta: define AZURE_TENANT_ID y AZURE_CLIENT_ID "
        "(variables de entorno o archivo .env)."
    )
