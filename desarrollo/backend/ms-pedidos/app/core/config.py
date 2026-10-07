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

    # URL base de ms-catalogo: de ahi se toma el PRECIO REAL de cada producto
    # (el precio nunca se acepta desde el cliente).
    # En Docker: http://ms-catalogo:8000
    CATALOGO_SERVICE_URL: str = "http://localhost:8002"

    # Clave compartida entre microservicios para los movimientos de stock de
    # ms-inventario (reservar / liberar / confirmar-salida). Debe coincidir con la de ms-inventario.
    INTERNAL_API_KEY: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()