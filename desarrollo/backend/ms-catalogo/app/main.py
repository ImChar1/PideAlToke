# Punto de entrada de la app
from fastapi import FastAPI
from app.infrastructure.db.session import Base, engine
from app.adapters.api.v1.routers import productos_router

# Crear la tabla en la db si no existe para desarrollo local
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Microservicio de Catalogo de Productos - PideAltoke")

# Ruta del controlador de productos
app.include_router(productos_router.router)
