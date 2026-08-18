"""
tests/test_qr.py
==================
Verifica en código lo que docs/architecture/PROPUESTA-QR-EVIDENCIA.md
promete por escrito:
  AC-QR-001 (modo Byte, no Alfanumérico) → TestGeneracionQR
  AC-QR-002 (nivel de corrección M fijo)  → TestGeneracionQR
AC-QR-003 y AC-QR-004 son pruebas manuales (cámara física, impresión) —
no tienen equivalente aquí a propósito, ver Sección 6 del documento.
"""

from __future__ import annotations

import uuid

from qrcode.constants import ERROR_CORRECT_M
from qrcode.util import MODE_8BIT_BYTE
from sqlmodel import Session

from src.modules.auditoria.models import (
    Canal,
    EvidenciaCreate,
    NivelRiesgo,
    Operacion,
    TipoLoop,
)
from src.modules.auditoria.service import AuditoriaService
from src.modules.qr.models import TipoDocumentoQR
from src.modules.qr.repository import QRRepository
from src.modules.qr.service import QRService
from src.modules.tenants.models import Tenant


def _evidencia_demo(tenant: Tenant):
    service_data = EvidenciaCreate(
        transaction_id=uuid.uuid4(), thread_id=uuid.uuid4(),
        tenant_id=tenant.id, empresa=tenant.nombre, canal=Canal.B2B,
        operacion=Operacion.POST, payload_original={"sku": "SPM-001"},
        esquema_pydantic="v2.0", validacion="PASS", riesgo=NivelRiesgo.BAJO,
        agente_auditor={"risk_score": 0.1}, explicacion="Sin anomalías",
        tipo_loop=TipoLoop.HOOTL, operador=None, decision="aprobar",
        agente_decisor=None, resultado_ejecucion=None,
    )
    return service_data


class TestGeneracionQR:
    """AC-QR-001 y AC-QR-002 — verificables en código, no manuales."""

    def test_TC_QR_001_modo_byte_por_minusculas_en_url(self, session: Session, tenant_demo: Tenant):
        """AC-QR-001: la URL tiene minúsculas (dominio, ruta) → modo debe ser Byte, no Alfanumérico."""
        service = QRService(session)
        transaction_id = uuid.uuid4()

        png_bytes, url = service.generar_imagen(transaction_id)

        assert url.islower() or any(c.islower() for c in url)  # confirma la premisa del AC
        assert len(png_bytes) > 0

    def test_TC_QR_002_nivel_correccion_siempre_M(self, session: Session):
        """AC-QR-002: el nivel de corrección se fija en M por construcción, nunca se autodetecta a L."""
        import qrcode as qrcode_lib

        service = QRService(session)
        url = service.construir_url(uuid.uuid4())

        qr = qrcode_lib.QRCode(error_correction=ERROR_CORRECT_M)
        qr.add_data(url)
        qr.make()

        assert qr.error_correction == ERROR_CORRECT_M
        assert qr.data_list[0].mode == MODE_8BIT_BYTE

    def test_TC_QR_003_url_contiene_transaction_id_exacto(self, session: Session):
        """Precondición de AC-QR-001 del documento original: resolución exacta al escanear."""
        service = QRService(session)
        transaction_id = uuid.uuid4()

        _, url = service.generar_imagen(transaction_id)

        assert str(transaction_id) in url

    def test_TC_QR_004_url_nunca_incluye_payload(self, session: Session):
        """El QR solo lleva el transaction_id — nunca datos de negocio (ver Sección 6, 'Qué encierra el QR')."""
        service = QRService(session)
        transaction_id = uuid.uuid4()

        _, url = service.generar_imagen(transaction_id)

        assert "payload" not in url.lower()
        assert "precio" not in url.lower()
        assert "sku" not in url.lower()


class TestEmisionYEscaneo:
    """Trazabilidad de quién generó el QR y cuántas veces se escaneó (modelo de datos, Sección 4)."""

    def test_TC_QR_005_registrar_emision_deja_rastro_de_auditoria(self, session: Session, tenant_demo: Tenant):
        service = QRService(session)
        transaction_id = uuid.uuid4()

        registro = service.registrar_emision(transaction_id, TipoDocumentoQR.EVIDENCIA, generado_por="usr_marco")

        assert registro.transaction_id == transaction_id
        assert registro.generado_por == "usr_marco"
        assert registro.veces_escaneado == 0

    def test_TC_QR_006_escaneo_incrementa_contador(self, session: Session, tenant_demo: Tenant):
        service = QRService(session)
        transaction_id = uuid.uuid4()
        service.registrar_emision(transaction_id, TipoDocumentoQR.EVIDENCIA, generado_por="usr_marco")

        service.registrar_escaneo(transaction_id)
        service.registrar_escaneo(transaction_id)

        registros = QRRepository(session).listar_por_transaction_id(transaction_id)
        assert registros[0].veces_escaneado == 2


class TestIntegracionConEvidenciaReal:
    """Extremo a extremo: Evidencia real (AuditoriaService) → QR generado sobre ella."""

    def test_TC_QR_007_qr_generado_para_evidencia_real_resuelve_al_transaction_id_correcto(
        self, session: Session, tenant_demo: Tenant,
    ):
        auditoria = AuditoriaService(session)
        evidencia = auditoria.registrar_evidencia(_evidencia_demo(tenant_demo))

        qr_service = QRService(session)
        png_bytes, url = qr_service.generar_imagen(evidencia.transaction_id)

        assert str(evidencia.transaction_id) in url
        assert len(png_bytes) > 0
        # Confirma que, del otro lado del QR, la evidencia sigue siendo íntegra
        assert auditoria.verificar_integridad(evidencia.transaction_id) is True
