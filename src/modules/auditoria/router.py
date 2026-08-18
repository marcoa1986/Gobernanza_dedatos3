"""
src/modules/auditoria/router.py
=================================
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from src.core.security import TokenPayload, get_current_user, require_permission
from src.database import get_session
from src.modules.auditoria.models import (
    EvidenciaCreate,
    EvidenciaRead,
    HallazgoAuditoriaCreate,
    HallazgoAuditoriaRead,
    MatrizTrazabilidadCreate,
    MatrizTrazabilidadRead,
    NivelRiesgo,
)
from src.modules.auditoria.service import AuditoriaService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qa", tags=["Auditoría"])


# ── Evidencia ─────────────────────────────────────────────────

@router.post(
    "/evidencia", response_model=EvidenciaRead, status_code=status.HTTP_201_CREATED,
    summary="Registrar evidencia (llamado internamente por el orquestador)",
)
def registrar_evidencia(
    data: EvidenciaCreate,
    session: Session = Depends(get_session),
    user: TokenPayload = require_permission("evidencia:write"),
):
    return AuditoriaService(session).registrar_evidencia(data)


@router.get("/evidencia/{transaction_id}", response_model=EvidenciaRead, summary="Detalle de una evidencia")
def obtener_evidencia(
    transaction_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: TokenPayload = require_permission("evidencia:read"),
):
    return AuditoriaService(session).obtener_o_404(transaction_id)


@router.get(
    "/evidencia/{transaction_id}/verificar", summary="Verificar integridad SHA-256 (paso 5 del ciclo de auditoría)",
)
def verificar_integridad(
    transaction_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: TokenPayload = require_permission("auditoria:read"),
):
    integra = AuditoriaService(session).verificar_integridad(transaction_id)
    return {"transaction_id": transaction_id, "integra": integra}


@router.get("/evidencia", response_model=list[EvidenciaRead], summary="Listar evidencia de un tenant")
def listar_evidencia(
    tenant_id: uuid.UUID,
    riesgo: NivelRiesgo | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    user: TokenPayload = require_permission("evidencia:read"),
):
    service = AuditoriaService(session)
    return service.listar_por_tenant(
        tenant_id, limit=limit, offset=offset,
        solo_riesgo=riesgo.value if riesgo else None,
    )


@router.get("/dashboard/kpis", summary="KPIs agregados — base del Dashboard BI")
def kpis(
    tenant_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: TokenPayload = require_permission("dashboard:read"),
):
    return AuditoriaService(session).kpis(tenant_id)


# ── Matriz de Trazabilidad ───────────────────────────────────

@router.post(
    "/trazabilidad", response_model=MatrizTrazabilidadRead, status_code=status.HTTP_201_CREATED,
    summary="Registrar fila en la Matriz de Trazabilidad",
)
def registrar_trazabilidad(
    data: MatrizTrazabilidadCreate,
    session: Session = Depends(get_session),
    user: TokenPayload = require_permission("evidencia:write"),
):
    return AuditoriaService(session).registrar_trazabilidad(data)


@router.get("/trazabilidad", response_model=list[MatrizTrazabilidadRead], summary="Matriz de Trazabilidad de un tenant")
def matriz_trazabilidad(
    tenant_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: TokenPayload = require_permission("trazabilidad:read"),
):
    return AuditoriaService(session).matriz_por_tenant(tenant_id)


# ── Hallazgos (Auditor Interno) ──────────────────────────────

@router.post(
    "/hallazgos", response_model=HallazgoAuditoriaRead, status_code=status.HTTP_201_CREATED,
    summary="Registrar hallazgo (paso 7 del ciclo de auditoría interna)",
)
def registrar_hallazgo(
    data: HallazgoAuditoriaCreate,
    session: Session = Depends(get_session),
    user: TokenPayload = require_permission("auditoria:write"),
):
    return AuditoriaService(session).registrar_hallazgo(data)


@router.post(
    "/hallazgos/{hallazgo_id}/cerrar", response_model=HallazgoAuditoriaRead,
    summary="Cerrar hallazgo (paso 8: cerrar auditoría)",
)
def cerrar_hallazgo(
    hallazgo_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: TokenPayload = require_permission("auditoria:write"),
):
    return AuditoriaService(session).cerrar_hallazgo(hallazgo_id)


@router.get(
    "/hallazgos", response_model=list[HallazgoAuditoriaRead],
    summary="Hallazgos de un período (ej. '2026-07')",
)
def hallazgos_periodo(
    tenant_id: uuid.UUID,
    periodo: str,
    session: Session = Depends(get_session),
    user: TokenPayload = require_permission("auditoria:read"),
):
    return AuditoriaService(session).hallazgos_del_periodo(tenant_id, periodo)
