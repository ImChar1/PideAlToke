from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Microservicio de Catalogo de Productos"
    ENVIRONMENT: str = "local"
    DATABASE_URL: str

    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_ID: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()