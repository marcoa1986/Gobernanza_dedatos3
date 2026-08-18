"""
src/modules/auditoria/service.py
==================================
Lógica de negocio de auditoría: cálculo de hash inmutable,
determinación de tipo de loop (HITL/HOTL/HOOTL), mapeo de riesgo.
Esta es la misma lógica que vivía en orchestrator.py — se mueve aquí
porque es responsabilidad del dominio "auditoria", no del orquestador
(el orquestador la INVOCA, no la posee).
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlmodel import Session

from src.modules.auditoria.models import (
    Evidencia,
    EvidenciaCreate,
    HallazgoAuditoria,
    HallazgoAuditoriaCreate,
    MatrizTrazabilidad,
    MatrizTrazabilidadCreate,
    NivelRiesgo,
    Operacion,
    TipoLoop,
)
from src.modules.auditoria.repository import (
    EvidenciaRepository,
    HallazgoRepository,
    TrazabilidadRepository,
)

logger = logging.getLogger(__name__)


def calcular_hash_evidencia(datos: dict) -> str:
    """
    SHA-256 de la serialización canónica (sort_keys=True) — el mismo
    contenido siempre produce el mismo hash, sin importar el orden
    en que se construyó el diccionario en memoria.
    """
    canonical = json.dumps(datos, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def determinar_tipo_loop(risk_score: float, operacion: Operacion, umbral_hitl: float, umbral_hotl: float) -> TipoLoop:
    """DELETE siempre requiere humano — sin excepción, sin importar el risk_score."""
    if operacion == Operacion.DELETE:
        return TipoLoop.HITL
    if risk_score >= umbral_hitl:
        return TipoLoop.HITL
    if risk_score >= umbral_hotl:
        return TipoLoop.HOTL
    return TipoLoop.HOOTL


def mapear_riesgo(risk_score: float) -> NivelRiesgo:
    if risk_score >= 0.70:
        return NivelRiesgo.ALTO
    if risk_score >= 0.40:
        return NivelRiesgo.MEDIO
    return NivelRiesgo.BAJO


class AuditoriaService:
    def __init__(self, session: Session):
        self.evidencia_repo = EvidenciaRepository(session)
        self.trazabilidad_repo = TrazabilidadRepository(session)
        self.hallazgo_repo = HallazgoRepository(session)

    def registrar_evidencia(self, data: EvidenciaCreate) -> Evidencia:
        """
        Punto único de escritura de Evidencia. Calcula el hash sobre
        TODOS los campos antes de persistir — así el hash certifica
        el contenido completo, no solo una parte.
        """
        campos_para_hash = data.model_dump(mode="json")
        hash_valor = calcular_hash_evidencia(campos_para_hash)

        evidencia = self.evidencia_repo.crear(data, hash_valor)
        logger.info(
            "[Evidencia] Registrada TXN=%s hash=%s… riesgo=%s loop=%s",
            evidencia.transaction_id, hash_valor[:12], evidencia.riesgo, evidencia.tipo_loop,
        )
        return evidencia

    def verificar_integridad(self, transaction_id: uuid.UUID) -> bool:
        """
        Recalcula el hash a partir del contenido almacenado y lo compara
        contra el hash guardado — así el Auditor Interno (paso 5 del
        ciclo: "Consultar Evidencias") puede detectar manipulación.
        """
        evidencia = self.evidencia_repo.obtener_por_transaction_id(transaction_id)
        if evidencia is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Evidencia '{transaction_id}' no encontrada.")

        campos = {
            "transaction_id": str(evidencia.transaction_id),
            "thread_id": str(evidencia.thread_id),
            "tenant_id": str(evidencia.tenant_id),
            "empresa": evidencia.empresa,
            "canal": evidencia.canal.value,
            "operacion": evidencia.operacion.value,
            "payload_original": evidencia.payload_original,
            "esquema_pydantic": evidencia.esquema_pydantic,
            "validacion": evidencia.validacion.value,
            "riesgo": evidencia.riesgo.value,
            "agente_auditor": evidencia.agente_auditor,
            "explicacion": evidencia.explicacion,
            "tipo_loop": evidencia.tipo_loop.value,
            "operador": evidencia.operador,
            "decision": evidencia.decision.value if evidencia.decision else None,
            "agente_decisor": evidencia.agente_decisor,
            "resultado_ejecucion": evidencia.resultado_ejecucion,
        }
        hash_recalculado = calcular_hash_evidencia(campos)
        integra = hash_recalculado == evidencia.hash
        if not integra:
            logger.critical(
                "[INTEGRIDAD] ¡Hash no coincide! TXN=%s esperado=%s recalculado=%s",
                transaction_id, evidencia.hash[:12], hash_recalculado[:12],
            )
        return integra

    def obtener_o_404(self, transaction_id: uuid.UUID) -> Evidencia:
        evidencia = self.evidencia_repo.obtener_por_transaction_id(transaction_id)
        if evidencia is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Evidencia '{transaction_id}' no encontrada.")
        return evidencia

    def listar_pendientes_hitl(self, tenant_id: uuid.UUID) -> list[Evidencia]:
        return self.evidencia_repo.listar_pendientes_hitl(tenant_id)

    def completar_decision_hitl(
        self, transaction_id: uuid.UUID, decision: str, operador: str,
        agente_decisor: dict | None = None, resultado_ejecucion: dict | None = None,
    ) -> Evidencia:
        """
        Cierra una Evidencia pendiente de HITL. Recalcula el hash sobre
        TODOS los campos (incluida la decisión) — el hash post-decisión
        certifica la historia completa, no solo el estado inicial.
        """
        evidencia = self.obtener_o_404(transaction_id)
        if evidencia.decision is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"La evidencia '{transaction_id}' ya tiene una decisión registrada ({evidencia.decision}). "
                "No se puede modificar — es inmutable una vez resuelta.",
            )

        campos = {
            "transaction_id": str(evidencia.transaction_id), "thread_id": str(evidencia.thread_id),
            "tenant_id": str(evidencia.tenant_id), "empresa": evidencia.empresa,
            "canal": evidencia.canal.value, "operacion": evidencia.operacion.value,
            "payload_original": evidencia.payload_original, "esquema_pydantic": evidencia.esquema_pydantic,
            "validacion": evidencia.validacion.value, "riesgo": evidencia.riesgo.value,
            "agente_auditor": evidencia.agente_auditor, "explicacion": evidencia.explicacion,
            "tipo_loop": evidencia.tipo_loop.value, "operador": operador, "decision": decision,
            "agente_decisor": agente_decisor, "resultado_ejecucion": resultado_ejecucion,
        }
        nuevo_hash = calcular_hash_evidencia(campos)

        actualizada = self.evidencia_repo.completar_decision_hitl(
            transaction_id, decision, operador, agente_decisor, resultado_ejecucion, nuevo_hash,
        )
        if actualizada is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "No se pudo completar la decisión — ya estaba resuelta.")
        logger.info("[Evidencia] HITL resuelto TXN=%s decision=%s operador=%s hash_nuevo=%s…",
                     transaction_id, decision, operador, nuevo_hash[:12])
        return actualizada

    def listar_por_tenant(self, tenant_id: uuid.UUID, **filtros) -> list[Evidencia]:
        return self.evidencia_repo.listar_por_tenant(tenant_id, **filtros)

    def kpis(self, tenant_id: uuid.UUID) -> dict:
        return self.evidencia_repo.kpis_por_tenant(tenant_id)

    # ── Trazabilidad ─────────────────────────────────────────

    def registrar_trazabilidad(self, data: MatrizTrazabilidadCreate) -> MatrizTrazabilidad:
        fila = self.trazabilidad_repo.registrar(data)
        logger.info("[Trazabilidad] %s → %s (%s)", fila.requisito, fila.resultado, fila.bitacora_id)
        return fila

    def matriz_por_tenant(self, tenant_id: uuid.UUID) -> list[MatrizTrazabilidad]:
        return self.trazabilidad_repo.listar_por_tenant(tenant_id)

    # ── Hallazgos (Auditor Interno) ──────────────────────────

    def registrar_hallazgo(self, data: HallazgoAuditoriaCreate) -> HallazgoAuditoria:
        hallazgo = self.hallazgo_repo.crear(data)
        logger.info("[Hallazgo] %s registrado por auditor=%s", hallazgo.tipo, hallazgo.auditor_id)
        return hallazgo

    def cerrar_hallazgo(self, hallazgo_id: uuid.UUID) -> HallazgoAuditoria:
        hallazgo = self.hallazgo_repo.cerrar(hallazgo_id)
        if hallazgo is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Hallazgo '{hallazgo_id}' no encontrado.")
        return hallazgo

    def hallazgos_del_periodo(self, tenant_id: uuid.UUID, periodo: str) -> list[HallazgoAuditoria]:
        return self.hallazgo_repo.listar_por_periodo(tenant_id, periodo)
