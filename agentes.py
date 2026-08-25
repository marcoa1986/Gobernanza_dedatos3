import json
import os
from typing import TypedDict, Dict, Any, Optional, List
from langgraph.graph import StateGraph, END

# ==========================================
# 1. DEFINICIÓN DEL ESTADO DEL GRAFO
# ==========================================
class EstadoCompra(TypedDict):
    folio_compra: str
    datos_compra: Dict[str, Any]       
    reglas_negocio: Optional[Dict]     
    politicas_iso: Optional[Dict]      
    decision_protagonista: str
    dictamen_auditor: str
    requiere_hitl: bool
    alertas_hitl: List[str]

# ==========================================
# 2. FUNCIONES DE LOS NODOS DEL GRAFO
# ==========================================

def nodo_cargar_gobernanza(state: EstadoCompra):
    """Nodo 1: Lee las reglas físicas de disco y las inyecta al estado."""
    try:
        with open("business_rules.json", "r", encoding="utf-8") as f:
            reglas = json.load(f)
        with open("policies.json", "r", encoding="utf-8") as f:
            politicas = json.load(f)
    except FileNotFoundError:
        print("⚠️ Advertencia: Archivos JSON de gobernanza no encontrados.")
        reglas, politicas = {}, {} 
        
    return {"reglas_negocio": reglas, "politicas_iso": politicas, "alertas_hitl": []}


def nodo_protagonista_decisor(state: EstadoCompra):
    """Nodo 2: Agente que toma la decisión primaria (Aprobar/Retener)."""
    datos = state["datos_compra"]
    qr_payload = datos.get("qr_payload")
    
    # Simulación de evaluación basada en reglas
    if qr_payload and datos.get("surtido_almacen") == "Completo":
        decision = "APROBAR"
    else:
        decision = "RETENER"
    
    return {"decision_protagonista": decision}


def nodo_antagonista_auditor(state: EstadoCompra):
    """
    Nodo 3: Agente Auditor. 
    Cruza los datos de la compra con las políticas exactas de policies.json 
    para determinar si se dispara el HITL.
    """
    decision_previa = state["decision_protagonista"]
    datos = state["datos_compra"]
    qr_payload = datos.get("qr_payload")
    alertas = state.get("alertas_hitl", [])
    
    # 1. Extraer las políticas de gobernanza cargadas en el Nodo 1
    politicas_iso = state.get("politicas_iso", {}).get("politicas_gobernanza_iso20000", {})
    condiciones_hitl = politicas_iso.get("requiere_revision_humana_si", {})
    
    requiere_hitl = False
    
    # 2. Evaluar dinámicamente según lo que dicta policies.json
    if condiciones_hitl.get("surtido_almacen_incompleto") and datos.get("surtido_almacen") == "Parcial":
        requiere_hitl = True
        alertas.append("- INFRACCIÓN ISO 20000: El surtido es 'Parcial'. Se requiere revisión manual.")
        
    if condiciones_hitl.get("qr_invalido") and (not qr_payload or qr_payload == "NO_QR"):
        requiere_hitl = True
        alertas.append("- INFRACCIÓN ISO 18004: Falla de trazabilidad. Código QR ausente o corrupto.")
        
    if condiciones_hitl.get("decision_previa_retenida") and decision_previa == "RETENER":
        requiere_hitl = True
        alertas.append("- ALERTA INTERNA: El Agente Decisor retuvo la orden preventiva. Auditar.")

    # 3. Emitir dictamen
    dictamen = "Revisión manual requerida (HITL)" if requiere_hitl else "Auditoría superada exitosamente."
    
    return {
        "dictamen_auditor": dictamen,
        "requiere_hitl": requiere_hitl,
        "alertas_hitl": alertas
    }


def nodo_notificar_hitl(state: EstadoCompra):
    """Nodo 4: Disparador de Alertas. Solo se ejecuta si requiere_hitl == True."""
    print("\n" + "!"*60)
    print(" 🚨 ALERTA MULTI-AGENTE: INTERVENCIÓN HUMANA REQUERIDA (HITL) 🚨")
    print(f" Folio afectado: {state.get('folio_compra')}")
    print(" Motivos detectados por el Antagonista:")
    for alerta in state.get("alertas_hitl", []):
        print(f"  {alerta}")
    print("!"*60 + "\n")
    
    return {}

# ==========================================
# 3. LÓGICA DE ENRUTAMIENTO CONDICIONAL
# ==========================================
def ruta_auditoria(state: EstadoCompra):
    """Dirige el tráfico del grafo dependiendo del dictamen del auditor."""
    if state.get("requiere_hitl"):
        return "ir_a_hitl"
    return "fin"

# ==========================================
# 4. CONSTRUCCIÓN DEL GRAFO
# ==========================================
workflow = StateGraph(EstadoCompra)

workflow.add_node("cargar_gobernanza", nodo_cargar_gobernanza)
workflow.add_node("protagonista", nodo_protagonista_decisor)
workflow.add_node("antagonista", nodo_antagonista_auditor)
workflow.add_node("notificar_hitl", nodo_notificar_hitl)

workflow.set_entry_point("cargar_gobernanza")
workflow.add_edge("cargar_gobernanza", "protagonista")
workflow.add_edge("protagonista", "antagonista")

# Desvío condicional hacia HITL
workflow.add_conditional_edges(
    "antagonista",
    ruta_auditoria,
    {
        "ir_a_hitl": "notificar_hitl",
        "fin": END
    }
)

workflow.add_edge("notificar_hitl", END)

# Compilación final
app = workflow.compile()