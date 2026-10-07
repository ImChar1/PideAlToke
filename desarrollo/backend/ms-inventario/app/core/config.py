# Carga de variables que provienen del .env, tipada con pydantic-settings

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

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

settings = Settings()
