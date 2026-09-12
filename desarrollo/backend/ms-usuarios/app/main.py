from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.infrastructure.db.session import engine, Base
from app.adapters.api.v1.routers.usuario_router import router as usuario_router

# Inicialización de tablas
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME)

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro de rutas siguiendo la arquitectura hexagonal
app.include_router(usuario_router, prefix="/api/v1")

@app.get("/api/v1/health", tags=["Health"])
def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME}