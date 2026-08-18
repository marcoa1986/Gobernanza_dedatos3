"""
src/modules/tenants/models.py
==============================
SQLModel unifica en una sola clase lo que antes eran dos (Pydantic +
SQLAlchemy por separado). El patrón: una clase Base con los campos
compartidos, y subclases que agregan tabla o restringen el esquema
según el caso de uso (Create / Read / tabla real).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class TenantBase(SQLModel):
    """Campos compartidos entre la tabla y los esquemas de API."""
    nombre: str = Field(max_length=200, index=True)
    rfc: str | None = Field(default=None, max_length=20, unique=True)
    canal: str = Field(default="B2B", max_length=10)          # B2B | B2C | B2G

    umbral_hitl: float = Field(default=0.80, ge=0.0, le=1.0)
    umbral_hotl: float = Field(default=0.50, ge=0.0, le=1.0)

    plan: str = Field(default="starter", max_length=50)        # starter|professional|enterprise
    max_transacciones_mes: int = Field(default=1000, ge=1)

    activo: bool = Field(default=True)


class Tenant(TenantBase, table=True):
    """Tabla real en PostgreSQL."""
    __tablename__ = "tenant"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    creado_en: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class TenantCreate(TenantBase):
    """Payload de entrada — sin id ni creado_en (los genera el servidor)."""
    pass


class TenantRead(TenantBase):
    """Payload de salida — expone id y creado_en."""
    id: uuid.UUID
    creado_en: datetime


class TenantUpdate(SQLModel):
    """Todos los campos opcionales — PATCH parcial."""
    nombre: str | None = None
    plan: str | None = None
    umbral_hitl: float | None = None
    umbral_hotl: float | None = None
    max_transacciones_mes: int | None = None
    activo: bool | None = None
