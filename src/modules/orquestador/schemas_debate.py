"""
src/modules/orquestador/schemas_debate.py
============================================
Esquema Pydantic ESTRICTO para el Auditor — exactamente como se pidió:
JSON validado, no texto libre parseado con regex. Esto es lo que hace
posible interceptar la decisión sin depender de parsing frágil.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

Severidad = Literal["Alta", "Media", "Baja"]
EstadoAuditoria = Literal["Aprobado", "Requiere Cambios", "Rechazado"]


class RiesgoEncontrado(BaseModel):
    categoria: str = Field(..., description="Ej. Seguridad, Arquitectura, Rendimiento, Costo")
    severidad: Severidad
    descripcion: str = Field(..., description="Qué falla o vulnerabilidad encontró")
    accion_mitigacion: str = Field(..., description="Qué le exige al Decisor que cambie")


class ResultadoAuditoriaEstructurado(BaseModel):
    """Lo que el Auditor DEBE devolver — validado, no negociable."""
    resumen_auditoria: str
    riesgos_encontrados: list[RiesgoEncontrado] = Field(default_factory=list)
    estado_auditoria: EstadoAuditoria


class PropuestaDecisor(BaseModel):
    contenido: str = Field(..., description="La propuesta, decisión o plan de acción del Decisor")
    justificacion: str = Field(default="", description="Por qué el Decisor eligió este enfoque")
    version: int = Field(default=1, ge=1, description="Número de iteración dentro del debate")


class TurnoDebate(BaseModel):
    intento: int
    propuesta: PropuestaDecisor
    auditoria: ResultadoAuditoriaEstructurado


class ResultadoDebate(BaseModel):
    """Lo que devuelve ejecutar_debate() — el contrato completo con el caller."""
    problema: str
    propuesta_final: PropuestaDecisor
    auditoria_final: ResultadoAuditoriaEstructurado
    intentos_usados: int
    escalado_a_humano: bool = Field(
        description="RN-ORQ-003: True si se agotaron los intentos sin llegar a 'Aprobado' — "
                     "requiere revisión humana obligatoria (HITL), no una simple advertencia."
    )
    historial: list[TurnoDebate] = Field(default_factory=list)
    completado_en: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DebateRequest(BaseModel):
    problema: str = Field(..., min_length=1, description="El problema, requerimiento o propuesta a evaluar")
    contexto: str = Field(default="", description="Contexto adicional: stack, restricciones, historial")
    max_intentos: int = Field(default=3, ge=1, le=5)
