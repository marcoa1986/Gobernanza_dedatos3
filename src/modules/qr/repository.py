"""
src/modules/qr/repository.py
==============================
"""

from __future__ import annotations

import uuid

from sqlmodel import Session, select

from src.modules.qr.models import QRGenerado, QRGeneradoCreate


class QRRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, data: QRGeneradoCreate) -> QRGenerado:
        registro = QRGenerado.model_validate(data)
        self.session.add(registro)
        self.session.commit()
        self.session.refresh(registro)
        return registro

    def listar_por_transaction_id(self, transaction_id: uuid.UUID) -> list[QRGenerado]:
        return list(
            self.session.exec(
                select(QRGenerado).where(QRGenerado.transaction_id == transaction_id)
            ).all()
        )

    def incrementar_escaneos(self, transaction_id: uuid.UUID) -> None:
        registros = self.listar_por_transaction_id(transaction_id)
        for registro in registros:
            registro.veces_escaneado += 1
            self.session.add(registro)
        if registros:
            self.session.commit()
