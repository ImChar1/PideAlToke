# Configuracion de la conexion con la DB

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# SQLite requiere check_same_thread=False, para PostgreSQL o MySQL no hace falta.
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependencia para inyectar sesion de DB en FastAPI, esta se cierra automaticamente al terminar el request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
