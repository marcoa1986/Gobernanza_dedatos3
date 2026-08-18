"""
src/api/dependencies.py
=========================
Esta es la capa "API Gateway" de la PoC (RN-GTW-001, ver ADR-001):
en microservicios reales sería un servicio aparte; aquí es un
middleware/dependencia FastAPI porque un PoC no necesita ese salto.

Flujo que implementa (el que pediste):
  JWT → validar firma → extraer tenant_id → validar Tenant existe
      → validar Tenant activo → validar permisos → handler
"""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from sqlmodel import Session

from src.core.security import TokenPayload, get_current_user
from src.database import get_session
from src.modules.tenants.models import Tenant
from src.modules.tenants.repository import TenantRepository


def get_tenant_activo(
    user: TokenPayload = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Tenant:
    """
    RN-GTW-001: Toda operación de negocio requiere un tenant existente Y activo.
    Se ejecuta DESPUÉS de get_current_user (JWT ya validado) y ANTES
    de cualquier lógica de negocio — así ningún router puede saltarse
    esta validación por accidente.
    """
    tenant = TenantRepository(session).obtener_por_id(uuid.UUID(user.tenant_id))
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant no encontrado.")
    if not tenant.activo:
        # 409, no 403: el problema no es el usuario, es el estado del tenant
        raise HTTPException(status.HTTP_409_CONFLICT, "Tenant deshabilitado. Contacta a soporte.")
    return tenant
