"""
graph_agents.py
===============
Grafo LangGraph de dos agentes con Human-in-the-Loop.

Flujo:
  agente_auditor ──► [INTERRUPT] ──► tomar_decision ──► ejecutar_accion ──► END

  1. agente_auditor  : Llama a Bedrock/Claude, analiza la transacción CRUD
                       contra el historial de bugs, produce risk_score.

  2. [INTERRUPT]     : LangGraph pausa el hilo ANTES de tomar_decision.
                       El operador ve la auditoría en el dashboard y elige:
                         • "approve"  → deja que el decisor proponga el parche
                         • "reject"   → termina sin ejecutar
                         • "modify"   → edita datos en caliente, luego continúa

  3. tomar_decision  : Llama a Bedrock/Claude, formaliza el parche de ejecución
                       teniendo en cuenta la decisión humana.

  4. ejecutar_accion : Aplica el parche en la BD real (Odoo/Postgres).
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime
from functools import lru_cache
from typing import Optional, TypedDict

import boto3
from botocore.config import Config as BotoConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from src.core.config import get_settings

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
# ESTADO DEL GRAFO
# ══════════════════════════════════════════════════════════════

class AuditState(TypedDict):
    """Estado completo que se persiste en cada checkpoint."""

    # ── Transacción CRUD original ──────────────────────────
    thread_id: str
    transaction_id: str
    operacion: str              # CREATE | UPDATE | DELETE
    tabla: str
    datos: dict
    usuario_id: str
    ip_origen: str
    timestamp: str

    # ── Output del auditor ─────────────────────────────────
    resultado_auditoria: Optional[dict]
    risk_score: float            # 0.0 (seguro) – 1.0 (crítico)

    # ── Decisión humana (se inyecta tras interrupt) ────────
    decision_humana: Optional[str]   # "approve" | "reject" | "modify"
    datos_modificados: Optional[dict]

    # ── Output del decisor ─────────────────────────────────
    propuesta_parche: Optional[dict]

    # ── Resultado de ejecución ─────────────────────────────
    resultado_ejecucion: Optional[dict]

    # ── Ciclo de vida ──────────────────────────────────────
    estado_grafo: str   # auditando | esperando_decision | ejecutando | completado | rechazado | error
    creado_en: str
    completado_en: Optional[str]
    error: Optional[str]


# ══════════════════════════════════════════════════════════════
# CLIENTE AWS BEDROCK  (singleton, thread-safe)
# ══════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def _bedrock_client():
    """
    Crea el cliente boto3 una sola vez.
    • En producción (ECS/Lambda) NO se pasan keys → usa IAM Role automáticamente.
    • En desarrollo local se leen de .env via config.
    """
    cfg = get_settings()

    boto_cfg = BotoConfig(
        connect_timeout=cfg.connect_timeout,
        read_timeout=cfg.read_timeout,
        retries={"max_attempts": cfg.max_retries, "mode": "adaptive"},
    )

    kwargs: dict = {
        "service_name": "bedrock-runtime",
        "region_name": cfg.aws_region,
        "config": boto_cfg,
    }

    # Solo agrega keys si están explícitamente configuradas (dev)
    if cfg.aws_access_key_id:
        kwargs["aws_access_key_id"]     = cfg.aws_access_key_id
        kwargs["aws_secret_access_key"] = cfg.aws_secret_access_key

    client = boto3.client(**kwargs)
    logger.info("Bedrock client inicializado | modelo=%s región=%s",
                cfg.model_id, cfg.aws_region)
    return client


def _invoke_claude(system: str, user: str,
                   max_tokens: int = 1024,
                   temperature: float | None = None) -> str:
    """
    Wrapper mínimo sobre boto3 invoke_model para Claude en Bedrock.
    Retorna el texto de la primera respuesta del modelo.
    """
    cfg = get_settings()
    client = _bedrock_client()
    temp = temperature if temperature is not None else cfg.temperature

    payload = {
        "anthropic_version": "bedrock-2023-06-01",
        "max_tokens": max_tokens,
        "temperature": temp,
        "top_p": cfg.top_p,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }

    if cfg.log_bedrock_calls:
        logger.debug("Bedrock →  %.120s …", user)

    response = client.invoke_model(
        modelId=cfg.model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(payload),
    )

    body = json.loads(response["body"].read())

    if cfg.log_token_usage:
        u = body.get("usage", {})
        logger.info("Bedrock tokens  in=%s  out=%s",
                    u.get("input_tokens"), u.get("output_tokens"))

    return body["content"][0]["text"]


def _parse_json(text: str) -> dict:
    """Extrae el primer bloque JSON de la respuesta de Claude."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return json.loads(m.group())
    return json.loads(text)


