"""
tests/test_auditoria.py
=========================
Cubre: RN-EVI-001 (hash inmutable), RN-EVI-002 (integridad verificable),
RN-ORQ-001 (DELETE siempre HITL), RN-ORQ-002 (umbrales por tenant).

Cada test referencia su caso de uso vía el docstring — ver
docs/traceability/matrix.md para el mapeo completo.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from src.modules.auditoria.models import (
    Canal,
    EvidenciaCreate,
    NivelRiesgo,
    Operacion,
    TipoLoop,
)
from src.modules.auditoria.service import (
    AuditoriaService,
    calcular_hash_evidencia,
    determinar_tipo_loop,
    mapear_riesgo,
)
from src.modules.tenants.models import Tenant


def _evidencia_create(tenant: Tenant, **overrides) -> EvidenciaCreate:
    base = dict(
        transaction_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        tenant_id=tenant.id,
        empresa=tenant.nombre,
        canal=Canal.B2B,
        operacion=Operacion.POST,
        payload_original={"producto_id": "PROD-001", "cantidad": 10},
        esquema_pydantic="v2.0",
        validacion="PASS",
        riesgo=NivelRiesgo.BAJO,
        agente_auditor={"risk_score": 0.1, "razonamiento": "Sin anomalías"},
        explicacion="Sin anomalías",
        tipo_loop=TipoLoop.HOOTL,
        operador=None,
        decision="aprobar",
        agente_decisor=None,
        resultado_ejecucion=None,
    )
    base.update(overrides)
    return EvidenciaCreate(**base)


class TestHashInmutable:
    """RN-EVI-001: la Evidencia lleva un hash SHA-256 verificable."""

    def test_TC_AUD_001_hash_es_determinista(self):
        """El mismo contenido siempre produce el mismo hash, sin importar el orden de las claves."""
        datos_a = {"b": 2, "a": 1, "c": {"z": 1, "y": 2}}
        datos_b = {"a": 1, "c": {"y": 2, "z": 1}, "b": 2}
        assert calcular_hash_evidencia(datos_a) == calcular_hash_evidencia(datos_b)

    def test_TC_AUD_002_hash_cambia_si_cambia_el_contenido(self):
        h1 = calcular_hash_evidencia({"cantidad": 10})
        h2 = calcular_hash_evidencia({"cantidad": 11})
        assert h1 != h2

    def test_TC_AUD_003_hash_tiene_formato_sha256(self):
        h = calcular_hash_evidencia({"x": 1})
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestIntegridadEvidencia:
    """RN-EVI-002: el Auditor Interno debe poder detectar manipulación (ciclo paso 5)."""

    def test_TC_AUD_004_evidencia_intacta_verifica_ok(self, session: Session, tenant_demo: Tenant):
        service = AuditoriaService(session)
        evidencia = service.registrar_evidencia(_evidencia_create(tenant_demo))

        assert service.verificar_integridad(evidencia.transaction_id) is True

    def test_TC_AUD_005_evidencia_manipulada_falla_verificacion(self, session: Session, tenant_demo: Tenant):
        service = AuditoriaService(session)
        evidencia = service.registrar_evidencia(_evidencia_create(tenant_demo))

        # Simula manipulación directa en BD (bypass del Service, como haría un atacante)
        evidencia.payload_original = {"producto_id": "PROD-001", "cantidad": 99999}
        session.add(evidencia)
        session.commit()

        assert service.verificar_integridad(evidencia.transaction_id) is False


class TestDeterminacionDeLoop:
    """RN-ORQ-001 y RN-ORQ-002."""

    def test_TC_AUD_006_delete_siempre_es_hitl_sin_importar_riesgo_bajo(self):
        resultado = determinar_tipo_loop(
            risk_score=0.01, operacion=Operacion.DELETE, umbral_hitl=0.80, umbral_hotl=0.50,
        )
        assert resultado == TipoLoop.HITL

    def test_TC_AUD_007_riesgo_sobre_umbral_hitl_es_hitl(self):
        resultado = determinar_tipo_loop(
            risk_score=0.85, operacion=Operacion.POST, umbral_hitl=0.80, umbral_hotl=0.50,
        )
        assert resultado == TipoLoop.HITL

    def test_TC_AUD_008_riesgo_medio_es_hotl(self):
        resultado = determinar_tipo_loop(
            risk_score=0.60, operacion=Operacion.PUT, umbral_hitl=0.80, umbral_hotl=0.50,
        )
        assert resultado == TipoLoop.HOTL

    def test_TC_AUD_009_riesgo_bajo_es_hootl(self):
        resultado = determinar_tipo_loop(
            risk_score=0.10, operacion=Operacion.POST, umbral_hitl=0.80, umbral_hotl=0.50,
        )
        assert resultado == TipoLoop.HOOTL

    def test_TC_AUD_010_umbrales_por_tenant_cambian_la_clasificacion(self):
        """Un tenant más conservador (umbral_hitl=0.30) escala a HITL lo que otro trataría como HOOTL."""
        conservador = determinar_tipo_loop(0.35, Operacion.POST, umbral_hitl=0.30, umbral_hotl=0.20)
        estandar = determinar_tipo_loop(0.35, Operacion.POST, umbral_hitl=0.80, umbral_hotl=0.50)
        assert conservador == TipoLoop.HITL
        assert estandar == TipoLoop.HOOTL


class TestMapeoRiesgo:
    def test_TC_AUD_011_mapeo_riesgo_alto(self):
        assert mapear_riesgo(0.75) == NivelRiesgo.ALTO

    def test_TC_AUD_012_mapeo_riesgo_medio(self):
        assert mapear_riesgo(0.45) == NivelRiesgo.MEDIO

    def test_TC_AUD_013_mapeo_riesgo_bajo(self):
        assert mapear_riesgo(0.10) == NivelRiesgo.BAJO


class TestEvidenciaKPIs:
    def test_TC_AUD_014_kpis_cuentan_por_riesgo_y_loop(self, session: Session, tenant_demo: Tenant):
        service = AuditoriaService(session)
        service.registrar_evidencia(_evidencia_create(tenant_demo, riesgo=NivelRiesgo.ALTO, tipo_loop=TipoLoop.HITL))
        service.registrar_evidencia(_evidencia_create(tenant_demo, riesgo=NivelRiesgo.BAJO, tipo_loop=TipoLoop.HOOTL))
        service.registrar_evidencia(_evidencia_create(tenant_demo, riesgo=NivelRiesgo.BAJO, tipo_loop=TipoLoop.HOOTL))

        kpis = service.kpis(tenant_demo.id)
        assert kpis["total"] == 3
        assert kpis["por_riesgo"]["Bajo"] == 2
        assert kpis["por_riesgo"]["Alto"] == 1
        assert kpis["por_loop"]["HOOTL"] == 2


class TestTransicionHITL:
    """RN-EVI-003: la única mutación permitida — pendiente → resuelto, hash recalculado."""

    def test_TC_AUD_015_completar_decision_cierra_evidencia_pendiente(self, session: Session, tenant_demo: Tenant):
        service = AuditoriaService(session)
        pendiente = service.registrar_evidencia(_evidencia_create(
            tenant_demo, tipo_loop=TipoLoop.HITL, decision=None, operador=None,
        ))
        hash_original = pendiente.hash

        resuelta = service.completar_decision_hitl(
            pendiente.transaction_id, decision="aprobar", operador="usr_marco",
            resultado_ejecucion={"filas_afectadas": 1},
        )

        assert resuelta.decision.value == "aprobar"
        assert resuelta.operador == "usr_marco"
        assert resuelta.hash != hash_original  # el contenido cambió → el hash DEBE cambiar
        assert service.verificar_integridad(pendiente.transaction_id) is True

    def test_TC_AUD_016_no_se_puede_resolver_dos_veces(self, session: Session, tenant_demo: Tenant):
        service = AuditoriaService(session)
        pendiente = service.registrar_evidencia(_evidencia_create(
            tenant_demo, tipo_loop=TipoLoop.HITL, decision=None, operador=None,
        ))
        service.completar_decision_hitl(pendiente.transaction_id, "aprobar", "usr_marco")

        with pytest.raises(HTTPException) as exc:
            service.completar_decision_hitl(pendiente.transaction_id, "rechazar", "usr_otro")
        assert exc.value.status_code == 409

    def test_TC_AUD_017_listar_pendientes_hitl_excluye_resueltas(self, session: Session, tenant_demo: Tenant):
        service = AuditoriaService(session)
        p1 = service.registrar_evidencia(_evidencia_create(tenant_demo, tipo_loop=TipoLoop.HITL, decision=None, operador=None))
        service.registrar_evidencia(_evidencia_create(tenant_demo, tipo_loop=TipoLoop.HITL, decision=None, operador=None))
        service.completar_decision_hitl(p1.transaction_id, "aprobar", "usr_marco")

        pendientes = service.listar_pendientes_hitl(tenant_demo.id)
        assert len(pendientes) == 1
        assert pendientes[0].transaction_id != p1.transaction_id
