"""
src/modules/copiloto/router.py
=================================
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlmodel import Session

from src.core.security import TokenPayload, require_permission
from src.database import get_session
from src.modules.copiloto.schemas import ResumenEjecutivo
from src.modules.copiloto.service import generar_resumen_ejecutivo

router = APIRouter(prefix="/copiloto", tags=["Copiloto Ejecutivo"])


@router.get(
    "/resumen-ejecutivo",
    response_model=ResumenEjecutivo,
    summary="Qué ocurre, por qué, impacto, recomendación, evidencia y decisión requerida",
)
def resumen_ejecutivo(
    tenant_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: TokenPayload = require_permission("dashboard:read"),
):
    return generar_resumen_ejecutivo(session, tenant_id)
