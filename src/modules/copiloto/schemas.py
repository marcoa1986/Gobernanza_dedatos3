"""
src/modules/copiloto/schemas.py
==================================
Estructura EXACTA de la sección "Experiencia" del prompt: qué ocurre,
por qué, qué impacto, qué recomienda, qué evidencia, qué decisión.
No es un resumen libre — cada campo responde una pregunta específica.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResumenEjecutivo(BaseModel):
    que_ocurre: str = Field(..., description="Qué está pasando ahora mismo, en una frase")
    por_que_ocurre: str = Field(..., description="La causa raíz, no solo el síntoma")
    impacto: str = Field(..., description="Qué pasa si no se atiende")
    recomendacion_ia: str = Field(..., description="Qué acción concreta recomienda el sistema")
    evidencia_relacionada: list[str] = Field(default_factory=list, description="transaction_id de las evidencias que sustentan esta narrativa")
    decision_requerida: str | None = Field(default=None, description="Qué decisión humana se necesita, si alguna — null si no requiere acción")
    prioridad: str = Field(..., pattern="^(Alta|Media|Baja)$")
