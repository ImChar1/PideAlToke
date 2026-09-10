# Carga de variables que provienen del .env
# Este archivo lee el .env de forma tipada usando pydantic-settings

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    PROJECT_NAME: str = "Microservicio de Pedidos"
    ENVIRONMENT: str = "local"
    DATABASE_URL: str

    # Credenciales para validar JWT de Azure AD
    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_ID: str = ""

    # URL base de ms-inventario, para reservar/liberar stock al crear un pedido.
    # En local: http://localhost:8001 (o el puerto que uses para levantarlo).
    # En AWS: URL interna de la EC2 backend / API Gateway.
    INVENTARIO_SERVICE_URL: str = "http://localhost:8001"

settings = Settings()
