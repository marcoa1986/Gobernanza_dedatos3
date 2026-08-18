"""
src/modules/usuarios/models.py
================================
Usuario con soporte MFA (TOTP + PIN) y rol por tenant.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel, UniqueConstraint


class UsuarioBase(SQLModel):
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    username: str = Field(max_length=100)
    email: str | None = Field(default=None, max_length=200)
    rol: str = Field(default="OPERADOR", max_length=20)


class Usuario(UsuarioBase, table=True):
    __tablename__ = "usuario"
    __table_args__ = (UniqueConstraint("tenant_id", "username", name="uq_tenant_username"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str

    # MFA
    totp_secret: str | None = Field(default=None, max_length=100)
    totp_activo: bool = Field(default=False)
    pin_hash: str | None = Field(default=None, max_length=64)
    pin_salt: str | None = Field(default=None, max_length=32)
    intentos_fallidos_mfa: int = Field(default=0)
    bloqueado: bool = Field(default=False)

    ultimo_login: datetime | None = Field(default=None)
    creado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UsuarioCreate(SQLModel):
    tenant_id: uuid.UUID
    username: str
    email: str | None = None
    rol: str = "OPERADOR"
    password: str = Field(min_length=8)


class UsuarioRead(UsuarioBase):
    id: uuid.UUID
    totp_activo: bool
    bloqueado: bool
    creado_en: datetime
