"""
src/modules/auditoria/repository.py
=====================================
Evidencia es INMUTABLE: este repositorio deliberadamente no expone
ningún método de actualización o borrado sobre ella. Los hallazgos
sí son editables (ciclo de vida abierto→cerrado), porque son el
producto del trabajo del Auditor Interno, no la evidencia en sí.
"""

from __future__ import annotations

import uuid

from sqlmodel import Session, func, select

from src.modules.auditoria.models import (
    Evidencia,
    EvidenciaCreate,
    HallazgoAuditoria,
    HallazgoAuditoriaCreate,
    MatrizTrazabilidad,
    MatrizTrazabilidadCreate,
)


class EvidenciaRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, data: EvidenciaCreate, hash_valor: str) -> Evidencia:
        """Único punto de escritura inicial. No hay `actualizar()` genérico a propósito."""
        evidencia = Evidencia.model_validate(data, update={"hash": hash_valor})
        self.session.add(evidencia)
        self.session.commit()
        self.session.refresh(evidencia)
        return evidencia

    def completar_decision_hitl(
        self, transaction_id: uuid.UUID, decision: str, operador: str,
        agente_decisor: dict | None, resultado_ejecucion: dict | None, nuevo_hash: str,
    ) -> Evidencia | None:
        """
        RN-EVI-003 — la ÚNICA transición de actualización permitida:
        pendiente (decision=None) → resuelto (decision set). No es
        mutabilidad abierta: se ejecuta una sola vez por transacción
        (falla si ya tenía decision), y el hash se recalcula sobre el
        contenido completo — el registro sigue siendo 100% verificable
        después de la transición, solo que certifica un estado distinto.
        """
        evidencia = self.obtener_por_transaction_id(transaction_id)
        if evidencia is None or evidencia.decision is not None:
            return None
        evidencia.decision = decision
        evidencia.operador = operador
        evidencia.agente_decisor = agente_decisor
        evidencia.resultado_ejecucion = resultado_ejecucion
        evidencia.hash = nuevo_hash
        self.session.add(evidencia)
        self.session.commit()
        self.session.refresh(evidencia)
        return evidencia

    def obtener_por_transaction_id(self, transaction_id: uuid.UUID) -> Evidencia | None:
        return self.session.exec(
            select(Evidencia).where(Evidencia.transaction_id == transaction_id)
        ).first()

    def listar_pendientes_hitl(self, tenant_id: uuid.UUID) -> list[Evidencia]:
        return list(self.session.exec(
            select(Evidencia).where(
                Evidencia.tenant_id == tenant_id,
                Evidencia.tipo_loop == "HITL",
                Evidencia.decision == None,  # noqa: E711 — SQLAlchemy exige == con None, no `is`
            ).order_by(Evidencia.timestamp.desc())
        ).all())

    def obtener_por_hash(self, hash_valor: str) -> Evidencia | None:
        return self.session.exec(select(Evidencia).where(Evidencia.hash == hash_valor)).first()

    def listar_por_tenant(
        self, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0,
        solo_riesgo: str | None = None,
    ) -> list[Evidencia]:
        query = select(Evidencia).where(Evidencia.tenant_id == tenant_id)
        if solo_riesgo:
            query = query.where(Evidencia.riesgo == solo_riesgo)
        query = query.order_by(Evidencia.timestamp.desc()).offset(offset).limit(limit)
        return list(self.session.exec(query).all())

    def kpis_por_tenant(self, tenant_id: uuid.UUID) -> dict:
        """Agregados base para el Dashboard BI (próximo módulo)."""
        total = self.session.exec(
            select(func.count()).select_from(Evidencia).where(Evidencia.tenant_id == tenant_id)
        ).one()

        por_riesgo = dict(
            self.session.exec(
                select(Evidencia.riesgo, func.count())
                .where(Evidencia.tenant_id == tenant_id)
                .group_by(Evidencia.riesgo)
            ).all()
        )
        por_loop = dict(
            self.session.exec(
                select(Evidencia.tipo_loop, func.count())
                .where(Evidencia.tenant_id == tenant_id)
                .group_by(Evidencia.tipo_loop)
            ).all()
        )
        por_validacion = dict(
            self.session.exec(
                select(Evidencia.validacion, func.count())
                .where(Evidencia.tenant_id == tenant_id)
                .group_by(Evidencia.validacion)
            ).all()
        )
        return {
            "total": total,
            "por_riesgo": por_riesgo,
            "por_loop": por_loop,
            "por_validacion": por_validacion,
        }


class TrazabilidadRepository:
    def __init__(self, session: Session):
        self.session = session

    def registrar(self, data: MatrizTrazabilidadCreate) -> MatrizTrazabilidad:
        fila = MatrizTrazabilidad.model_validate(data)
        self.session.add(fila)
        self.session.commit()
        self.session.refresh(fila)
        return fila

    def listar_por_tenant(self, tenant_id: uuid.UUID, limit: int = 100) -> list[MatrizTrazabilidad]:
        query = (
            select(MatrizTrazabilidad)
            .where(MatrizTrazabilidad.tenant_id == tenant_id)
            .order_by(MatrizTrazabilidad.timestamp.desc())
            .limit(limit)
        )
        return list(self.session.exec(query).all())

    def listar_por_evidencia(self, evidencia_id: uuid.UUID) -> list[MatrizTrazabilidad]:
        return list(
            self.session.exec(
                select(MatrizTrazabilidad).where(MatrizTrazabilidad.evidencia_id == evidencia_id)
            ).all()
        )


class HallazgoRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, data: HallazgoAuditoriaCreate) -> HallazgoAuditoria:
        hallazgo = HallazgoAuditoria.model_validate(data)
        self.session.add(hallazgo)
        self.session.commit()
        self.session.refresh(hallazgo)
        return hallazgo

    def obtener_por_id(self, hallazgo_id: uuid.UUID) -> HallazgoAuditoria | None:
        return self.session.get(HallazgoAuditoria, hallazgo_id)

    def listar_por_periodo(self, tenant_id: uuid.UUID, periodo: str) -> list[HallazgoAuditoria]:
        query = select(HallazgoAuditoria).where(
            HallazgoAuditoria.tenant_id == tenant_id,
            HallazgoAuditoria.periodo == periodo,
        )
        return list(self.session.exec(query).all())

    def cerrar(self, hallazgo_id: uuid.UUID) -> HallazgoAuditoria | None:
        from datetime import datetime, timezone
        hallazgo = self.obtener_por_id(hallazgo_id)
        if hallazgo is None:
            return None
        hallazgo.estado = "cerrado"
        hallazgo.fecha_cierre = datetime.now(timezone.utc)
        self.session.add(hallazgo)
        self.session.commit()
        self.session.refresh(hallazgo)
        return hallazgo
