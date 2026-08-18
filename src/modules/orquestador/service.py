"""
src/modules/orquestador/service.py
====================================
El orquestador ya no posee la lógica de hash/riesgo/loop — esa vive en
auditoria/service.py (es su dominio). El orquestador solo COORDINA:
Pydantic → Agente Auditor (LangGraph/Bedrock) → Loop Engine → Evidencia.

RN-ORQ-001: DELETE siempre requiere HITL (ver auditoria.service.determinar_tipo_loop)
RN-ORQ-002: El tenant define sus propios umbrales de riesgo (Tenant.umbral_hitl/hotl)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

from src.modules.auditoria.models import (
    Canal,
    Evidencia,
    EvidenciaCreate,
    NivelRiesgo,
    Operacion,
    TipoLoop,
)
from src.modules.auditoria.service import (
    AuditoriaService,
    determinar_tipo_loop,
    mapear_riesgo,
)
from src.modules.orquestador.ai_agents import AuditState, get_executor
from src.modules.tenants.models import Tenant

logger = logging.getLogger(__name__)


class TransaccionCRUD(BaseModel):
    """Transacción interceptada desde el sistema externo (Odoo/SAP/Salesforce)."""
    operacion: Operacion
    tabla: str
    payload: dict
    usuario_id: str
    ip_origen: str = "0.0.0.0"
    canal: Canal = Canal.B2B

    @field_validator("payload")
    @classmethod
    def payload_no_vacio(cls, v: dict) -> dict:
        if not v:
            raise ValueError("El payload no puede estar vacío")
        return v


class ResultadoOrquestacion(BaseModel):
    transaction_id: uuid.UUID
    thread_id: uuid.UUID
    riesgo: NivelRiesgo
    tipo_loop: TipoLoop
    estado_final: str
    hash_evidencia: Optional[str] = None
    tiempo_total_ms: float = 0.0


class OrquestadorService:
    """
    Coordinador del pipeline. Una instancia por request (recibe su
    propia sesión de BD) — no es un singleton con estado compartido,
    a diferencia del GraphExecutor (ese sí es singleton: mantiene el
    checkpointer de LangGraph).
    """

    def __init__(self, session: Session):
        self.session = session
        self.auditoria = AuditoriaService(session)
        self._graph_executor = get_executor()

    async def procesar_transaccion(
        self, transaccion: TransaccionCRUD, tenant: Tenant,
    ) -> ResultadoOrquestacion:
        inicio = datetime.now(timezone.utc)
        transaction_id = uuid.uuid4()
        thread_id = uuid.uuid4()

        logger.info(
            "[Orquestador] ▶ TXN=%s OP=%s TABLA=%s TENANT=%s",
            transaction_id, transaccion.operacion, transaccion.tabla, tenant.id,
        )

        # ── Agente Auditor (LangGraph + Bedrock) ────────────────
        initial_state: AuditState = {
            "thread_id": str(thread_id),
            "transaction_id": str(transaction_id),
            "operacion": transaccion.operacion.value,
            "tabla": transaccion.tabla,
            "datos": transaccion.payload,
            "usuario_id": transaccion.usuario_id,
            "ip_origen": transaccion.ip_origen,
            "timestamp": inicio.isoformat(),
            "resultado_auditoria": None,
            "risk_score": 0.0,
            "decision_humana": None,
            "datos_modificados": None,
            "propuesta_parche": None,
            "resultado_ejecucion": None,
            "estado_grafo": "auditando",
            "creado_en": inicio.isoformat(),
            "completado_en": None,
            "error": None,
        }
        estado_post_audit = await asyncio.to_thread(
            self._graph_executor.iniciar_auditoria, initial_state
        )
        audit_result = estado_post_audit.get("resultado_auditoria") or {}
        risk_score = float(estado_post_audit.get("risk_score", 0.5))

        # ── Determinar loop y riesgo (dominio: auditoria) ───────
        tipo_loop = determinar_tipo_loop(
            risk_score, transaccion.operacion, tenant.umbral_hitl, tenant.umbral_hotl
        )
        riesgo = mapear_riesgo(risk_score)

        # ── HOOTL: automático, sin pausa ─────────────────────────
        resultado_ejecucion = None
        if tipo_loop == TipoLoop.HOOTL:
            estado_final = await asyncio.to_thread(
                self._graph_executor.reanudar_con_decision, str(thread_id), "approve", None,
            )
            resultado_ejecucion = estado_final.get("resultado_ejecucion")

        # ── Registrar Evidencia (siempre — incluso si queda pendiente de HITL) ──
        evidencia = self.auditoria.registrar_evidencia(EvidenciaCreate(
            transaction_id=transaction_id,
            thread_id=thread_id,
            tenant_id=tenant.id,
            empresa=tenant.nombre,
            canal=transaccion.canal,
            operacion=transaccion.operacion,
            payload_original=transaccion.payload,
            esquema_pydantic="v2.0",
            validacion="PASS",
            riesgo=riesgo,
            agente_auditor=audit_result,
            explicacion=audit_result.get("razonamiento", ""),
            tipo_loop=tipo_loop,
            operador=None,
            decision="aprobar" if tipo_loop == TipoLoop.HOOTL else None,
            agente_decisor=None,
            resultado_ejecucion=resultado_ejecucion,
        ))

        tiempo_ms = round((datetime.now(timezone.utc) - inicio).total_seconds() * 1000, 2)
        estado_final_str = "completado" if tipo_loop == TipoLoop.HOOTL else f"pendiente_{tipo_loop.value.lower()}"

        logger.info(
            "[Orquestador] ✓ TXN=%s estado=%s hash=%s…",
            transaction_id, estado_final_str, evidencia.hash[:12],
        )
        return ResultadoOrquestacion(
            transaction_id=transaction_id, thread_id=thread_id,
            riesgo=riesgo, tipo_loop=tipo_loop, estado_final=estado_final_str,
            hash_evidencia=evidencia.hash, tiempo_total_ms=tiempo_ms,
        )

    async def reanudar_con_decision(
        self, transaction_id: uuid.UUID, decision: str, operador_id: str,
        datos_modificados: Optional[dict] = None,
    ) -> Evidencia:
        """
        Reanuda el hilo LangGraph pausado Y cierra la Evidencia — antes
        esto solo hacía lo primero; sin la segunda parte, una Evidencia
        HITL quedaba "pendiente" para siempre, sin importar lo que el
        operador decidiera en el Dashboard.
        """
        evidencia_pendiente = self.auditoria.obtener_o_404(transaction_id)
        if evidencia_pendiente.decision is not None:
            raise ValueError(f"Transacción '{transaction_id}' ya fue resuelta.")

        estado_final = await asyncio.to_thread(
            self._graph_executor.reanudar_con_decision,
            str(evidencia_pendiente.thread_id), decision, datos_modificados,
        )
        logger.info(
            "[Orquestador] Reanudado TXN=%s thread=%s decisión=%s operador=%s",
            transaction_id, evidencia_pendiente.thread_id, decision, operador_id,
        )

        return self.auditoria.completar_decision_hitl(
            transaction_id=transaction_id, decision=decision, operador=operador_id,
            agente_decisor=estado_final.get("propuesta_parche"),
            resultado_ejecucion=estado_final.get("resultado_ejecucion"),
        )
