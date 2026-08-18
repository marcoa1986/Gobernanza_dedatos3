"""
src/modules/auditoria/models.py
=================================
Migrado de SQLAlchemy puro a SQLModel: una sola definición sirve
como tabla Y como esquema de API — se elimina la duplicación que
existía entre orchestrator.py (Pydantic) y models_evidencia.py (SQLAlchemy).

Tabla Evidencia — INMUTABLE una vez creada (ver EvidenciaRepository).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlmodel import JSON, Column, Field, SQLModel, Text


class Canal(str, Enum):
    B2B = "B2B"
    B2C = "B2C"
    B2G = "B2G"


class Operacion(str, Enum):
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


class Validacion(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class NivelRiesgo(str, Enum):
    BAJO = "Bajo"
    MEDIO = "Medio"
    ALTO = "Alto"


class TipoLoop(str, Enum):
    HITL = "HITL"
    HOTL = "HOTL"
    HOOTL = "HOOTL"


class DecisionHumana(str, Enum):
    APROBAR = "aprobar"
    RECHAZAR = "rechazar"
    MODIFICAR = "modificar"


# ══════════════════════════════════════════════════════════════
# EVIDENCIA
# ══════════════════════════════════════════════════════════════

class EvidenciaBase(SQLModel):
    transaction_id: uuid.UUID = Field(index=True)
    thread_id: uuid.UUID = Field(index=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    empresa: str = Field(max_length=200)
    canal: Canal

    operacion: Operacion
    payload_original: dict = Field(sa_column=Column(JSON))
    esquema_pydantic: str = Field(default="v2.0", max_length=50)

    validacion: Validacion = Field(default=Validacion.PASS)

    riesgo: NivelRiesgo
    agente_auditor: dict = Field(sa_column=Column(JSON))
    explicacion: str | None = Field(default=None, sa_column=Column(Text))

    tipo_loop: TipoLoop
    operador: str | None = Field(default=None, max_length=200)
    decision: DecisionHumana | None = Field(default=None)

    agente_decisor: dict | None = Field(default=None, sa_column=Column(JSON))
    resultado_ejecucion: dict | None = Field(default=None, sa_column=Column(JSON))


class Evidencia(EvidenciaBase, table=True):
    __tablename__ = "evidencia"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    hash: str = Field(max_length=64, unique=True, index=True)  # SHA-256


class EvidenciaCreate(EvidenciaBase):
    pass


class EvidenciaRead(EvidenciaBase):
    id: uuid.UUID
    timestamp: datetime
    hash: str


# ══════════════════════════════════════════════════════════════
# MATRIZ DE TRAZABILIDAD
# ══════════════════════════════════════════════════════════════

class MatrizTrazabilidadBase(SQLModel):
    evidencia_id: uuid.UUID = Field(foreign_key="evidencia.id", index=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)

    requisito: str = Field(max_length=20, index=True)       # RN-001
    regla: str = Field(max_length=200)                        # Stock >= 0
    caso_prueba: str = Field(max_length=20)                   # TC-001
    tipo_validacion: str = Field(max_length=50)                # Pydantic | IA | HITL
    agente: str = Field(max_length=100)                        # Auditor | Humano | Sistema
    resultado: str = Field(max_length=50)                       # PASS | FAIL | Aprobado
    bitacora_id: str = Field(max_length=50)                     # TX001

    canal: Canal | None = None
    observaciones: str | None = Field(default=None, sa_column=Column(Text))


class MatrizTrazabilidad(MatrizTrazabilidadBase, table=True):
    __tablename__ = "matriz_trazabilidad"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MatrizTrazabilidadCreate(MatrizTrazabilidadBase):
    pass


class MatrizTrazabilidadRead(MatrizTrazabilidadBase):
    id: uuid.UUID
    timestamp: datetime


# ══════════════════════════════════════════════════════════════
# HALLAZGOS DEL AUDITOR INTERNO
# ══════════════════════════════════════════════════════════════

class TipoHallazgo(str, Enum):
    NO_CONFORMIDAD = "No Conformidad"
    OBSERVACION = "Observación"
    HALLAZGO = "Hallazgo"
    ACCION_CORRECTIVA = "Acción Correctiva"


class EstadoHallazgo(str, Enum):
    ABIERTO = "abierto"
    EN_PROCESO = "en_proceso"
    CERRADO = "cerrado"
    VERIFICADO = "verificado"


class HallazgoAuditoriaBase(SQLModel):
    evidencia_id: uuid.UUID | None = Field(default=None, foreign_key="evidencia.id")
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)

    tipo: TipoHallazgo
    descripcion: str = Field(sa_column=Column(Text))
    evidencia_texto: str | None = Field(default=None, sa_column=Column(Text))
    recomendacion: str | None = Field(default=None, sa_column=Column(Text))

    estado: EstadoHallazgo = Field(default=EstadoHallazgo.ABIERTO)
    fecha_limite: datetime | None = None
    fecha_cierre: datetime | None = None

    auditor_id: str = Field(max_length=200)
    responsable_id: str | None = Field(default=None, max_length=200)

    periodo: str | None = Field(default=None, max_length=20)   # "2026-07"
    informe_id: str | None = Field(default=None, max_length=50)


class HallazgoAuditoria(HallazgoAuditoriaBase, table=True):
    __tablename__ = "hallazgo_auditoria"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    creado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HallazgoAuditoriaCreate(HallazgoAuditoriaBase):
    pass


class HallazgoAuditoriaRead(HallazgoAuditoriaBase):
    id: uuid.UUID
    creado_en: datetime
