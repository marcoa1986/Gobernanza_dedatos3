"""
src/database.py
================
Punto único de acceso a PostgreSQL. Todos los módulos importan
`get_session` como dependencia FastAPI — nunca crean su propio engine.
"""

from __future__ import annotations

from typing import Iterator

from sqlmodel import SQLModel, Session, create_engine

from src.core.config import get_settings

_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    echo=_settings.database_echo,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,      # evita conexiones muertas tras inactividad
)


def init_db() -> None:
    """
    Crea todas las tablas registradas en el metadata de SQLModel.
    Se llama una sola vez en el startup de FastAPI.
    En producción esto lo reemplaza Alembic (próximo módulo del roadmap).
    """
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """Dependencia FastAPI: una sesión por request, se cierra sola."""
    with Session(engine) as session:
        yield session

        # Asegúrate de que la contraseña aquí sea admin123
SQLALCHEMY_DATABASE_URL = "postgresql+psycopg://smartpromarco:admin123@127.0.0.1:5432/smartpromarco_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
# ... el resto de tu código con SQLModel se queda igual ...
