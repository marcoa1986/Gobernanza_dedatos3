"""
src/modules/usuarios/service.py
=================================
Lógica de autenticación real, respaldada por UsuarioRepository.
Sustituye los mocks de la versión anterior de security.py —
ahora cada paso consulta y escribe en PostgreSQL de verdad.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException, status
from sqlmodel import Session

from src.core.security import (
    JWTManager,
    TOTPManager,
    TokenResponse,
    UserRole,
    generar_salt,
    hash_password,
    hash_pin,
    verify_password,
    verify_pin,
)
from src.modules.usuarios.models import Usuario, UsuarioCreate
from src.modules.usuarios.repository import UsuarioRepository

logger = logging.getLogger(__name__)

MAX_INTENTOS_MFA = 5


class AuthService:
    def __init__(self, session: Session):
        self.repo = UsuarioRepository(session)

    def registrar_usuario(self, data: UsuarioCreate) -> Usuario:
        existente = self.repo.obtener_por_username(data.tenant_id, data.username)
        if existente is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"El usuario '{data.username}' ya existe en este tenant.",
            )
        return self.repo.crear(data, hashed_password=hash_password(data.password))

    def login(self, tenant_id: uuid.UUID, username: str, password: str) -> str:
        """
        Paso 1: valida credenciales → emite token temporal (sin permisos).
        """
        usuario = self.repo.obtener_por_username(tenant_id, username)
        if usuario is None or not verify_password(password, usuario.hashed_password):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas.")
        if usuario.bloqueado:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Cuenta bloqueada por demasiados intentos fallidos de MFA. Contacta a tu Tenant Admin.",
            )
        return JWTManager.create_temp_token(str(usuario.id), str(usuario.tenant_id), UserRole(usuario.rol))

    def verificar_totp(self, temp_token: str, codigo: str) -> TokenResponse:
        """Paso 2a: valida el código de Google Authenticator."""
        payload = JWTManager.decode(temp_token)
        if payload.mfa_verified:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Este token ya fue verificado.")

        usuario = self.repo.obtener_por_id(uuid.UUID(payload.sub))
        if usuario is None or not usuario.totp_activo or not usuario.totp_secret:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "TOTP no configurado para este usuario. Usa /auth/mfa/setup/totp primero.",
            )
        if not TOTPManager.verify_code(usuario.totp_secret, codigo):
            self.repo.registrar_intento_fallido(usuario.id, MAX_INTENTOS_MFA)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Código TOTP inválido o expirado.")

        self.repo.registrar_login_exitoso(usuario.id)
        logger.info("[Auth] Login TOTP exitoso: usuario=%s", usuario.id)
        return JWTManager.create_full_token(str(usuario.id), str(usuario.tenant_id), UserRole(usuario.rol))

    def verificar_pin(self, temp_token: str, pin: str) -> TokenResponse:
        """Paso 2b: valida el PIN de seguridad de 6 dígitos."""
        payload = JWTManager.decode(temp_token)
        if payload.mfa_verified:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Este token ya fue verificado.")

        usuario = self.repo.obtener_por_id(uuid.UUID(payload.sub))
        if usuario is None or not usuario.pin_hash or not usuario.pin_salt:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "PIN no configurado para este usuario. Usa /auth/mfa/setup/pin primero.",
            )
        if not verify_pin(pin, usuario.pin_salt, usuario.pin_hash):
            self.repo.registrar_intento_fallido(usuario.id, MAX_INTENTOS_MFA)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "PIN incorrecto.")

        self.repo.registrar_login_exitoso(usuario.id)
        logger.info("[Auth] Login PIN exitoso: usuario=%s", usuario.id)
        return JWTManager.create_full_token(str(usuario.id), str(usuario.tenant_id), UserRole(usuario.rol))

    def iniciar_setup_totp(self, usuario_id: uuid.UUID, tenant_nombre: str) -> dict:
        usuario = self.repo.obtener_por_id(usuario_id)
        if usuario is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado.")

        secret = TOTPManager.generate_secret()
        uri = TOTPManager.get_provisioning_uri(secret, usuario.username, tenant_nombre)
        codigos = TOTPManager.generate_backup_codes()
        self.repo.guardar_totp_pendiente(usuario.id, secret)
        return {"qr_uri": uri, "secret": secret, "backup_codes": codigos}

    def confirmar_setup_totp(self, usuario_id: uuid.UUID, codigo: str) -> None:
        usuario = self.repo.obtener_por_id(usuario_id)
        if usuario is None or not usuario.totp_secret:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "No hay un TOTP pendiente de confirmar.")
        if not TOTPManager.verify_code(usuario.totp_secret, codigo):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Código inválido — el TOTP no se activó.")
        self.repo.activar_totp(usuario.id)
        logger.info("[Auth] TOTP activado: usuario=%s", usuario.id)

    def configurar_pin(self, usuario_id: uuid.UUID, pin: str) -> None:
        if len(pin) != 6 or not pin.isdigit():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El PIN debe ser de exactamente 6 dígitos.")
        salt = generar_salt()
        self.repo.guardar_pin(usuario_id, hash_pin(pin, salt), salt)
        logger.info("[Auth] PIN configurado: usuario=%s", usuario_id)