# ══════════════════════════════════════════════════════════════
# NODO 1 — AGENTE AUDITOR
# ══════════════════════════════════════════════════════════════

_AUDITOR_SYSTEM = """\
Eres un auditor experto en seguridad y calidad de bases de datos empresariales.
Analiza transacciones CRUD e identifica riesgos y anomalías.

RESPONDE ÚNICAMENTE EN JSON (sin texto extra):
{
  "es_valida"           : boolean,
  "risk_score"          : float (0.0 = seguro, 1.0 = crítico),
  "problemas_detectados": ["desc1", "desc2"],
  "bugs_similares"      : [{"bug_id": "QA-XXX", "descripcion": "..."}],
  "patron_sospechoso"   : boolean,
  "razonamiento"        : "Explicación concisa en español"
}"""

_BUGS_CONOCIDOS = """\
- QA-2024-001: Duplicación en UPDATE sin control de versión concurrente
- QA-2024-002: DELETE en cascada no controlado en tablas relacionadas
- QA-2024-003: Inyección SQL en campos de búsqueda libre
- QA-2024-004: Montos negativos en transacciones financieras
- QA-2024-005: Escalamiento de privilegios en modificaciones masivas
- QA-2024-006: Campos requeridos vacíos bypaseando validación de schema"""


def agente_auditor(state: AuditState) -> dict:
    """
    Nodo 1: llama a Claude para auditar la transacción.
    Produce resultado_auditoria y risk_score en el estado.
    """
    logger.info("[Auditor] Analizando %s | op=%s tabla=%s",
                state["transaction_id"], state["operacion"], state["tabla"])

    user_msg = f"""\
Transacción a auditar:
  ID          : {state["transaction_id"]}
  Operación   : {state["operacion"]}
  Tabla       : {state["tabla"]}
  Usuario     : {state["usuario_id"]}
  IP origen   : {state["ip_origen"]}
  Timestamp   : {state["timestamp"]}
  Datos       :
{json.dumps(state["datos"], indent=4, ensure_ascii=False)}

Historial de bugs conocidos:
{_BUGS_CONOCIDOS}

¿Presenta riesgos esta transacción?"""

    try:
        raw = _invoke_claude(_AUDITOR_SYSTEM, user_msg,
                             max_tokens=900, temperature=0.2)
        audit = _parse_json(raw)
        risk  = float(audit.get("risk_score", 0.5))

        logger.info("[Auditor] Completado | risk_score=%.2f válida=%s",
                    risk, audit.get("es_valida"))
        return {
            "resultado_auditoria": audit,
            "risk_score": risk,
            "estado_grafo": "esperando_decision",
        }

    except Exception as exc:
        logger.exception("[Auditor] Error inesperado")
        return {
            "resultado_auditoria": {"error": str(exc)},
            "risk_score": 0.5,
            "estado_grafo": "error",
            "error": f"Error en auditoría: {exc}",
        }


# ══════════════════════════════════════════════════════════════
# NODO 2 — DECISOR  (se ejecuta DESPUÉS del interrupt)
# ══════════════════════════════════════════════════════════════

_DECISOR_SYSTEM = """\
Eres un agente decisor de transacciones de base de datos.
El operador humano ya revisó la auditoría y tomó una decisión.
Tu rol es formalizar el parche de ejecución.

RESPONDE ÚNICAMENTE EN JSON:
{
  "patch_id"           : "PATCH-YYYYMMDD-NNN",
  "accion"             : "EJECUTAR" | "EJECUTAR_MODIFICADO" | "RECHAZAR",
  "motivo"             : "Justificación concisa",
  "datos_a_ejecutar"   : { ... datos finales ... },
  "validaciones_extra" : ["validación1"],
  "nivel_impacto"      : "BAJO" | "MEDIO" | "ALTO",
  "requiere_rollback"  : boolean
}"""


