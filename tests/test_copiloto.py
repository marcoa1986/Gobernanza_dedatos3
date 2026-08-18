"""
tests/test_copiloto.py
=========================
Mockea _invoke_claude. Lo crítico a probar no es "qué tan bien escribe
Claude" (eso no es testeable con mocks) — es que RN-COP-001 se cumple
en código: el Copiloto nunca puede colar un transaction_id que no
exista de verdad en los datos que se le dieron.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import patch

from sqlmodel import Session

from src.modules.auditoria.models import Canal, EvidenciaCreate, NivelRiesgo, Operacion, TipoLoop
from src.modules.auditoria.service import AuditoriaService
from src.modules.copiloto.service import generar_resumen_ejecutivo
from src.modules.tenants.models import Tenant


def _evidencia_pendiente(tenant: Tenant):
    return EvidenciaCreate(
        transaction_id=uuid.uuid4(), thread_id=uuid.uuid4(), tenant_id=tenant.id,
        empresa=tenant.nombre, canal=Canal.B2B, operacion=Operacion.DELETE,
        payload_original={"sku": "SPM-001"}, esquema_pydantic="v2.0", validacion="PASS",
        riesgo=NivelRiesgo.ALTO, agente_auditor={"risk_score": 0.9}, explicacion="DELETE de alto riesgo",
        tipo_loop=TipoLoop.HITL, operador=None, decision=None, agente_decisor=None, resultado_ejecucion=None,
    )


def _respuesta_llm(evidencia_citada: list[str], prioridad="Alta"):
    return json.dumps({
        "que_ocurre": "Hay una transacción DELETE de alto riesgo pendiente",
        "por_que_ocurre": "El producto no tiene historial de auditoría previo",
        "impacto": "Pérdida de datos si se aprueba sin revisión",
        "recomendacion_ia": "Revisar el historial del producto antes de aprobar",
        "evidencia_relacionada": evidencia_citada,
        "decision_requerida": "Aprobar o rechazar el DELETE",
        "prioridad": prioridad,
    })


class TestRNCOP001NoAlucinaEvidencia:
    """La regla que más importa: nunca citar un transaction_id que no exista de verdad."""

    def test_TC_COP_001_cita_evidencia_real_correctamente(self, session: Session, tenant_demo: Tenant):
        service = AuditoriaService(session)
        ev = service.registrar_evidencia(_evidencia_pendiente(tenant_demo))

        with patch("src.modules.copiloto.service._invoke_claude") as mock_llm:
            mock_llm.return_value = _respuesta_llm([str(ev.transaction_id)])
            resumen = generar_resumen_ejecutivo(session, tenant_demo.id)

        assert str(ev.transaction_id) in resumen.evidencia_relacionada

    def test_TC_COP_002_descarta_transaction_id_inventado(self, session: Session, tenant_demo: Tenant):
        """Si el LLM alucina un ID que no está en los datos reales, el código lo filtra — no confía ciegamente en el prompt."""
        service = AuditoriaService(session)
        service.registrar_evidencia(_evidencia_pendiente(tenant_demo))

        id_inventado = str(uuid.uuid4())  # no corresponde a ninguna evidencia real
        with patch("src.modules.copiloto.service._invoke_claude") as mock_llm:
            mock_llm.return_value = _respuesta_llm([id_inventado])
            resumen = generar_resumen_ejecutivo(session, tenant_demo.id)

        assert id_inventado not in resumen.evidencia_relacionada
        assert resumen.evidencia_relacionada == []

    def test_TC_COP_003_sin_pendientes_no_hay_ids_disponibles_para_citar(self, session: Session, tenant_demo: Tenant):
        with patch("src.modules.copiloto.service._invoke_claude") as mock_llm:
            mock_llm.return_value = _respuesta_llm([str(uuid.uuid4())])  # el LLM igual intenta citar algo
            resumen = generar_resumen_ejecutivo(session, tenant_demo.id)

        assert resumen.evidencia_relacionada == []  # se descarta — no había nada real que citar


class TestEstructuraDeLosSeisPuntos:
    """La narrativa exacta que pidió el prompt — no un resumen libre."""

    def test_TC_COP_004_responde_las_6_preguntas_exactas(self, session: Session, tenant_demo: Tenant):
        with patch("src.modules.copiloto.service._invoke_claude") as mock_llm:
            mock_llm.return_value = _respuesta_llm([])
            resumen = generar_resumen_ejecutivo(session, tenant_demo.id)

        assert resumen.que_ocurre
        assert resumen.por_que_ocurre
        assert resumen.impacto
        assert resumen.recomendacion_ia
        assert resumen.decision_requerida
        assert resumen.prioridad in ("Alta", "Media", "Baja")

    def test_TC_COP_005_prioridad_fuera_del_enum_falla_validacion(self, session: Session, tenant_demo: Tenant):
        import pytest
        from pydantic import ValidationError
        with patch("src.modules.copiloto.service._invoke_claude") as mock_llm:
            mock_llm.return_value = _respuesta_llm([], prioridad="Urgentísima")
            with pytest.raises(ValidationError):
                generar_resumen_ejecutivo(session, tenant_demo.id)
