from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.infrastructure.db.session import Base, engine
from app.adapters.api.v1.routers import pedidos_router
from app.core.config import settings
from app.adapters.messaging.pedido_eventos_handler import manejar_evento_pedido
from app.infrastructure.messaging.rabbitmq_consumer import ConsumerConfig, ConsumerManager
from app.infrastructure.messaging.event_publishers import cerrar_event_publisher

# Crear las tablas en la db si no existen para desarrollo local
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # El consumidor de RabbitMQ corre en hilos propios: se levanta con la app y se detiene al apagarla.
    # Con RABBITMQ_ENABLED=false (por defecto) no se toca el broker para nada.
    consumidores = None
    if settings.RABBITMQ_ENABLED:
        consumidores = ConsumerManager(ConsumerConfig.desde_settings(settings), manejar_evento_pedido)
        consumidores.iniciar()
    yield
    if consumidores is not None:
        consumidores.detener()
    # Al apagar: cerrar de forma limpia la conexion del publicador de RabbitMQ (si se abrio).
    cerrar_event_publisher()


app = FastAPI(title="Microservicio de Pedidos - PideAltoke", lifespan=lifespan)

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
) 

# Controladores
app.include_router(pedidos_router.router, prefix="/api/v1")

# Endpoint de salud
@app.get("/api/v1/health", tags=["Health"])
def health_check():
    return {"status": "ok", "project": "Microservicio de Pedidos"}