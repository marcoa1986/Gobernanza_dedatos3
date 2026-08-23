from typing import TypedDict, Dict, Any
from langgraph.graph import StateGraph, END
import json

class AgentState(TypedDict):
    folio_compra: str
    datos_compra: Dict[str, Any]
    decision_protagonista: str
    observaciones_protagonista: str
    auditoria_antagonista: str
    bandera_roja: bool
    decision_final_humano: str

def nodo_protagonista(state: AgentState):
    print(f"[Protagonista] Evaluando compra: {state.get('folio_compra')}")
    datos = state.get("datos_compra", {})
    
    if datos.get("factura_vs_oc") == "Pendiente":
        decision = "Retener Pago"
        obs = "Falta validar factura contra orden de compra."
    else:
        decision = "Aprobar Pago"
        obs = "Documentacion aparentemente completa."
        
    return {
        "decision_protagonista": decision,
        "observaciones_protagonista": obs
    }

def nodo_antagonista(state: AgentState):
    print("[Antagonista] Auditando decision del protagonista...")
    decision_prota = state.get("decision_protagonista")
    datos = state.get("datos_compra", {})
    
    bandera_roja = False
    auditoria = "Auditoria superada sin observaciones."
    
    if decision_prota == "Aprobar Pago" and datos.get("surtido_almacen") != "Completo":
        bandera_roja = True
        auditoria = "ALERTA RIESGO: El protagonista aprobo el pago, pero el almacen reporta surtido parcial."
        
    return {
        "auditoria_antagonista": auditoria,
        "bandera_roja": bandera_roja
    }

def requiere_humano(state: AgentState):
    if state.get("bandera_roja"):
        print("[Sistema] Bandera roja detectada por el Auditor. Interrumpiendo para revision del Human-in-the-loop.")
        return "revision_humana"
    print("[Sistema] Todo en orden. Flujo autorizado.")
    return "fin"

def nodo_humano(state: AgentState):
    print("[Humano] Revisando discrepancia en la consola...")
    decision_humana = state.get("decision_final_humano", "Pago Rechazado Manualmente - Requiere Aclaracion")
    return {"decision_final_humano": decision_humana}

workflow = StateGraph(AgentState)

workflow.add_node("protagonista", nodo_protagonista)
workflow.add_node("antagonista", nodo_antagonista)
workflow.add_node("revision_humana", nodo_humano)

workflow.set_entry_point("protagonista")
workflow.add_edge("protagonista", "antagonista")

workflow.add_conditional_edges(
    "antagonista",
    requiere_humano,
    {
        "revision_humana": "revision_humana",
        "fin": END
    }
)

workflow.add_edge("revision_humana", END)

app = workflow.compile()

if __name__ == "__main__":
    estado_inicial = {
        "folio_compra": "OC-2026-001",
        "datos_compra": {
            "factura_vs_oc": "Recibida",
            "surtido_almacen": "Parcial",
            "proveedor": "Proveedor Quimico Industrial"
        }
    }
    
    print("Iniciando flujo multi-agente para SMARTPROMARCO...\n")
    resultado = app.invoke(estado_inicial)
    
    print("\nResultado Final del Estado en Memoria:")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
