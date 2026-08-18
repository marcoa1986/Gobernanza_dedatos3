"""
src/modules/qr/models.py
==========================
Una sola tabla nueva (ver PROPUESTA-QR-EVIDENCIA.md, Sección 4).
No referencia físicamente a Evidencia con ForeignKey — el vínculo es
lógico por transaction_id, porque el QR puede generarse para tipos de
documento (cotización, orden de compra) que todavía no tienen Evidencia
al momento de imprimirse.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


class TipoDocumentoQR(str, Enum):
    DIAGNOSTICO = "diagnostico"
    COTIZACION = "cotizacion"
    ORDEN_COMPRA = "orden_compra"
    REPORTE = "reporte"
    AUDITORIA = "auditoria"
    EVIDENCIA = "evidencia"


class QRGeneradoBase(SQLModel):
    transaction_id: uuid.UUID = Field(index=True)
    tipo_documento: TipoDocumentoQR
    generado_por: str = Field(max_length=200)


class QRGenerado(QRGeneradoBase, table=True):
    __tablename__ = "qr_generado"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    generado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    veces_escaneado: int = Field(default=0)


class QRGeneradoCreate(QRGeneradoBase):
    pass


class QRGeneradoRead(QRGeneradoBase):
    id: uuid.UUID
    generado_en: datetime
    veces_escaneado: int
