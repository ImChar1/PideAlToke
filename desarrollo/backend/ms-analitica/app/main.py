from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.api.v1.routers import analitica_router
from app.adapters.messaging.eventos_handlers import crear_handler_movimientos, crear_handler_pedidos
from app.core.config import settings
from app.core.container import analitica
from app.infrastructure.kafka.kafka_consumer import ConsumerConfig, ConsumerManager


def _config(topico: str, grupo: str) -> ConsumerConfig:
    return ConsumerConfig(
        topico=topico,
        grupo=grupo,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        client_id=settings.KAFKA_CLIENT_ID,
        concurrencia=settings.KAFKA_CONSUMER_CONCURRENCY,
        max_reintentos=settings.KAFKA_MAX_RETRIES,
        espera_base=settings.KAFKA_RETRY_BASE_SECONDS,
        espera_maxima=settings.KAFKA_RETRY_MAX_SECONDS,
        reconexion_maxima=settings.KAFKA_RECONNECT_MAX_SECONDS,
        reconstruir_al_iniciar=settings.KAFKA_REBUILD_ON_START,
        session_timeout_ms=settings.KAFKA_SESSION_TIMEOUT_MS,
        max_poll_interval_ms=settings.KAFKA_MAX_POLL_INTERVAL_MS,
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Los consumidores corren en hilos propios: se levantan con la app y se detienen al apagarla.
    # Con KAFKA_ENABLED=false (por defecto) no se toca el cluster para nada.
    managers = []
    if settings.KAFKA_ENABLED:
        # Dos consumer groups independientes: cada uno lee TODO su topico a su propio ritmo.
        for topico, grupo, handler in (
            (settings.KAFKA_TOPIC_PEDIDOS, settings.KAFKA_GROUP_VENTAS, crear_handler_pedidos(analitica)),
            (settings.KAFKA_TOPIC_MOVIMIENTOS, settings.KAFKA_GROUP_STOCK, crear_handler_movimientos(analitica)),
        ):
            manager = ConsumerManager(
                _config(topico, grupo), handler,
                al_invalido=analitica.registrar_invalido, al_fallido=analitica.registrar_fallido,
            )
            manager.iniciar()
            managers.append(manager)
    yield
    for manager in managers:
        manager.detener()


app = FastAPI(title="Microservicio de Analitica (Kafka) - PideAltoke", lifespan=lifespan)

# Configuración de CORS (el dashboard Angular consume este API a traves del gateway)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Controladores
app.include_router(analitica_router.router, prefix="/api/v1")


# Endpoint de salud
@app.get("/api/v1/health", tags=["Health"])
def health_check():
    return {"status": "ok", "project": "Microservicio de Analitica"}
