import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ==========================================
# CONFIGURACIÓN DE LA BASE DE DATOS
# ==========================================
# Lee la variable de entorno inyectada por Docker o usa el host 'smartpromarco-postgres'
import os

database_url: str = os.getenv(
    "DATABASE_URL", 
    "postgresql+psycopg2://postgres:postgres@smartpromarco-postgres:5432/smartpromarco_db"
)
redis_url: str = os.getenv("REDIS_URL", "redis://smartpromarco-redis:6379")

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependencia para inyectar la sesión en los endpoints de FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()