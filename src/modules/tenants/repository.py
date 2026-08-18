"""
src/modules/tenants/repository.py
===================================
Repository Pattern: única capa que toca SQL. El Service nunca
importa `select()` directamente — siempre pasa por aquí.
"""

from __future__ import annotations

import uuid

from sqlmodel import Session, select

from src.modules.tenants.models import Tenant, TenantCreate, TenantUpdate


class TenantRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, data: TenantCreate) -> Tenant:
        tenant = Tenant.model_validate(data)
        self.session.add(tenant)
        self.session.commit()
        self.session.refresh(tenant)
        return tenant

    def obtener_por_id(self, tenant_id: uuid.UUID) -> Tenant | None:
        return self.session.get(Tenant, tenant_id)

    def obtener_por_rfc(self, rfc: str) -> Tenant | None:
        return self.session.exec(select(Tenant).where(Tenant.rfc == rfc)).first()

    def listar(self, solo_activos: bool = True, limit: int = 100) -> list[Tenant]:
        query = select(Tenant)
        if solo_activos:
            query = query.where(Tenant.activo == True)  # noqa: E712
        return list(self.session.exec(query.limit(limit)).all())

    def actualizar(self, tenant_id: uuid.UUID, data: TenantUpdate) -> Tenant | None:
        tenant = self.obtener_por_id(tenant_id)
        if tenant is None:
            return None
        updates = data.model_dump(exclude_unset=True)
        for campo, valor in updates.items():
            setattr(tenant, campo, valor)
        self.session.add(tenant)
        self.session.commit()
        self.session.refresh(tenant)
        return tenant

    def desactivar(self, tenant_id: uuid.UUID) -> bool:
        """Soft delete — nunca borramos un tenant físicamente (hay evidencia ligada)."""
        tenant = self.obtener_por_id(tenant_id)
        if tenant is None:
            return False
        tenant.activo = False
        self.session.add(tenant)
        self.session.commit()
        return True
