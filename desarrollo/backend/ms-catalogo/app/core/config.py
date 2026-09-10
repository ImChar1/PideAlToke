# Carga de variables que provienen del .env

# Este archivo lee el .env de forma tipada usando pydantic-settings
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Microservicio de Catalogo de Productos"
    ENVIRONMENT: str = "local"
    DATABASE_URL: str

    # Credenciales para validar JWT de Azure AD
    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_ID: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
