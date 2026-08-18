"""
src/modules/qr/service.py
============================
Consumidor delgado de AuditoriaService — no importa nada de
src/modules/auditoria/ salvo tipos de lectura (ver AC-QR de
PROPUESTA-QR-EVIDENCIA.md, "0 líneas modificadas en auditoria/").

Implementa AC-QR-001 y AC-QR-002 (verificables en código):
  AC-QR-001: el modo de codificación debe ser Byte, no Alfanumérico
             (nuestras URLs llevan minúsculas).
  AC-QR-002: el nivel de corrección se fija en M, nunca se degrada a L.
AC-QR-003 y AC-QR-004 son pruebas manuales (Sprint 3, ver roadmap) —
no se pueden verificar con pytest porque dependen de una cámara física.
"""

from __future__ import annotations

import io
import uuid

import qrcode
from qrcode.constants import ERROR_CORRECT_M
from qrcode.util import MODE_8BIT_BYTE
from sqlmodel import Session

from src.core.config import get_settings
from src.modules.qr.models import QRGenerado, QRGeneradoCreate, TipoDocumentoQR
from src.modules.qr.repository import QRRepository


class QRService:
    def __init__(self, session: Session):
        self.repo = QRRepository(session)
        self.settings = get_settings()

    def construir_url(self, transaction_id: uuid.UUID) -> str:
        base = self.settings.qr_base_url.rstrip("/")
        return f"{base}/evidencia/publica/{transaction_id}"

    def generar_imagen(self, transaction_id: uuid.UUID) -> tuple[bytes, str]:
        """
        Genera el PNG del QR. Retorna (bytes_png, url_codificada).
        Nivel de corrección M fijo por construcción — nunca autodetectado,
        así AC-QR-002 se cumple siempre, no "en la mayoría de los casos".
        """
        url = self.construir_url(transaction_id)

        qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=10, border=4)
        qr.add_data(url)
        qr.make(fit=True)

        # AC-QR-001: verificar en tiempo de generación, no solo en tests,
        # que el modo sea Byte — si algún día cambiamos a URLs en mayúsculas
        # y esto deja de cumplirse, preferimos fallar aquí, no en producción.
        modo_usado = qr.data_list[0].mode
        if modo_usado != MODE_8BIT_BYTE:
            raise ValueError(
                f"AC-QR-001 violado: se esperaba modo Byte (4), se obtuvo {modo_usado}. "
                "¿La URL dejó de tener minúsculas?"
            )

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue(), url

    def registrar_emision(
        self, transaction_id: uuid.UUID, tipo_documento: TipoDocumentoQR, generado_por: str,
    ) -> QRGenerado:
        """Deja rastro de auditoría de QUIÉN emitió el QR y CUÁNDO — no del contenido, ya inmutable en Evidencia."""
        return self.repo.crear(QRGeneradoCreate(
            transaction_id=transaction_id, tipo_documento=tipo_documento, generado_por=generado_por,
        ))

    def registrar_escaneo(self, transaction_id: uuid.UUID) -> None:
        self.repo.incrementar_escaneos(transaction_id)
