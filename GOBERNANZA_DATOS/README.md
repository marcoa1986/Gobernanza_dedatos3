# Gobernanza de Datos — SMARTPROMARCO
## Índice único de entregables

Esta carpeta no duplica el código — enlaza y resume cada pieza del
proyecto para que se pueda navegar sin buscar entre los 87+ archivos
del repositorio. Cada entrada dice qué es, dónde vive de verdad, y con
qué evidencia (tests) queda respaldada.

---

## 1. Arquitectura y Decisiones

| Documento | Qué contiene | Ruta real |
|---|---|---|
| Plan Maestro | Convenciones (`RN-`, `CU-`, `AC-`, `TC-`, `ADR-`), secuencia de módulos, estado de fases | `docs/PLAN_MAESTRO.md` |
| ADR-001 | Estrategia Multi-Tenant: shared DB+`tenant_id` (PoC) → RLS → Schemas → BD dedicada | `docs/adr/ADR-001.md` |
| ADR-006 | Separación cliente-servidor: por qué los scripts admin acceden a BD directo y el Dashboard no | `docs/adr/ADR-006-separacion-cliente-servidor.md` |
| Propuesta QR | Trazabilidad física ISO/IEC 18004 — arquitectura, RACI, roadmap Sprint 1-4 | `docs/architecture/PROPUESTA-QR-EVIDENCIA.md` |

## 2. Producto y Experiencia

| Documento | Qué contiene | Ruta real |
|---|---|---|
| B. UX por Roles | Los 5 roles (Operativo, Supervisor, Auditor, Ejecutivo, Administrador) y su experiencia Copiloto | `docs/product/B-UX-POR-ROLES.md` |
| K. Criterios para Jurados | 9 criterios demostrables en vivo, cada uno ligado a un test real | `docs/product/K-CRITERIOS-JURADOS.md` |
| Estudios de Mercado y Factibilidad | Mercado, factibilidad económica y técnica — cada cifra trazable a su fuente real | `docs/product/ESTUDIOS-MERCADO-FACTIBILIDAD.md` |

## 3. Código — Gobierno de Datos en Ejecución

| Módulo | Qué gobierna | Ruta real | Tests |
|---|---|---|---|
| `tenants` | Multiempresa, umbrales de riesgo por tenant | `src/modules/tenants/` | 5 |
| `usuarios` | Identidad, MFA (TOTP+PIN), 6 roles RBAC (incluye `SUPERVISOR`, nuevo) | `src/modules/usuarios/`, `src/core/security.py` | 12 |
| `auditoria` | Evidencia inmutable (SHA-256), Matriz de Trazabilidad, Hallazgos, cierre HITL | `src/modules/auditoria/` | 20 |
| `orquestador` | Pipeline de auditoría + Decisor/Auditor con guardrail de reintentos | `src/modules/orquestador/` | 10 |
| `qr` | Trazabilidad física verificable | `src/modules/qr/` | 7 |
| `copiloto` | Narrativa ejecutiva — nunca cita evidencia inventada | `src/modules/copiloto/` | 5 |

**Total: 56 pruebas automatizadas, 25 endpoints, 0 fallando** al momento de generar este índice.

## 4. Contractual y Financiero

| Documento | Qué contiene |
|---|---|
| SOW v2.0 | Alcance, WBS con estado real, CAPEX/OPEX con cifras medidas (no estimadas), criterios AC- |

*(Entregado como .docx en una sesión anterior — `SOW_v2_Gobernanza_SMARTPROMARCO.docx`, fuera de este .zip por ser binario.)*

## 5. Cómo verificar cualquier afirmación de esta carpeta

```bash
pytest tests/ -v              # las 56 pruebas, en vivo
docker compose up -d --build  # el stack completo
python scripts/seed_catalogo.py           # datos reales, no de ejemplo
python scripts/bootstrap_usuario_demo.py  # credenciales para el Dashboard
```

Nada en esta carpeta afirma algo que no esté respaldado por un test o
un archivo real en el repositorio — es un índice, no una promesa aparte.
