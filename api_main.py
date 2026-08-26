from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
import json
from sqlalchemy.orm import Session

# Importaciones locales de BD
from database import engine, get_db, Base
from models import MatrizValidacionCompras 
from agentes import app as workflow_agentes

# ==========================================
# CREACIÓN AUTOMÁTICA DE TABLAS AL ARRANCAR
# ==========================================
Base.metadata.create_all(bind=engine)

app = FastAPI(title="API SMARTPROMARCO", version="1.0")

# ==========================================
# SCHEMAS (MOLDES JSON PARA PYDANTIC)
# ==========================================

class CompraRequest(BaseModel):
    folio_compra: str
    datos_compra: Dict[str, Any]

class CompraResponse(BaseModel):
    id: int
    folio_compra: str
    estatus_fase: str
    decision_agente: Optional[str] = None
    requiere_hitl: bool
    
    class Config:
        from_attributes = True

class CompraUpdate(BaseModel):
    estatus_fase: str
    requiere_hitl: bool

# ==========================================
# ENDPOINTS (RUTAS DE LA API)
# ==========================================

@app.post("/evaluar-compra/", tags=["Validación de Compras"])
async def evaluar_compra(request: CompraRequest, db: Session = Depends(get_db)):
    try:
        estado_inicial = {
            "folio_compra": request.folio_compra,
            "datos_compra": request.datos_compra,
            "reglas_negocio": {},
            "politicas_iso": {},
            "decision_protagonista": "",
            "dictamen_auditor": "",
            "requiere_hitl": False,
            "alertas_hitl": []
        }

        # Ejecuta LangGraph
        estado_final = workflow_agentes.invoke(estado_inicial)

        # Prepara los datos para PostgreSQL
        alertas_json_str = json.dumps(estado_final.get("alertas_hitl", []))

        nuevo_registro = MatrizValidacionCompras(
            folio_compra=estado_final.get("folio_compra"),
            decision_agente=estado_final.get("decision_protagonista"),
            dictamen_auditor=estado_final.get("dictamen_auditor"),
            requiere_hitl=estado_final.get("requiere_hitl"),
            alertas_generadas=alertas_json_str
        )

        # Inserta en la Base de Datos
        db.add(nuevo_registro)
        db.commit()
        db.refresh(nuevo_registro)

        return {
            "estatus": "guardado_exitosamente",
            "id_bd": nuevo_registro.id,
            "folio": estado_final.get("folio_compra"),
            "resultado_agentes": {
                "decision_protagonista": estado_final.get("decision_protagonista"),
                "dictamen_auditor": estado_final.get("dictamen_auditor"),
                "requiere_hitl": estado_final.get("requiere_hitl"),
                "alertas_hitl": estado_final.get("alertas_hitl", [])
            }
        }

    except Exception as e:
        db.rollback() 
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@app.get("/evaluar-compra/{folio_compra}", response_model=CompraResponse, tags=["Validación de Compras"])
def consultar_compra(folio_compra: str, db: Session = Depends(get_db)):
    """Consulta el estatus actual de una evaluación de compra."""
    compra = db.query(MatrizValidacionCompras).filter(MatrizValidacionCompras.folio_compra == folio_compra).first()
    if not compra:
        raise HTTPException(status_code=404, detail="Folio no encontrado")
    return compra


@app.put("/evaluar-compra/{folio_compra}", response_model=CompraResponse, tags=["Validación de Compras"])
def actualizar_compra(folio_compra: str, datos: CompraUpdate, db: Session = Depends(get_db)):
    """Actualiza el estatus de la compra tras una revisión manual."""
    compra = db.query(MatrizValidacionCompras).filter(MatrizValidacionCompras.folio_compra == folio_compra).first()
    if not compra:
        raise HTTPException(status_code=404, detail="Folio no encontrado")
    
    compra.estatus_fase = datos.estatus_fase
    compra.requiere_hitl = datos.requiere_hitl
    
    db.commit()
    db.refresh(compra)
    return compra


@app.delete("/evaluar-compra/{folio_compra}", tags=["Validación de Compras"])
def eliminar_compra(folio_compra: str, db: Session = Depends(get_db)):
    """Elimina un registro de validación de la base de datos."""
    compra = db.query(MatrizValidacionCompras).filter(MatrizValidacionCompras.folio_compra == folio_compra).first()
    if not compra:
        raise HTTPException(status_code=404, detail="Folio no encontrado")
    
    db.delete(compra)
    db.commit()
    return {"mensaje": f"El folio {folio_compra} ha sido eliminado correctamente"}