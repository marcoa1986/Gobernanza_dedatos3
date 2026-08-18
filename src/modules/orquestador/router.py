"""
src/modules/orquestador/router.py
====================================
Expone el patrón Decisor/Auditor como servicio HTTP independiente —
usable para auditar CUALQUIER propuesta (arquitectura, negocio, código),
no solo transacciones CRUD.

También expone el ciclo HITL de transacciones: listar pendientes y que
un humano las resuelva — sin esto, el Dashboard no tiene forma real de
aprobar/rechazar nada, solo de mostrar datos.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session

from src.core.security import TokenPayload, require_permission
from src.database import get_session
from src.modules.auditoria.models import EvidenciaRead
from src.modules.auditoria.service import AuditoriaService
from src.modules.orquestador.contexto_regulatorio import SECTORES_DISPONIBLES
from src.modules.orquestador.debate import ejecutar_debate
from src.modules.orquestador.schemas_debate import DebateRequest, ResultadoDebate
from src.modules.orquestador.service import OrquestadorService

router = APIRouter(prefix="/orquestador", tags=["Decisor / Auditor"])


# ── Debate Decisor/Auditor (propuestas de arquitectura, negocio, código) ──

@router.get("/debate/sectores", summary="Sectores con contexto regulatorio real disponible")
def listar_sectores(user: TokenPayload = require_permission("evidencia:read")):
    return {"sectores_disponibles": SECTORES_DISPONIBLES}


@router.post(
    "/debate",
    response_model=ResultadoDebate,
    summary="Ejecuta el debate Decisor↔Auditor sobre una propuesta, con guardrail de reintentos",
)
def debatir(
    data: DebateRequest,
    sectores: list[str] | None = None,
    user: TokenPayload = require_permission("evidencia:write"),
):
    """
    `sectores` (query param, repetible: ?sectores=banca&sectores=comercio_exterior)
    inyecta contexto regulatorio real en ambos agentes. Si se omite, el
    Auditor evalúa solo contra las 4 categorías técnicas base.
    """
    return ejecutar_debate(data, sectores=sectores)


# ── Ciclo HITL de transacciones CRUD auditadas ────────────────────────

class DecisionHumanaRequest(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject|modify)$")
    datos_modificados: dict | None = None


@router.get(
    "/transacciones/pendientes",
    response_model=list[EvidenciaRead],
    summary="Lista transacciones HITL esperando decisión humana",
)
def transacciones_pendientes(
    tenant_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: TokenPayload = require_permission("hitl:respond"),
):
    return AuditoriaService(session).listar_pendientes_hitl(tenant_id)


@router.post(
    "/transacciones/{transaction_id}/decision",
    response_model=EvidenciaRead,
    summary="Aprueba, rechaza o modifica una transacción HITL pendiente",
)
async def decidir_transaccion(
    transaction_id: uuid.UUID,
    data: DecisionHumanaRequest,
    session: Session = Depends(get_session),
    user: TokenPayload = require_permission("hitl:respond"),
):
    service = OrquestadorService(session)
    return await service.reanudar_con_decision(
        transaction_id=transaction_id, decision=data.decision,
        operador_id=user.sub, datos_modificados=data.datos_modificados,
    )
