from sqlalchemy import Column, Integer, String, Boolean, Text
from database import Base

class MatrizValidacionCompras(Base):
    __tablename__ = "matriz_validacion_compras"

    # Identificadores básicos (Aquí estaba el detalle del guion bajo)
    id = Column(Integer, primary_key=True, index=True)
    folio_compra = Column(String, unique=True, index=True)
    # Estatus del proceso
    estatus_fase = Column(String, default="EN REVISIÓN")

    # Resultados del Sistema Multi-Agente
    decision_agente = Column(String)
    dictamen_auditor = Column(String)
    requiere_hitl = Column(Boolean, default=False)
    alertas_generadas = Column(Text)       # Lista de errores en formato JSON String
