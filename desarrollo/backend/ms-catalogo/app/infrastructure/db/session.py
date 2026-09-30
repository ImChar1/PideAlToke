from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

is_sqlite = "sqlite" in settings.DATABASE_URL.lower()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=not is_sqlite,
    pool_recycle=3600 if not is_sqlite else -1,
    connect_args={"check_same_thread": False} if is_sqlite else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()