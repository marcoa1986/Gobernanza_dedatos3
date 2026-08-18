# SMARTPROMARCO Gobernanza — Plataforma SaaS de Auditoría Inteligente

**Versión:** 0.2.0 · **Estado:** PoC — Módulo 1 (Fundación) completo
**Convenciones del proyecto:** ver `docs/PLAN_MAESTRO.md`

## Qué es

Audita transacciones CRUD críticas en ERPs/CRMs (Odoo, SAP, Salesforce) con
un Agente Auditor de IA (Claude 3.5 Sonnet vía AWS Bedrock), calibra el nivel
de intervención humana (HITL/HOTL/HOOTL) según el riesgo, y genera evidencia
inmutable (hash SHA-256) trazable a ISO 20000/27001/42001.

## Estructura real del repo

```
smartpromarco-gobernanza/
├── api_main.py                    # shim → src/api/main.py (compat. launch.json)
├── compose.yaml                   # único Docker Compose (servicios PoC + extended)
├── docker/Dockerfile
├── requirements.txt
├── .env.example
├── pytest.ini
├── src/
│   ├── database.py                # engine/session SQLModel
│   ├── core/
│   │   ├── config.py               # Settings — única fuente de configuración
│   │   └── security.py             # MFA/TOTP + JWT + RBAC (infraestructura pura)
│   ├── modules/
│   │   ├── tenants/                # models · repository · service · router
│   │   ├── usuarios/               # Usuario + endpoints /auth/*
│   │   ├── auditoria/              # Evidencia · MatrizTrazabilidad · Hallazgo
│   │   ├── orquestador/            # ai_agents.py (LangGraph/Bedrock) + service.py
│   │   └── qr/                     # QRGenerado + generación (ISO/IEC 18004)
│   └── api/
│       ├── main.py                 # composition root — arma la app real
│       └── dependencies.py         # get_tenant_activo (API Gateway de la PoC)
├── tests/                          # 36 tests, todos ligados a un TC-XXX-NNN
└── docs/
    ├── PLAN_MAESTRO.md             # convenciones, ID globales, secuencia de módulos
    ├── adr/ADR-001.md              # Estrategia Multi-Tenant
    └── architecture/
        └── PROPUESTA-QR-EVIDENCIA.md  # arquitectura + ISO/IEC 18004 + RACI + roadmap
```

## Levantar el PoC

```bash
cp .env.example .env    # y edita tus credenciales

# Solo los servicios del PoC (postgres, redis, adminer, api, dashboard):
docker compose up -d

# Si además necesitas Qdrant/MinIO/Grafana/Prometheus/Loki/n8n/Ollama:
docker compose --profile extended up -d
```

URLs:
- API + Swagger → http://localhost:8000/docs
- Dashboard Streamlit → http://localhost:8501
- Adminer (inspección BD) → http://localhost:8081

## Desarrollo local sin Docker para la API

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn api_main:app --reload --port 8000
```

## Sembrar datos reales (Módulo 2)

```bash
# Contra Postgres real (usa DATABASE_URL de tu .env):
python scripts/seed_catalogo.py

# Contra SQLite local, para probar sin Docker:
python scripts/seed_catalogo.py --database-url "sqlite:///demo.db"
```

Carga `scripts/seed_data/catalogo.xlsx` (164 líneas reales de compra de
Suministros Industriales), genera Evidencia + Hallazgos reales, y escribe
en `ClienteERPMock` (simulación del Odoo/SAP del cliente) para las
transacciones HOTL/HOOTL — HITL queda pendiente de aprobación, igual que
en producción.

## Tests

```bash
pytest                    # 36 tests — SQLite en memoria, no requiere Docker
pytest --cov=src tests/   # con cobertura
```

## Documentación

- **`docs/PLAN_MAESTRO.md`** — el plan completo: convenciones de trazabilidad,
  secuencia de módulos, decisiones de arquitectura.
- **`docs/adr/ADR-001.md`** — Estrategia Multi-Tenant.

## Convención de identificadores

`RN-` regla de negocio · `CU-` caso de uso · `RF-` requisito funcional ·
`TC-` caso de prueba · `EVT-` evento de dominio · `ADR-` decisión de
arquitectura. Detalle completo en `docs/PLAN_MAESTRO.md`.
