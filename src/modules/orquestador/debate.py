"""
src/modules/orquestador/debate.py
====================================
Patrón Decisor vs. Auditor — general, reusable para CUALQUIER propuesta
(arquitectura, negocio, código), no solo para transacciones CRUD.
Complementa (no reemplaza) el flujo de auditoría de transacciones que
ya vive en ai_agents.py — comparten el mismo cliente de Bedrock.

RN-ORQ-003 (Guardrail de reintentos): si en `max_intentos` iteraciones
el Decisor no logra que el Auditor apruebe, la ejecución se PAUSA y se
escala a HITL — nunca se ejecuta una propuesta "Requiere Cambios" o
"Rechazado" solo porque se acabaron los intentos.

RN-ORQ-004 (Criterios finitos + contexto regulatorio real): el Auditor
evalúa contra un set acotado de categorías técnicas, MÁS el contexto
regulatorio real del sector (ver contexto_regulatorio.py) cuando aplica
— evita que se vuelva tan exigente que rechace propuestas válidas por
criterios no acotados, y evita que audite en el vacío cuando el sector
sí importa (banca, comercio exterior, retail).
"""

from __future__ import annotations

import logging

from src.modules.orquestador.ai_agents import _invoke_claude, _parse_json
from src.modules.orquestador.contexto_regulatorio import construir_contexto_regulatorio
from src.modules.orquestador.schemas_debate import (
    DebateRequest,
    PropuestaDecisor,
    ResultadoAuditoriaEstructurado,
    ResultadoDebate,
    TurnoDebate,
)

logger = logging.getLogger(__name__)

MAX_INTENTOS_DEFAULT = 3

# ══════════════════════════════════════════════════════════════
# SYSTEM PROMPTS — el rol exacto que se pidió, con contexto sectorial inyectable
# ══════════════════════════════════════════════════════════════

DECISOR_SYSTEM_BASE = """\
Eres el Decisor. Tu objetivo es tomar problemas o requerimientos, \
evaluarlos y definir un plan de acción claro, estructurado y ejecutable. \
Tienes la autoridad para tomar decisiones de arquitectura, negocio o código. \
Cuando el Auditor señale riesgos o fallas en tus decisiones, evalúa sus \
argumentos objetivamente y refina la decisión final justificando cada ajuste.

RESPONDE ÚNICAMENTE EN JSON:
{
  "contenido": "tu propuesta o decisión, completa y ejecutable",
  "justificacion": "por qué elegiste este enfoque, o qué ajustaste y por qué"
}"""

AUDITOR_SYSTEM_BASE = """\
Eres el Auditor. Tu único objetivo es auditar minuciosamente las \
propuestas y decisiones presentadas por el Decisor. Debes buscar: \
vulnerabilidades de seguridad, cuellos de botella de rendimiento, costos \
ocultos, falta de escalabilidad, casos de borde (edge cases) y vacíos \
lógicos. Tu tono debe ser directo, técnico y sin concesiones. No tomas \
las decisiones, solo las auditas.

Limita tu crítica a estas 4 categorías técnicas — Seguridad, Arquitectura, \
Rendimiento, Costo — MÁS el cumplimiento normativo del sector cuando se \
te proporcione contexto regulatorio explícito (ver más abajo). No inventes \
criterios fuera de estas categorías: una propuesta técnicamente válida no \
debe rechazarse por preferencias de estilo.

RESPONDE ÚNICAMENTE EN JSON, con esta estructura exacta:
{
  "resumen_auditoria": "breve texto de la evaluación general",
  "riesgos_encontrados": [
    {
      "categoria": "Seguridad | Arquitectura | Rendimiento | Costo | Cumplimiento Normativo",
      "severidad": "Alta | Media | Baja",
      "descripcion": "qué falla o vulnerabilidad encontraste",
      "accion_mitigacion": "qué le exiges al Decisor que cambie"
    }
  ],
  "estado_auditoria": "Aprobado | Requiere Cambios | Rechazado"
}
Si no encuentras riesgos, "riesgos_encontrados" es una lista vacía y
"estado_auditoria" es "Aprobado"."""


def _con_contexto(system_base: str, sectores: list[str] | None) -> str:
    """Inyecta el contexto regulatorio real del/los sector(es) indicado(s), si aplica."""
    if not sectores:
        return system_base
    contexto = construir_contexto_regulatorio(sectores)
    return f"{system_base}\n\nCONTEXTO REGULATORIO REAL APLICABLE (úsalo para fundamentar tu evaluación,\nno lo inventes ni lo ignores):\n{contexto}"


# ══════════════════════════════════════════════════════════════
# LLAMADAS INDIVIDUALES (separadas del loop para poder mockearlas en tests)
# ══════════════════════════════════════════════════════════════

