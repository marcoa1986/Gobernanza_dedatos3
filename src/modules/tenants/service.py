"""
src/modules/tenants/service.py
================================
Service Layer: reglas de negocio. El Router nunca toca el Repository
directamente — siempre pasa por aquí.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException, status
from sqlmodel import Session

from src.modules.tenants.models import Tenant, TenantCreate, TenantUpdate
from src.modules.tenants.repository import TenantRepository

logger = logging.getLogger(__name__)

PLANES_VALIDOS = {"starter", "professional", "enterprise"}


class TenantService:
    def __init__(self, session: Session):
        self.repo = TenantRepository(session)

    def alta_tenant(self, data: TenantCreate) -> Tenant:
        """
        Configuración inicial de un nuevo tenant (onboarding).
        Regla de negocio: RFC único, plan válido, umbrales HITL > HOTL.
        """
        if data.plan not in PLANES_VALIDOS:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Plan '{data.plan}' inválido. Debe ser uno de: {sorted(PLANES_VALIDOS)}",
            )
        if data.umbral_hitl <= data.umbral_hotl:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "umbral_hitl debe ser mayor que umbral_hotl (HITL es el riesgo más alto).",
            )
        if data.rfc and self.repo.obtener_por_rfc(data.rfc):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Ya existe un tenant registrado con RFC '{data.rfc}'.",
            )

        tenant = self.repo.crear(data)
        logger.info("[Tenant] Alta completada: %s (%s) plan=%s", tenant.nombre, tenant.id, tenant.plan)
        return tenant

    def obtener_o_404(self, tenant_id: uuid.UUID) -> Tenant:
        tenant = self.repo.obtener_por_id(tenant_id)
        if tenant is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Tenant '{tenant_id}' no encontrado.")
        return tenant

    def listar_activos(self, limit: int = 100) -> list[Tenant]:
        return self.repo.listar(solo_activos=True, limit=limit)

    def actualizar(self, tenant_id: uuid.UUID, data: TenantUpdate) -> Tenant:
        if data.umbral_hitl is not None and data.umbral_hotl is not None:
            if data.umbral_hitl <= data.umbral_hotl:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    "umbral_hitl debe ser mayor que umbral_hotl.",
                )
        tenant = self.repo.actualizar(tenant_id, data)
        if tenant is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Tenant '{tenant_id}' no encontrado.")
        logger.info("[Tenant] Actualizado: %s", tenant_id)
        return tenant

    def desactivar(self, tenant_id: uuid.UUID) -> None:
        if not self.repo.desactivar(tenant_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Tenant '{tenant_id}' no encontrado.")
        logger.warning("[Tenant] Desactivado: %s", tenant_id)
