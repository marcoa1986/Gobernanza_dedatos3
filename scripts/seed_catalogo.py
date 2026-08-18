"""
scripts/seed_catalogo.py
==========================
Módulo 2 (ver docs/PLAN_MAESTRO.md): siembra la BD con datos REALES de
compra (catalogo.xlsx, Suministros Industriales, 164 líneas) y genera
Evidencia + Hallazgos reales — no sintéticos — para la demo del Dashboard.

RECONCILIACIÓN (2026-07-20): tu api_main.py de "Fase 2 del SOW" reveló
que mi ejecutar_accion seguía siendo un stub (nunca escribía en una
tabla real). Este script lo cierra: `ClienteERPMock` simula la tabla
`producto` del Odoo/SAP del cliente — SMARTPROMARCO no posee esa lógica
de negocio en producción (ver SOW, Sección 9, Fuera de Alcance), pero
el PoC necesita un destino real de escritura para demostrar que el
pipeline completo (auditar → decidir → ESCRIBIR → dejar evidencia)
funciona de punta a punta, no solo hasta la auditoría.

Uso:
    python scripts/seed_catalogo.py
    python scripts/seed_catalogo.py --database-url sqlite:///demo.db

ARQUITECTURA (ver docs/adr/ADR-006-separacion-cliente-servidor.md):
este script accede a la base de datos DIRECTAMENTE, sin pasar por la
API — es una excepción consciente para tooling administrativo de una
sola vez, no un descuido. Cualquier funcionalidad de producto (lo que
un usuario o proceso recurrente ejecute) debe ser cliente HTTP, como
el Dashboard en dashboard/api_client.py.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlmodel import Field, Session, SQLModel, create_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config import get_settings  # noqa: E402
from src.modules.auditoria.models import (  # noqa: E402
    Canal,
    Evidencia,  # noqa: F401 — registra la tabla en metadata
    EvidenciaCreate,
    HallazgoAuditoriaCreate,
    MatrizTrazabilidad,  # noqa: F401
    Operacion,
    TipoLoop,
)
from src.modules.auditoria.service import (  # noqa: E402
    AuditoriaService,
    determinar_tipo_loop,
    mapear_riesgo,
)
from src.modules.tenants.models import Tenant  # noqa: E402
from src.modules.tenants.repository import TenantRepository  # noqa: E402
from src.modules.usuarios.models import Usuario  # noqa: F401,E402


# ══════════════════════════════════════════════════════════════
# TABLA MOCK — simula el Odoo/SAP del cliente (solo para el PoC)
# ══════════════════════════════════════════════════════════════

class ClienteERPMock(SQLModel, table=True):
    """
    NO es un módulo de SMARTPROMARCO — simula dónde viviría el producto
    en el sistema del cliente. Le da a `ejecutar_accion` un destino real
    de escritura sin necesitar una instancia Odoo corriendo en el PoC.
    """
    __tablename__ = "cliente_erp_mock_producto"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    sku_interno: str = Field(max_length=100)
    descripcion: str = Field(max_length=500)
    categoria: str = Field(max_length=100)
    marca: str | None = Field(default=None, max_length=100)
    precio_unitario: float = 0.0
    proveedor: str = Field(max_length=200)
    orden_compra: str = Field(max_length=50)
    creado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


CAMPOS_CALIDAD = ["marca", "sku_proveedor", "codigo_original", "ficha_tecnica_url"]
VALORES_PENDIENTES = {"POR IDENTIFICAR", "PENDIENTE PROVEEDOR", "NAN", ""}


def _esta_vacio(valor) -> bool:
    if pd.isna(valor):
        return True
    return str(valor).strip().upper() in VALORES_PENDIENTES


def calcular_risk_score(row: pd.Series) -> float:
    """RN-SEED-001: el riesgo crece con cada campo de calidad faltante."""
    faltantes = sum(1 for campo in CAMPOS_CALIDAD if _esta_vacio(row.get(campo)))
    return {0: 0.10, 1: 0.35, 2: 0.55, 3: 0.75, 4: 0.90}[faltantes]


def ejecutar_accion_real(session: Session, tenant: Tenant, payload: dict) -> dict:
    """
    El write-back real que faltaba. Equivalente a `_aplicar_en_db` en tu
    api_main.py, pero contra la tabla mock en vez de un Odoo real.
    """
    registro = ClienteERPMock(
        tenant_id=tenant.id,
        sku_interno=payload["sku_interno"],
        descripcion=payload["descripcion"],
        categoria=payload["categoria"],
        marca=payload["marca"] if payload["marca"] not in VALORES_PENDIENTES else None,
        precio_unitario=payload["precio_unitario"],
        proveedor=payload["proveedor"],
        orden_compra=payload["orden_compra"],
    )
    session.add(registro)
    session.commit()
    session.refresh(registro)
    return {"registro_id": str(registro.id), "tabla": "cliente_erp_mock_producto", "filas_afectadas": 1}


def main(database_url: str | None = None, xlsx_path: str | None = None) -> None:
    settings = get_settings()
    engine = create_engine(database_url or settings.database_url, echo=False)
    SQLModel.metadata.create_all(engine)

    ruta = Path(xlsx_path or Path(__file__).parent / "seed_data" / "catalogo.xlsx")
    df = pd.read_excel(ruta, sheet_name="Catalogo_Enriquecido")
    print(f"📦 {len(df)} filas cargadas de {ruta.name}")

    with Session(engine) as session:
        # ── Tenant: Suministros Industriales (idempotente por RFC) ──
        tenant_repo = TenantRepository(session)
        tenant = tenant_repo.obtener_por_rfc("SUI900101AAA")
        if tenant is None:
            tenant = Tenant(
                nombre="Suministros Industriales SMARTPROMARCO",
                rfc="SUI900101AAA", canal="B2B",
                umbral_hitl=0.80, umbral_hotl=0.50, plan="professional",
            )
            session.add(tenant)
            session.commit()
            session.refresh(tenant)
        print(f"🏢 Tenant: {tenant.nombre} ({tenant.id})")

        auditoria = AuditoriaService(session)
        contadores = {"HITL": 0, "HOTL": 0, "HOOTL": 0}
        gaps = {campo: 0 for campo in CAMPOS_CALIDAD}

        for _, row in df.iterrows():
            risk_score = calcular_risk_score(row)
            riesgo = mapear_riesgo(risk_score)
            tipo_loop = determinar_tipo_loop(risk_score, Operacion.POST, tenant.umbral_hitl, tenant.umbral_hotl)
            contadores[tipo_loop.value] += 1

            payload = {
                "sku_interno": str(row.get("sku_interno", "")),
                "descripcion": str(row.get("descripcion", "")),
                "categoria": str(row.get("categoria_sugerida", "")),
                "marca": str(row.get("marca", "")),
                "precio_unitario": float(row.get("precio_unitario", 0) or 0),
                "cantidad": float(row.get("cantidad", 0) or 0),
                "proveedor": str(row.get("proveedor", "")),
                "orden_compra": str(row.get("orden_compra", "")),
            }

            # ── Escritura real (cierra el gap de ejecutar_accion) ───
            # HOOTL/HOTL escriben ya; HITL queda pendiente de operador
            # igual que en tu api_main.py (modo_autonomia).
            resultado_ejecucion = None
            if tipo_loop != TipoLoop.HITL:
                resultado_ejecucion = ejecutar_accion_real(session, tenant, payload)

            campos_completos = 4 - sum(1 for c in CAMPOS_CALIDAD if _esta_vacio(row.get(c)))
            auditoria.registrar_evidencia(EvidenciaCreate(
                transaction_id=uuid.uuid4(), thread_id=uuid.uuid4(),
                tenant_id=tenant.id, empresa=tenant.nombre, canal=Canal.B2B,
                operacion=Operacion.POST, payload_original=payload,
                esquema_pydantic="v2.0", validacion="PASS", riesgo=riesgo,
                agente_auditor={
                    "risk_score": risk_score,
                    "razonamiento": f"{campos_completos}/4 campos de calidad completos (marca, SKU proveedor, código original, ficha técnica).",
                },
                explicacion="Evaluado contra completitud de datos del enriquecimiento (Fase 1 pipeline).",
                tipo_loop=tipo_loop,
                operador=None,
                decision="aprobar" if tipo_loop != TipoLoop.HITL else None,
                agente_decisor=None,
                resultado_ejecucion=resultado_ejecucion,
            ))

            for campo in CAMPOS_CALIDAD:
                if _esta_vacio(row.get(campo)):
                    gaps[campo] += 1

        # ── Hallazgos agregados — así audita un humano real, no 1 por fila ──
        periodo = datetime.now(timezone.utc).strftime("%Y-%m")
        etiquetas = {
            "marca": "marca identificada", "sku_proveedor": "SKU de proveedor asignado",
            "codigo_original": "código original capturado", "ficha_tecnica_url": "ficha técnica",
        }
        hallazgos_creados = 0
        for campo, etiqueta in etiquetas.items():
            if gaps[campo] == 0:
                continue
            tipo = "No Conformidad" if gaps[campo] / len(df) > 0.5 else "Observación"
            auditoria.registrar_hallazgo(HallazgoAuditoriaCreate(
                tenant_id=tenant.id, tipo=tipo,
                descripcion=f"{gaps[campo]} de {len(df)} productos sin {etiqueta}.",
                recomendacion=f"Solicitar al proveedor completar '{campo}' antes del próximo ciclo de compra.",
                auditor_id="seed_script", periodo=periodo,
            ))
            hallazgos_creados += 1

        kpis = auditoria.kpis(tenant.id)
        print(f"✅ {len(df)} Evidencias registradas — HITL={contadores['HITL']} HOTL={contadores['HOTL']} HOOTL={contadores['HOOTL']}")
        print(f"✅ {hallazgos_creados} Hallazgos registrados (período {periodo})")
        print(f"📊 KPIs del tenant: {kpis}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Siembra la BD con catalogo.xlsx real.")
    parser.add_argument("--database-url", default=None, help="Override de DATABASE_URL (ej. sqlite:///demo.db)")
    parser.add_argument("--xlsx-path", default=None, help="Ruta alterna a catalogo.xlsx")
    args = parser.parse_args()
    main(database_url=args.database_url, xlsx_path=args.xlsx_path)
