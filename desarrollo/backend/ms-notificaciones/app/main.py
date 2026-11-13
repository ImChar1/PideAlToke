from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.api.v1.routers import notificaciones_router
from app.adapters.messaging.eventos_handlers import manejar_alerta_stock, manejar_notificacion_pedido
from app.core.config import settings
from app.infrastructure.messaging.rabbitmq_consumer import ConsumerConfig, ConsumerManager


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Los consumidores de RabbitMQ corren en hilos propios: se levantan con la app y se detienen al
    # apagarla. Cada cola tiene su propio manager (hilos, prefetch y reintentos independientes).
    # Con RABBITMQ_ENABLED=false (por defecto) no se toca el broker para nada.
    managers = []
    if settings.RABBITMQ_ENABLED:
        for cola, handler in (
            (settings.RABBITMQ_QUEUE_NOTIF_PEDIDOS, manejar_notificacion_pedido),
            (settings.RABBITMQ_QUEUE_ALERTAS_STOCK, manejar_alerta_stock),
        ):
            manager = ConsumerManager(ConsumerConfig.desde_settings(settings, cola), handler)
            manager.iniciar()
            managers.append(manager)
    yield
    for manager in managers:
        manager.detener()


app = FastAPI(title="Microservicio de Notificaciones - PideAltoke", lifespan=lifespan)

# Configuración de CORS (el dashboard Angular consume este API a traves del gateway)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Controladores
app.include_router(notificaciones_router.router, prefix="/api/v1")


# Endpoint de salud
@app.get("/api/v1/health", tags=["Health"])
def health_check():
    return {"status": "ok", "project": "Microservicio de Notificaciones"}
