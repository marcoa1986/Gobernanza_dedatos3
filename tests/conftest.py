"""
tests/conftest.py
===================
Las pruebas usan SQLite en memoria, no PostgreSQL — así corren en
segundos y sin depender de Docker estar levantado. Los tipos de
columna (UUID, JSON) son compatibles vía SQLModel/SQLAlchemy en
ambos motores, así que esto valida la lógica real, no un mock.
"""

from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session, SQLModel, create_engine

from src.modules.auditoria.models import Evidencia  # noqa: F401 — registra la tabla en metadata
from src.modules.qr.models import QRGenerado  # noqa: F401
from src.modules.tenants.models import Tenant
from src.modules.usuarios.models import Usuario  # noqa: F401


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="tenant_demo")
def tenant_demo_fixture(session: Session) -> Tenant:
    tenant = Tenant(
        id=uuid.uuid4(),
        nombre="Suministros Industriales Demo",
        rfc="SID900101ABC",
        canal="B2B",
        umbral_hitl=0.80,
        umbral_hotl=0.50,
        plan="professional",
    )
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return tenant