def _decisor_proponer(problema: str, contexto: str, sectores: list[str] | None) -> PropuestaDecisor:
    system = _con_contexto(DECISOR_SYSTEM_BASE, sectores)
    user_msg = f"Problema o requerimiento:\n{problema}\n\nContexto:\n{contexto or '(sin contexto adicional)'}"
    raw = _invoke_claude(system, user_msg, max_tokens=1200, temperature=0.3)
    data = _parse_json(raw)
    return PropuestaDecisor(contenido=data["contenido"], justificacion=data.get("justificacion", ""), version=1)


def _decisor_refinar(
    propuesta_previa: PropuestaDecisor, auditoria: ResultadoAuditoriaEstructurado,
    problema: str, sectores: list[str] | None,
) -> PropuestaDecisor:
    system = _con_contexto(DECISOR_SYSTEM_BASE, sectores)
    riesgos_texto = "\n".join(
        f"- [{r.severidad}/{r.categoria}] {r.descripcion} → exige: {r.accion_mitigacion}"
        for r in auditoria.riesgos_encontrados
    )
    user_msg = f"""\
Problema original:
{problema}

Tu propuesta anterior (versión {propuesta_previa.version}):
{propuesta_previa.contenido}

El Auditor respondió "{auditoria.estado_auditoria}" con estos riesgos:
{riesgos_texto or '(sin riesgos detallados)'}

Resumen del auditor: {auditoria.resumen_auditoria}

Refina tu decisión atendiendo CADA riesgo señalado. Justifica cada ajuste."""

    raw = _invoke_claude(system, user_msg, max_tokens=1200, temperature=0.3)
    data = _parse_json(raw)
    return PropuestaDecisor(
        contenido=data["contenido"], justificacion=data.get("justificacion", ""),
        version=propuesta_previa.version + 1,
    )


def _auditor_auditar(
    propuesta: PropuestaDecisor, problema: str, sectores: list[str] | None,
) -> ResultadoAuditoriaEstructurado:
    system = _con_contexto(AUDITOR_SYSTEM_BASE, sectores)
    user_msg = f"""\
Problema original:
{problema}

Propuesta del Decisor (versión {propuesta.version}):
{propuesta.contenido}

Justificación del Decisor:
{propuesta.justificacion}

Audita esta propuesta."""

    raw = _invoke_claude(system, user_msg, max_tokens=1200, temperature=0.1)
    data = _parse_json(raw)
    # Validación ESTRICTA — si Claude no respeta el esquema, esto lanza
    # ValidationError en vez de dejar pasar un JSON malformado silenciosamente.
    return ResultadoAuditoriaEstructurado.model_validate(data)


# ══════════════════════════════════════════════════════════════
# EL LOOP — con guardrail de reintentos (RN-ORQ-003)
# ══════════════════════════════════════════════════════════════

def ejecutar_debate(request: DebateRequest, sectores: list[str] | None = None) -> ResultadoDebate:
    """
    Orquesta el ciclo Decisor → Auditor → (refinar | aprobar | escalar).
    `sectores` (ej. ["comercio_exterior", "banca"]) inyecta contexto
    regulatorio real — ver contexto_regulatorio.py para las claves válidas.
    Nunca ejecuta una propuesta no aprobada solo porque se acabaron los
    intentos — ese es exactamente el punto del guardrail.
    """
    logger.info("[Debate] Iniciando | max_intentos=%s | sectores=%s", request.max_intentos, sectores)

    propuesta = _decisor_proponer(request.problema, request.contexto, sectores)
    historial: list[TurnoDebate] = []
    auditoria: ResultadoAuditoriaEstructurado

    for intento in range(1, request.max_intentos + 1):
        auditoria = _auditor_auditar(propuesta, request.problema, sectores)
        historial.append(TurnoDebate(intento=intento, propuesta=propuesta, auditoria=auditoria))
        logger.info(
            "[Debate] Intento %d/%d | estado=%s | riesgos=%d",
            intento, request.max_intentos, auditoria.estado_auditoria, len(auditoria.riesgos_encontrados),
        )

        if auditoria.estado_auditoria == "Aprobado":
            return ResultadoDebate(
                problema=request.problema, propuesta_final=propuesta, auditoria_final=auditoria,
                intentos_usados=intento, escalado_a_humano=False, historial=historial,
            )

        if intento < request.max_intentos:
            propuesta = _decisor_refinar(propuesta, auditoria, request.problema, sectores)

    # Guardrail: se agotaron los intentos sin "Aprobado" → HITL obligatorio.
    logger.warning(
        "[Debate] Guardrail activado: %d intentos agotados sin aprobación — escalando a HITL",
        request.max_intentos,
    )
    return ResultadoDebate(
        problema=request.problema, propuesta_final=propuesta, auditoria_final=auditoria,
        intentos_usados=request.max_intentos, escalado_a_humano=True, historial=historial,
    )
