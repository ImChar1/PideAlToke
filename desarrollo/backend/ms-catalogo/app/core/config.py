from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Microservicio de Catalogo de Productos"
    ENVIRONMENT: str = "local"
    DATABASE_URL: str

    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_ID: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

# Sin estos dos valores no se puede validar NINGUN token (la URL de claves quedaria mal formada y
# cada peticion respondería un 401 confuso). Es mejor fallar al arrancar, con un mensaje claro.
if not settings.AZURE_TENANT_ID or not settings.AZURE_CLIENT_ID:
    raise RuntimeError(
        "Configuracion incompleta: define AZURE_TENANT_ID y AZURE_CLIENT_ID "
        "(variables de entorno o archivo .env)."
    )
