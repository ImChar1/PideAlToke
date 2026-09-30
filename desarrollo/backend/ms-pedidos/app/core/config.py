from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Microservicio de Pedidos"
    ENVIRONMENT: str = "local"
    DATABASE_URL: str

    # Credenciales de Azure Entra ID
    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_ID: str = ""

    # URL base de ms-inventario.
    # En desarrollo local: http://localhost:8003 (o el puerto local de ms-inventario)
    # En Docker: http://ms-inventario:8000 (lo sobreescribe el archivo .env)
    INVENTARIO_SERVICE_URL: str = "http://localhost:8003"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()