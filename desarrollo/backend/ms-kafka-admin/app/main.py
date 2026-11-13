from fastapi import FastAPI
from app.adapters.api.v1.routers import kafka_router

# Sin CORSMiddleware a proposito: es un API operativo (curl / Swagger / otros servicios), no lo
# consume el navegador de la app. Menos superficie expuesta.
app = FastAPI(title="Microservicio de Administracion de Kafka - PideAltoke")

# Controladores: /api/kafka/...
app.include_router(kafka_router.router)


# Endpoint de salud
@app.get("/api/v1/health", tags=["Health"])
def health_check():
    return {"status": "ok", "project": "Microservicio de Administracion de Kafka"}
