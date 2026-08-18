"""
src/modules/tenants/router.py
===============================
Configuración inicial del tenant — Entregable pedido explícitamente
por Marco en esta sesión. Cada endpoint: validación (Pydantic/SQLModel
lo hace automático) + logging + auditoría + permiso RBAC.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from src.core.security import TokenPayload, get_current_user, require_permission
from src.database import get_session
from src.modules.tenants.models import TenantCreate, TenantRead, TenantUpdate
from src.modules.tenants.service import TenantService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.post(
    "",
    response_model=TenantRead,
    status_code=status.HTTP_201_CREATED,
    summary="Configuración inicial de un nuevo tenant",
)
def alta_tenant(
    data: TenantCreate,
    session: Session = Depends(get_session),
    user: TokenPayload = require_permission("usuarios:admin"),
):
    """
    Alta de un nuevo tenant (empresa cliente). Requiere permiso
    'usuarios:admin' — en la práctica, SUPER_ADMIN o TENANT_ADMIN.
    """
    service = TenantService(session)
    tenant = service.alta_tenant(data)
    logger.info("[Audit] Tenant creado por usuario=%s tenant=%s", user.sub, tenant.id)
    return tenant


@router.get("", response_model=list[TenantRead], summary="Listar tenants activos")
def listar_tenants(
    session: Session = Depends(get_session),
    user: TokenPayload = Depends(get_current_user),
):
    service = TenantService(session)
    return service.listar_activos()


@router.get("/{tenant_id}", response_model=TenantRead, summary="Detalle de un tenant")
def obtener_tenant(
    tenant_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: TokenPayload = Depends(get_current_user),
):
    service = TenantService(session)
    return service.obtener_o_404(tenant_id)


@router.patch("/{tenant_id}", response_model=TenantRead, summary="Actualizar configuración de tenant")
def actualizar_tenant(
    tenant_id: uuid.UUID,
    data: TenantUpdate,
    session: Session = Depends(get_session),
    user: TokenPayload = require_permission("usuarios:admin"),
):
    service = TenantService(session)
    tenant = service.actualizar(tenant_id, data)
    logger.info("[Audit] Tenant actualizado por usuario=%s tenant=%s", user.sub, tenant_id)
    return tenant


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Desactivar tenant (soft delete)")
def desactivar_tenant(
    tenant_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: TokenPayload = require_permission("usuarios:admin"),
):
    service = TenantService(session)
    service.desactivar(tenant_id)
    logger.warning("[Audit] Tenant desactivado por usuario=%s tenant=%s", user.sub, tenant_id)
