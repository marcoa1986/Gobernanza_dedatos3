"""
src/modules/usuarios/repository.py
====================================
"""

from __future__ import annotations

import uuid

from sqlmodel import Session, select

from src.modules.usuarios.models import Usuario, UsuarioCreate


class UsuarioRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, data: UsuarioCreate, hashed_password: str) -> Usuario:
        usuario = Usuario(
            tenant_id=data.tenant_id,
            username=data.username,
            email=data.email,
            rol=data.rol,
            hashed_password=hashed_password,
        )
        self.session.add(usuario)
        self.session.commit()
        self.session.refresh(usuario)
        return usuario

    def obtener_por_id(self, usuario_id: uuid.UUID) -> Usuario | None:
        return self.session.get(Usuario, usuario_id)

    def obtener_por_username(self, tenant_id: uuid.UUID, username: str) -> Usuario | None:
        return self.session.exec(
            select(Usuario).where(
                Usuario.tenant_id == tenant_id, Usuario.username == username
            )
        ).first()

    def guardar_totp_pendiente(self, usuario_id: uuid.UUID, secret: str) -> None:
        usuario = self.obtener_por_id(usuario_id)
        if usuario is None:
            return
        usuario.totp_secret = secret
        usuario.totp_activo = False  # se activa cuando confirme el primer código
        self.session.add(usuario)
        self.session.commit()

    def activar_totp(self, usuario_id: uuid.UUID) -> None:
        usuario = self.obtener_por_id(usuario_id)
        if usuario is None:
            return
        usuario.totp_activo = True
        self.session.add(usuario)
        self.session.commit()

    def guardar_pin(self, usuario_id: uuid.UUID, pin_hash: str, pin_salt: str) -> None:
        usuario = self.obtener_por_id(usuario_id)
        if usuario is None:
            return
        usuario.pin_hash = pin_hash
        usuario.pin_salt = pin_salt
        self.session.add(usuario)
        self.session.commit()

    def registrar_intento_fallido(self, usuario_id: uuid.UUID, max_intentos: int = 5) -> None:
        usuario = self.obtener_por_id(usuario_id)
        if usuario is None:
            return
        usuario.intentos_fallidos_mfa += 1
        if usuario.intentos_fallidos_mfa >= max_intentos:
            usuario.bloqueado = True
        self.session.add(usuario)
        self.session.commit()

    def registrar_login_exitoso(self, usuario_id: uuid.UUID) -> None:
        from datetime import datetime, timezone
        usuario = self.obtener_por_id(usuario_id)
        if usuario is None:
            return
        usuario.intentos_fallidos_mfa = 0
        usuario.ultimo_login = datetime.now(timezone.utc)
        self.session.add(usuario)
        self.session.commit()
