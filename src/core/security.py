"""
src/core/security.py
=====================
Mecánica de seguridad transversal: hashing, TOTP, JWT y RBAC.
NO contiene endpoints (esos viven en modules/usuarios/router.py) ni
lógica de negocio de usuarios (esa vive en modules/usuarios/service.py).
Este módulo es infraestructura pura — cualquier módulo puede importarlo
para proteger sus propios endpoints con `require_permission` / `require_role`.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import pyotp
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field

from src.core.config import get_settings

# ──────────────────────────────────────────────────────────────
# ROLES Y PERMISOS (RBAC)
# ──────────────────────────────────────────────────────────────

class UserRole(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    TENANT_ADMIN = "TENANT_ADMIN"
    AUDITOR_INTERNO = "AUDITOR_INTERNO"
    SUPERVISOR = "SUPERVISOR"
    OPERADOR = "OPERADOR"
    VIEWER = "VIEWER"


ROLE_PERMISSIONS: dict[UserRole, list[str]] = {
    UserRole.SUPER_ADMIN: ["*"],
    UserRole.TENANT_ADMIN: [
        "transaccion:read", "transaccion:write",
        "evidencia:read", "evidencia:write",
        "auditoria:read", "auditoria:write",
        "dashboard:read", "usuarios:admin",
        "trazabilidad:read",
    ],
    UserRole.AUDITOR_INTERNO: [
        "evidencia:read", "auditoria:read", "auditoria:write",
        "dashboard:read", "trazabilidad:read", "informe:write",
    ],
    UserRole.SUPERVISOR: [
        # Ve y puede actuar sobre TODO el HITL pendiente del tenant (no
        # solo lo suyo) — es su función: respaldo y escalamiento entre
        # operadores. NO tiene usuarios:admin — no configura el tenant,
        # eso es exclusivo de TENANT_ADMIN.
        "transaccion:read", "hitl:respond", "evidencia:read",
        "dashboard:read", "trazabilidad:read",
    ],
    UserRole.OPERADOR: [
        "transaccion:read", "hitl:respond", "evidencia:read", "dashboard:read",
    ],
    UserRole.VIEWER: ["dashboard:read", "evidencia:read"],
}


def has_permission(role: UserRole, permission: str) -> bool:
    perms = ROLE_PERMISSIONS.get(role, [])
    return "*" in perms or permission in perms


# ──────────────────────────────────────────────────────────────
# MODELOS JWT
# ──────────────────────────────────────────────────────────────

class TokenPayload(BaseModel):
    sub: str
    tenant_id: str
    rol: UserRole
    permisos: list[str]
    mfa_verified: bool = False
    exp: Optional[int] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    rol: UserRole
    mfa_verified: bool


# ──────────────────────────────────────────────────────────────
# HASHING (password, PIN)
# ──────────────────────────────────────────────────────────────

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def generar_salt() -> str:
    return secrets.token_hex(16)


def hash_pin(pin: str, salt: str) -> str:
    return hmac.new(salt.encode(), pin.encode(), hashlib.sha256).hexdigest()


def verify_pin(pin: str, salt: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_pin(pin, salt), stored_hash)


# ──────────────────────────────────────────────────────────────
# TOTP
# ──────────────────────────────────────────────────────────────

class TOTPManager:
    @staticmethod
    def generate_secret() -> str:
        return pyotp.random_base32()

    @staticmethod
    def get_provisioning_uri(secret: str, username: str, tenant: str) -> str:
        cfg = get_settings()
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=f"{tenant}/{username}", issuer_name=cfg.mfa_issuer)

    @staticmethod
    def verify_code(secret: str, code: str, valid_window: int = 1) -> bool:
        return pyotp.TOTP(secret).verify(code, valid_window=valid_window)

    @staticmethod
    def generate_backup_codes(n: int = 8) -> list[str]:
        return [secrets.token_hex(5).upper() for _ in range(n)]


# ──────────────────────────────────────────────────────────────
# JWT
# ──────────────────────────────────────────────────────────────

class JWTManager:
    @staticmethod
    def create_temp_token(user_id: str, tenant_id: str, rol: UserRole) -> str:
        cfg = get_settings()
        exp = datetime.now(timezone.utc) + timedelta(minutes=cfg.jwt_temp_expire_minutes)
        payload = {
            "sub": user_id, "tenant_id": tenant_id, "rol": rol.value,
            "permisos": [], "mfa_verified": False, "exp": exp,
        }
        return jwt.encode(payload, cfg.jwt_secret, algorithm=cfg.jwt_algorithm)

    @staticmethod
    def create_full_token(user_id: str, tenant_id: str, rol: UserRole) -> TokenResponse:
        cfg = get_settings()
        expire_delta = timedelta(minutes=cfg.jwt_access_expire_minutes)
        exp = datetime.now(timezone.utc) + expire_delta
        payload = {
            "sub": user_id, "tenant_id": tenant_id, "rol": rol.value,
            "permisos": ROLE_PERMISSIONS.get(rol, []), "mfa_verified": True, "exp": exp,
        }
        token = jwt.encode(payload, cfg.jwt_secret, algorithm=cfg.jwt_algorithm)
        return TokenResponse(
            access_token=token, expires_in=int(expire_delta.total_seconds()),
            rol=rol, mfa_verified=True,
        )

    @staticmethod
    def decode(token: str) -> TokenPayload:
        cfg = get_settings()
        try:
            data = jwt.decode(token, cfg.jwt_secret, algorithms=[cfg.jwt_algorithm])
            return TokenPayload(**data)
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token inválido o expirado: {e}",
                headers={"WWW-Authenticate": "Bearer"},
            )


# ──────────────────────────────────────────────────────────────
# DEPENDENCIAS FASTAPI (usadas por CUALQUIER router de CUALQUIER módulo)
# ──────────────────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(_bearer_scheme),
) -> TokenPayload:
    payload = JWTManager.decode(credentials.credentials)
    if not payload.mfa_verified:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "MFA no verificado. Completa el segundo factor en /auth/mfa.",
        )
    return payload


def require_permission(permission: str):
    async def _check(user: TokenPayload = Depends(get_current_user)):
        if not has_permission(UserRole(user.rol), permission):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Rol '{user.rol}' no tiene el permiso '{permission}'.",
            )
        return user
    return Depends(_check)


def require_role(*roles: UserRole):
    async def _check(user: TokenPayload = Depends(get_current_user)):
        if UserRole(user.rol) not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Se requiere uno de los roles: {[r.value for r in roles]}",
            )
        return user
    return Depends(_check)


def require_same_tenant(tenant_id: str):
    async def _check(user: TokenPayload = Depends(get_current_user)):
        if user.rol == UserRole.SUPER_ADMIN:
            return user
        if user.tenant_id != tenant_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Acceso denegado: tenant no coincide.")
        return user
    return Depends(_check)
