from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ==========================================
# CONFIGURACIÓN DE LA BASE DE DATOS
# ==========================================
# Formato: postgresql://usuario:password@servidor:puerto/nombre_bd
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/smartpromarco_db"

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