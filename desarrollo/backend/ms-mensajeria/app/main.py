from fastapi import FastAPI
from app.adapters.api.v1.routers import rabbitmq_router

# Sin CORSMiddleware a proposito: es un API operativo (curl / Swagger / otros servicios), no lo
# consume el navegador de la app. Menos superficie expuesta.
app = FastAPI(title="Microservicio de Mensajeria (Admin RabbitMQ) - PideAltoke")

# Controladores: /api/rabbitmq/...
app.include_router(rabbitmq_router.router)


# Endpoint de salud
@app.get("/api/v1/health", tags=["Health"])
def health_check():
    return {"status": "ok", "project": "Microservicio de Mensajeria"}
