"""
src/modules/qr/router.py
==========================
GET /evidencia/publica/{transaction_id} implementa la recomendación de
seguridad de ADR-005 (pendiente de tu confirmación): exige autenticación
con rol mínimo VIEWER. El QR es la llave física, no la puerta abierta.

Reutiliza AuditoriaService.verificar_integridad() en CADA consulta
(no como paso opcional) — así ninguna evidencia manipulada puede
mostrarse como válida a través de un escaneo.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlmodel import Session

from src.core.security import TokenPayload, require_permission
from src.database import get_session
from src.modules.auditoria.service import AuditoriaService
from src.modules.qr.models import QRGeneradoRead, TipoDocumentoQR
from src.modules.qr.repository import QRRepository
from src.modules.qr.service import QRService

router = APIRouter(tags=["Trazabilidad QR"])


@router.post(
    "/qr/generar/{transaction_id}",
    summary="Genera el PNG del QR para una transacción existente",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
def generar_qr(
    transaction_id: uuid.UUID,
    tipo_documento: TipoDocumentoQR,
    session: Session = Depends(get_session),
    user: TokenPayload = require_permission("evidencia:write"),
):
    # Verificamos que la evidencia exista ANTES de emitir el QR — de nada
    # sirve un código escaneable que apunta a un 404.
    AuditoriaService(session).obtener_o_404(transaction_id)

    service = QRService(session)
    png_bytes, url = service.generar_imagen(transaction_id)
    service.registrar_emision(transaction_id, tipo_documento, generado_por=user.sub)

    return Response(content=png_bytes, media_type="image/png", headers={"X-QR-URL": url})


@router.get(
    "/qr/emisiones/{transaction_id}",
    response_model=list[QRGeneradoRead],
    summary="Historial de emisión de QR para una transacción",
)
def historial_emisiones(
    transaction_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: TokenPayload = require_permission("auditoria:read"),
):
    return QRRepository(session).listar_por_transaction_id(transaction_id)


@router.get(
    "/evidencia/publica/{transaction_id}",
    summary="Vista curada de evidencia — a donde apunta el QR al escanear",
)
def consultar_evidencia_publica(
    transaction_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: TokenPayload = require_permission("evidencia:read"),
):
    auditoria = AuditoriaService(session)
    evidencia = auditoria.obtener_o_404(transaction_id)

    # La integridad se verifica SIEMPRE, no como paso aparte — si el hash
    # no coincide, el escaneo lo dice de inmediato, no solo el endpoint
    # de verificación explícita.
    integra = auditoria.verificar_integridad(transaction_id)

    QRService(session).registrar_escaneo(transaction_id)

    estado = "pendiente" if evidencia.decision is None else evidencia.decision.value
    return {
        "thread_id": evidencia.thread_id,
        "transaction_id": evidencia.transaction_id,
        "documento": {"tipo": evidencia.operacion.value, "fecha": evidencia.timestamp},
        "usuario": evidencia.operador,
        "tenant": evidencia.empresa,
        "estado": estado,
        "hash_sha256": evidencia.hash,
        "integridad_verificada": integra,
        "resultado_diagnostico": evidencia.agente_auditor,
        "catalogo_utilizado": evidencia.payload_original,
        "nivel_riesgo": evidencia.riesgo.value,
        "tipo_loop": evidencia.tipo_loop.value,
    }
