from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.infrastructure.db.session import Base, engine
from app.adapters.api.v1.routers import inventario_router

# Crear las tablas en la db si no existen para desarrollo local
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Microservicio de Inventario - PideAltoke")

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Controladores
app.include_router(inventario_router.router, prefix="/api/v1")

# Endpoint de salud
@app.get("/api/v1/health", tags=["Health"])
def health_check():
    return {"status": "ok", "project": "Microservicio de Inventario"}