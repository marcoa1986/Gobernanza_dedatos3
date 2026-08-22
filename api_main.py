from fastapi import FastAPI, Depends
from sqlalchemy import create_engine, Column, String, Date
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from pydantic import BaseModel
from typing import List, Optional
from datetime import date

# 1. AQUÍ ESTÁ LA CONEXIÓN (Usamos localhost porque Docker expuso el puerto 5432)
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/smartpromarco"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. Modelo de la tabla
class Compra(Base):
    __tablename__ = "matriz_validacion_compras"
    
    folio = Column(String(50), primary_key=True)
    proveedor = Column(String(255))
    cotizacion = Column(String(20))
    orden_compra = Column(String(20))
    surtido_almacen = Column(String(20))
    factura_vs_oc = Column(String(50))
    datos_bancarios = Column(String(20))
    fecha_surtido = Column(Date)
    estatus_general = Column(String(50))
    fecha_pago_estimada = Column(Date)
    observaciones = Column(String)

# 3. Esquema de Pydantic para el JSON
class CompraSchema(BaseModel):
    folio: str
    proveedor: Optional[str]
    cotizacion: Optional[str]
    orden_compra: Optional[str]
    surtido_almacen: Optional[str]
    factura_vs_oc: Optional[str]
    datos_bancarios: Optional[str]
    fecha_surtido: Optional[date]
    estatus_general: Optional[str]
    fecha_pago_estimada: Optional[date]
    observaciones: Optional[str]

    class Config:
        from_attributes = True

app = FastAPI(title="API SMARTPROMARCO")

def get_db():
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()

# 4. Endpoint
@app.get("/compras/", response_model=List[CompraSchema])
def leer_compras(db_session: Session = Depends(get_db)):
    return db_session.query(Compra).all()