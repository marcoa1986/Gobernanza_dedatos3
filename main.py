from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any
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

class CompraRequest(BaseModel):
    folio_compra: str
    datos_compra: Dict[str, Any]

@app.post("/evaluar-compra/")
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