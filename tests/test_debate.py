"""
tests/test_debate.py
=======================
Mockea _invoke_claude — no llama a Bedrock real. Verifica el CONTROL DE
FLUJO del guardrail (RN-ORQ-003), no la calidad del razonamiento del LLM
(eso se valida manualmente contra Bedrock real, fuera de CI).
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.modules.orquestador import debate
from src.modules.orquestador.contexto_regulatorio import (
    SECTORES_DISPONIBLES,
    construir_contexto_regulatorio,
)
from src.modules.orquestador.schemas_debate import (
    DebateRequest,
    ResultadoAuditoriaEstructurado,
    RiesgoEncontrado,
)


def _decisor_response(contenido="Usar Fargate con autoscaling", justificacion="Costo variable, sin servidores fijos"):
    return json.dumps({"contenido": contenido, "justificacion": justificacion})


def _auditor_response(estado="Aprobado", riesgos=None):
    return json.dumps({
        "resumen_auditoria": "Evaluación de prueba",
        "riesgos_encontrados": riesgos or [],
        "estado_auditoria": estado,
    })


class TestGuardrailReintentos:
    """RN-ORQ-003: nunca se ejecuta sin aprobación solo por agotar intentos."""

    def test_TC_DEB_001_aprobado_en_primer_intento_no_escala(self):
        with patch("src.modules.orquestador.debate._invoke_claude") as mock_llm:
            mock_llm.side_effect = [_decisor_response(), _auditor_response(estado="Aprobado")]
            resultado = debate.ejecutar_debate(DebateRequest(problema="¿Cómo desplegar el worker?"))

        assert resultado.escalado_a_humano is False
        assert resultado.intentos_usados == 1

    def test_TC_DEB_002_agota_intentos_sin_aprobar_escala_a_hitl(self):
        riesgo = [{"categoria": "Seguridad", "severidad": "Alta", "descripcion": "x", "accion_mitigacion": "y"}]
        with patch("src.modules.orquestador.debate._invoke_claude") as mock_llm:
            mock_llm.side_effect = [
                _decisor_response(),                                    # propuesta v1
                _auditor_response(estado="Requiere Cambios", riesgos=riesgo),  # intento 1
                _decisor_response(contenido="v2"),                       # refinamiento
                _auditor_response(estado="Requiere Cambios", riesgos=riesgo),  # intento 2
                _decisor_response(contenido="v3"),                       # refinamiento
                _auditor_response(estado="Requiere Cambios", riesgos=riesgo),  # intento 3 (último)
            ]
            resultado = debate.ejecutar_debate(
                DebateRequest(problema="Conectar app directo a RDS", max_intentos=3)
            )

        assert resultado.escalado_a_humano is True
        assert resultado.intentos_usados == 3
        # Nunca se marca como aprobado solo por agotar intentos:
        assert resultado.auditoria_final.estado_auditoria != "Aprobado"

    def test_TC_DEB_003_aprueba_en_el_segundo_intento_no_agota_el_tercero(self):
        riesgo = [{"categoria": "Costo", "severidad": "Media", "descripcion": "x", "accion_mitigacion": "y"}]
        with patch("src.modules.orquestador.debate._invoke_claude") as mock_llm:
            mock_llm.side_effect = [
                _decisor_response(),
                _auditor_response(estado="Requiere Cambios", riesgos=riesgo),
                _decisor_response(contenido="v2 con Fargate"),
                _auditor_response(estado="Aprobado"),
            ]
            resultado = debate.ejecutar_debate(DebateRequest(problema="Procesar reportes esporádicos", max_intentos=3))

        assert resultado.escalado_a_humano is False
        assert resultado.intentos_usados == 2
        assert len(resultado.historial) == 2


class TestValidacionEstrictaAuditor:
    """El Auditor DEBE devolver el esquema exacto — no texto libre parseado laxamente."""

    def test_TC_DEB_004_json_malformado_del_auditor_lanza_error_no_pasa_silencioso(self):
        with patch("src.modules.orquestador.debate._invoke_claude") as mock_llm:
            mock_llm.side_effect = [
                _decisor_response(),
                json.dumps({"resumen_auditoria": "ok", "estado_auditoria": "Tal vez"}),  # severidad inválida
            ]
            with pytest.raises(ValidationError):
                debate.ejecutar_debate(DebateRequest(problema="x"))

    def test_TC_DEB_005_severidad_fuera_del_enum_es_rechazada_por_pydantic(self):
        with pytest.raises(ValidationError):
            RiesgoEncontrado(categoria="Seguridad", severidad="Extrema", descripcion="x", accion_mitigacion="y")


class TestContextoRegulatorioReal:
    """El contexto inyectado es real y verificable, no inventado en el momento."""

    def test_TC_DEB_006_todos_los_sectores_disponibles_tienen_contenido_no_vacio(self):
        for sector in SECTORES_DISPONIBLES:
            contexto = construir_contexto_regulatorio([sector])
            assert len(contexto) > 100, f"Sector '{sector}' tiene contexto sospechosamente corto"

    def test_TC_DEB_007_sector_comercio_exterior_referencia_la_reforma_2026(self):
        contexto = construir_contexto_regulatorio(["comercio_exterior"])
        assert "2026" in contexto
        assert "aduanal" in contexto.lower()

    def test_TC_DEB_008_sector_desconocido_no_rompe_el_flujo(self):
        contexto = construir_contexto_regulatorio(["sector_inventado_que_no_existe"])
        assert contexto == ""

    def test_TC_DEB_009_multiples_sectores_se_concatenan(self):
        contexto = construir_contexto_regulatorio(["banca", "retail"])
        assert "CNBV" in contexto
        assert "RETAIL" in contexto.upper()

    def test_TC_DEB_010_contexto_se_inyecta_en_el_system_prompt_del_auditor(self):
        with patch("src.modules.orquestador.debate._invoke_claude") as mock_llm:
            mock_llm.return_value = _decisor_response()
            debate._decisor_proponer("problema", "", ["banca"])
            system_usado = mock_llm.call_args[0][0]

        assert "CNBV" in system_usado