def tomar_decision(state: AuditState) -> dict:
    """
    Nodo 2: formaliza el parche basándose en:
      • El resultado de auditoría del nodo anterior
      • La decisión humana inyectada tras el interrupt

    ⚠️  Este nodo está precedido por interrupt_before=['tomar_decision'].
        Cuando LangGraph llega aquí, decision_humana ya está en el estado.
    """
    decision = state.get("decision_humana") or "approve"
    logger.info("[Decisor] decision_humana=%s", decision)

    # Rechazo directo: no llama a Claude (ahorra latencia + costo)
    if decision == "reject":
        return {
            "propuesta_parche": {
                "accion"  : "RECHAZAR",
                "motivo"  : "Rechazado explícitamente por el operador.",
                "patch_id": f"PATCH-REJECTED-{state['transaction_id']}",
                "nivel_impacto": "BAJO",
                "requiere_rollback": False,
            },
            "estado_grafo": "rechazado",
        }

    # Approve / Modify: Claude formaliza el parche
    datos_finales = state.get("datos_modificados") or state["datos"]

    user_msg = f"""\
Resultado de auditoría:
{json.dumps(state["resultado_auditoria"], indent=4, ensure_ascii=False)}

Decisión del operador : {decision.upper()}
Datos originales      : {json.dumps(state["datos"], indent=4, ensure_ascii=False)}
Datos finales         : {json.dumps(datos_finales, indent=4, ensure_ascii=False)}
Operación             : {state["operacion"]} en tabla '{state["tabla"]}'

Genera el parche de ejecución formal."""

    try:
        raw   = _invoke_claude(_DECISOR_SYSTEM, user_msg,
                               max_tokens=700, temperature=0.1)
        parche = _parse_json(raw)
        logger.info("[Decisor] Parche generado | accion=%s impacto=%s",
                    parche.get("accion"), parche.get("nivel_impacto"))
        return {
            "propuesta_parche": parche,
            "estado_grafo": "ejecutando",
        }

    except Exception as exc:
        logger.exception("[Decisor] Error inesperado")
        return {
            "propuesta_parche": {"accion": "ERROR", "motivo": str(exc)},
            "estado_grafo": "error",
            "error": f"Error en decisor: {exc}",
        }


# ══════════════════════════════════════════════════════════════
# NODO 3 — EJECUTOR
# ══════════════════════════════════════════════════════════════

def ejecutar_accion(state: AuditState) -> dict:
    """
    Nodo 3: aplica el parche aprobado en la base de datos.
    Aquí se conectaría al cliente real de Odoo / PostgreSQL.
    """
    parche = state.get("propuesta_parche") or {}
    accion = parche.get("accion", "ERROR")

    if accion in ("RECHAZAR", "ERROR"):
        return {
            "resultado_ejecucion": {"status": "skipped", "accion": accion},
            "estado_grafo"       : "rechazado",
            "completado_en"      : datetime.utcnow().isoformat(),
        }

    logger.info("[Executor] Aplicando '%s' en tabla '%s'",
                accion, state["tabla"])

    try:
        # ── 🔌 Integración real (Odoo RPC / psycopg2) ──────────────
        # from odoo_client import get_client
        # odoo = get_client()
        # odoo.execute_kw(state["tabla"], state["operacion"].lower(),
        #                 [parche["datos_a_ejecutar"]])
        # ──────────────────────────────────────────────────────────

        resultado = {
            "status"        : "success",
            "patch_id"      : parche.get("patch_id"),
            "transaction_id": state["transaction_id"],
            "operacion"     : state["operacion"],
            "tabla"         : state["tabla"],
            "nivel_impacto" : parche.get("nivel_impacto", "BAJO"),
            "filas_afectadas": 1,
            "ejecutado_en"  : datetime.utcnow().isoformat(),
        }
        logger.info("[Executor] ✅ %s", resultado["patch_id"])
        return {
            "resultado_ejecucion": resultado,
            "estado_grafo"       : "completado",
            "completado_en"      : datetime.utcnow().isoformat(),
        }

    except Exception as exc:
        logger.exception("[Executor] Error al ejecutar")
        return {
            "resultado_ejecucion": {"status": "error", "error": str(exc)},
            "estado_grafo"       : "error",
            "error"              : f"Error al ejecutar: {exc}",
            "completado_en"      : datetime.utcnow().isoformat(),
        }


# ══════════════════════════════════════════════════════════════
# ROUTING
# ══════════════════════════════════════════════════════════════

