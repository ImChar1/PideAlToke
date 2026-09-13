from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.infrastructure.db.session import Base, engine
from app.adapters.api.v1.routers import productos_router

# Crear las tablas en la db si no existen para desarrollo local
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Microservicio de Catalogo de Productos - PideAltoke")

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Controladores
app.include_router(productos_router.router, prefix="/api/v1")

# Endpoint de salud
@app.get("/api/v1/health", tags=["Health"])
def health_check():
    return {"status": "ok", "project": "Microservicio de Catálogo de Productos"}