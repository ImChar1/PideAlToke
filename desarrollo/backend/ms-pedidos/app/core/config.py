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

    # --- RabbitMQ: ms-pedidos es PRODUCTOR de eventos de pedido ---
    # Apagado por defecto: sin broker (tests, `uvicorn` local) el servicio funciona igual y
    # simplemente no publica. docker compose lo enciende con RABBITMQ_ENABLED=true.
    RABBITMQ_ENABLED: bool = False
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_VHOST: str = "/"
    RABBITMQ_USER: str = ""
    RABBITMQ_PASSWORD: str = ""
    RABBITMQ_HEARTBEAT: int = 60
    # Timeout (s) de conexion/socket. Corto a proposito: publicar ocurre dentro de la peticion HTTP
    # y un broker caido no debe congelar la creacion de pedidos.
    RABBITMQ_CONNECTION_TIMEOUT: float = 5.0
    # Tras un fallo de publicacion no se vuelve a intentar durante estos segundos (evita que cada
    # peticion espere el timeout completo mientras el broker esta caido).
    RABBITMQ_PUBLISH_COOLDOWN_SECONDS: float = 10.0

    # Topologia que ESTE servicio necesita: el exchange donde publica y las routing keys.
    # (Debe coincidir con la que declara el consumidor: ms-inventario.)
    RABBITMQ_EXCHANGE_PEDIDOS: str = "pedidos.events"      # tipo TOPIC
    RABBITMQ_RK_PEDIDO_CREADO: str = "pedido.creado"
    RABBITMQ_RK_PEDIDO_CONFIRMADO: str = "pedido.confirmado"
    RABBITMQ_RK_PEDIDO_CANCELADO: str = "pedido.cancelado"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

# Sin estos dos valores no se puede validar NINGUN token (la URL de claves quedaria mal formada y
# cada peticion respondería un 401 confuso). Es mejor fallar al arrancar, con un mensaje claro.
if not settings.AZURE_TENANT_ID or not settings.AZURE_CLIENT_ID:
    raise RuntimeError(
        "Configuracion incompleta: define AZURE_TENANT_ID y AZURE_CLIENT_ID "
        "(variables de entorno o archivo .env)."
    )

# Con RabbitMQ encendido hacen falta credenciales: mejor fallar al arrancar con un mensaje claro
# que descubrirlo en la primera publicacion.
if settings.RABBITMQ_ENABLED and not (settings.RABBITMQ_USER and settings.RABBITMQ_PASSWORD):
    raise RuntimeError(
        "Configuracion incompleta: RABBITMQ_ENABLED=true requiere RABBITMQ_USER y RABBITMQ_PASSWORD."
    )