def _ruta_post_decision(state: AuditState) -> str:
    """Si el decisor rechazó o encontró error, va directo a END."""
    if state.get("estado_grafo") in ("rechazado", "error"):
        return END
    return "ejecutar_accion"


# ══════════════════════════════════════════════════════════════
# CONSTRUCCIÓN DEL GRAFO
# ══════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def _checkpointer() -> SqliteSaver:
    """Checkpointer SQLite para persistir estados entre invocaciones."""
    cfg  = get_settings()
    conn = sqlite3.connect(cfg.sqlite_db_path, check_same_thread=False)
    saver = SqliteSaver(conn)
    logger.info("SqliteSaver listo | db=%s", cfg.sqlite_db_path)
    return saver


def build_graph():
    """
    Construye y compila el grafo con:
      • interrupt_before=['tomar_decision']  → pausa nativa de LangGraph
      • SqliteSaver                          → checkpoints persistentes
    """
    wf = StateGraph(AuditState)

    wf.add_node("agente_auditor", agente_auditor)
    wf.add_node("tomar_decision",  tomar_decision)
    wf.add_node("ejecutar_accion", ejecutar_accion)

    wf.set_entry_point("agente_auditor")
    wf.add_edge("agente_auditor", "tomar_decision")
    wf.add_conditional_edges("tomar_decision", _ruta_post_decision)
    wf.add_edge("ejecutar_accion", END)

    cfg = get_settings()

    graph = wf.compile(
        checkpointer=_checkpointer(),
        interrupt_before=[cfg.interrupt_node],   # ← "tomar_decision"
    )

    logger.info("✅ Grafo compilado | interrupt_before=['%s']", cfg.interrupt_node)
    return graph


# ══════════════════════════════════════════════════════════════
# EXECUTOR DE ALTO NIVEL
# ══════════════════════════════════════════════════════════════

class GraphExecutor:
    """
    API de alto nivel para FastAPI.
    Oculta los detalles de checkpoints y configuración del grafo.
    """

    def __init__(self):
        self.graph = build_graph()

    # ── Helpers ──────────────────────────────────────────────────

    def _config(self, thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    def _snapshot_values(self, thread_id: str) -> Optional[dict]:
        snap = self.graph.get_state(self._config(thread_id))
        return dict(snap.values) if snap else None

    def esta_pausado(self, thread_id: str) -> bool:
        """True si el hilo está esperando en interrupt."""
        cfg  = get_settings()
        snap = self.graph.get_state(self._config(thread_id))
        return bool(snap and cfg.interrupt_node in (snap.next or []))

    # ── Operaciones principales ───────────────────────────────────

    def iniciar_auditoria(self, state: AuditState) -> dict:
        """
        Ejecuta el grafo desde el inicio hasta el interrupt.
        Retorna el estado con resultado_auditoria y risk_score.
        La ejecución queda PAUSADA antes de tomar_decision.
        """
        cfg = self._config(state["thread_id"])
        self.graph.invoke(state, config=cfg)  # se detiene en interrupt
        snap_vals = self._snapshot_values(state["thread_id"])
        return snap_vals or {}

    def reanudar_con_decision(
        self,
        thread_id: str,
        decision: str,                        # "approve" | "reject" | "modify"
        datos_modificados: Optional[dict] = None,
    ) -> dict:
        """
        1. Verifica que el hilo esté pausado.
        2. Inyecta la decisión humana en el estado.
        3. Reanuda la ejecución → decisor → executor → END.
        """
        if not self.esta_pausado(thread_id):
            raise ValueError(f"Thread '{thread_id}' no está pausado en interrupt.")

        cfg = self._config(thread_id)

        # Inyectar decisión humana en el checkpoint actual
        self.graph.update_state(
            cfg,
            {
                "decision_humana"  : decision,
                "datos_modificados": datos_modificados,
            },
        )

        # None como input = "continúa desde el último checkpoint"
        self.graph.invoke(None, config=cfg)

        return self._snapshot_values(thread_id) or {}

    def obtener_estado(self, thread_id: str) -> Optional[dict]:
        return self._snapshot_values(thread_id)


# Singleton compartido por FastAPI y tests
_executor: Optional[GraphExecutor] = None


def get_executor() -> GraphExecutor:
    global _executor
    if _executor is None:
        _executor = GraphExecutor()
    return _executor
