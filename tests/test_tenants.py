"""
tests/test_tenants.py
=======================
Cubre RN-TEN-001 (umbral_hitl > umbral_hotl) y RN-TEN-002 (plan válido).
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from src.modules.tenants.models import TenantCreate
from src.modules.tenants.service import TenantService


class TestAltaTenant:
    def test_TC_TEN_001_alta_exitosa_con_datos_validos(self, session: Session):
        service = TenantService(session)
        tenant = service.alta_tenant(TenantCreate(
            nombre="QA-Servicio Demo", rfc="QSD900101XYZ",
            plan="professional", umbral_hitl=0.80, umbral_hotl=0.50,
        ))
        assert tenant.id is not None
        assert tenant.activo is True

    def test_TC_TEN_002_rechaza_plan_invalido(self, session: Session):
        """RN-TEN-002: el plan debe ser starter | professional | enterprise."""
        service = TenantService(session)
        with pytest.raises(HTTPException) as exc:
            service.alta_tenant(TenantCreate(nombre="X", plan="platino"))
        assert exc.value.status_code == 422

    def test_TC_TEN_003_rechaza_umbral_hitl_menor_o_igual_a_hotl(self, session: Session):
        """RN-TEN-001: HITL es el riesgo más alto, su umbral debe ser mayor que HOTL."""
        service = TenantService(session)
        with pytest.raises(HTTPException) as exc:
            service.alta_tenant(TenantCreate(nombre="X", umbral_hitl=0.40, umbral_hotl=0.60))
        assert exc.value.status_code == 422

    def test_TC_TEN_004_rechaza_rfc_duplicado(self, session: Session):
        service = TenantService(session)
        service.alta_tenant(TenantCreate(nombre="Empresa A", rfc="DUP900101ABC"))
        with pytest.raises(HTTPException) as exc:
            service.alta_tenant(TenantCreate(nombre="Empresa B", rfc="DUP900101ABC"))
        assert exc.value.status_code == 409

    def test_TC_TEN_005_desactivar_es_soft_delete(self, session: Session):
        service = TenantService(session)
        tenant = service.alta_tenant(TenantCreate(nombre="Empresa C"))
        service.desactivar(tenant.id)

        recargado = service.obtener_o_404(tenant.id)
        assert recargado.activo is False
        assert recargado.id == tenant.id  # sigue existiendo — no se borró
