"""
src/modules/copiloto/service.py
==================================
El Copiloto NO es un agente nuevo con su propio criterio — es una capa
de síntesis que lee KPIs + Hallazgos + Evidencia YA REALES (nunca
inventa cifras) y los traduce a la narrativa de 6 puntos que pidió el
prompt. Reutiliza _invoke_claude de ai_agents.py, no un cliente nuevo.

RN-COP-001: el Copiloto solo puede citar transaction_id que existan de
verdad en la Evidencia consultada — nunca alucina evidencia de soporte.
"""

from __future__ import annotations

import logging

from sqlmodel import Session

from src.modules.auditoria.service import AuditoriaService
from src.modules.copiloto.schemas import ResumenEjecutivo
from src.modules.orquestador.ai_agents import _invoke_claude, _parse_json

logger = logging.getLogger(__name__)

COPILOTO_SYSTEM = """\
Eres el Copiloto Ejecutivo de SMARTPROMARCO. Tu trabajo es traducir \
KPIs y hallazgos de auditoría — datos reales que se te dan, nunca los \
inventas — en una narrativa ejecutiva breve y honesta.

Responde SIEMPRE en JSON con esta estructura exacta:
{
  "que_ocurre": "una frase, lo más relevante ahora mismo",
  "por_que_ocurre": "la causa raíz visible en los datos",
  "impacto": "qué pasa si no se atiende",
  "recomendacion_ia": "una acción concreta y ejecutable",
  "evidencia_relacionada": ["solo transaction_id que aparezcan en los datos que te dieron"],
  "decision_requerida": "qué decidir, o null si no hace falta ninguna",
  "prioridad": "Alta | Media | Baja"
}

Si los datos no muestran nada urgente, dilo — no inventes un problema
para sonar útil. La honestidad importa más que sonar dramático."""


def generar_resumen_ejecutivo(session: Session, tenant_id) -> ResumenEjecutivo:
    auditoria = AuditoriaService(session)
    kpis = auditoria.kpis(tenant_id)
    pendientes = auditoria.listar_pendientes_hitl(tenant_id)

    # IDs reales disponibles — el Copiloto solo puede citar de esta lista
    ids_disponibles = [str(ev.transaction_id) for ev in pendientes[:10]]

    contexto = f"""\
KPIs actuales del tenant:
- Total de transacciones auditadas: {kpis.get('total', 0)}
- Por riesgo: {kpis.get('por_riesgo', {})}
- Por tipo de intervención: {kpis.get('por_loop', {})}
- Transacciones pendientes de decisión humana ahora: {len(pendientes)}

transaction_id disponibles para citar como evidencia (NO inventes otros):
{ids_disponibles or '(ninguna pendiente ahora mismo)'}"""

    raw = _invoke_claude(COPILOTO_SYSTEM, contexto, max_tokens=800, temperature=0.2)
    data = _parse_json(raw)

    resumen = ResumenEjecutivo.model_validate(data)

    # RN-COP-001 aplicado en código, no solo confiado al prompt: si el
    # modelo citó un ID que no estaba en la lista real, se descarta —
    # mejor evidencia vacía que evidencia inventada.
    resumen.evidencia_relacionada = [
        tid for tid in resumen.evidencia_relacionada if tid in ids_disponibles
    ]

    logger.info("[Copiloto] Resumen generado | prioridad=%s | evidencia_citada=%d",
                resumen.prioridad, len(resumen.evidencia_relacionada))
    return resumen
