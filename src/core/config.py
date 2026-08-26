"""
src/core/config.py
===================
Configuración centralizada del proyecto (una sola fuente de verdad).
Todos los módulos importan de aquí — nunca leen os.getenv() directamente.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── App ──────────────────────────────────────────────────
    app_name: str = "SMARTPROMARCO Gobernanza"
    environment: str = "development"          # development | staging | production
    debug: bool = True

    # ── Base de datos ────────────────────────────────────────
    database_url: str = "postgresql+psycopg://smartpromarco:smartpromarco@smartpromarco-postgres:5432/smartpromarco"
    database_echo: bool = False

    # ── Redis (pub/sub de alertas del orquestador) ──────────
    redis_url: str = "redis://localhost:6379"

    # ── Seguridad ────────────────────────────────────────────
    jwt_secret: str = "cambia-esto-en-produccion-con-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 480
    jwt_temp_expire_minutes: int = 5
    mfa_issuer: str = "SMARTPROMARCO"

    # ── AWS Bedrock (Agente Auditor / Decisor) ──────────────
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    model_id: str = "anthropic.claude-3-5-sonnet-20241022"
    connect_timeout: int = 5
    read_timeout: int = 30
    max_retries: int = 2
    temperature: float = 0.0
    top_p: float = 0.9
    log_bedrock_calls: bool = True
    log_token_usage: bool = True

    # ── LangGraph (checkpointing del Agente Auditor/Decisor) ─
    sqlite_db_path: str = "./langgraph_checkpoints.db"
    interrupt_node: str = "tomar_decision"

    # ── CORS ─────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:8501", "http://localhost:3000"]

    # ── QR (ISO/IEC 18004) ──────────────────────────────────
    qr_base_url: str = "http://localhost:8000"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton — se cachea para no releer .env en cada request."""
    return Settings()
