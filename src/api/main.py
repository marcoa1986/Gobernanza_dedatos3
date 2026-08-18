"""
src/api/main.py
=================
Composition root — el único lugar donde se ensamblan todos los
módulos. Ningún módulo importa a otro directamente salvo a través
de aquí o de dependencias explícitas (core/security, database).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import get_settings
from src.database import init_db
from src.modules.auditoria.router import router as auditoria_router
from src.modules.copiloto.router import router as copiloto_router
from src.modules.orquestador.router import router as orquestador_router
from src.modules.qr.router import router as qr_router
from src.modules.tenants.router import router as tenants_router
from src.modules.usuarios.router import router as usuarios_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Plataforma SaaS de Gobernanza Inteligente de Calidad de Datos. "
        "Audita transacciones CRUD con IA (Agente Auditor + Agente Decisor), "
        "calibra HITL/HOTL/HOOTL por riesgo, y genera evidencia inmutable "
        "trazable a ISO 20000/27001/42001."
    ),
    version="0.2.0",
    contact={"name": "SMARTPROMARCO GROUP"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(usuarios_router)
app.include_router(tenants_router)
app.include_router(auditoria_router)
app.include_router(qr_router)
app.include_router(orquestador_router)
app.include_router(copiloto_router)


@app.on_event("startup")
def on_startup() -> None:
    logger.info("🚀 %s arrancando (env=%s)", settings.app_name, settings.environment)
    init_db()
    logger.info("✅ Tablas SQLModel verificadas/creadas.")


@app.get("/health", tags=["Sistema"], summary="Health check")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}
