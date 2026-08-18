# PLAN MAESTRO — SMARTPROMARCO Gobernanza
## Trazabilidad, Arquitectura y Secuencia de Módulos

**Versión:** 1.1 · **Fecha:** 2026-07-20
**Propósito:** documento único de referencia para no repetir convenciones en
cada sesión. Todo lo demás (RN-\*.md, CU-\*.md, matrix.md) se deriva de aquí.

**Nota de continuidad:** este archivo reemplaza tu copia local de
`docs/PLAN_MAESTRO.md` — agrega el prefijo `AC-` y la propuesta QR
(secciones 1 y 6) sobre la versión que ya tenías del Módulo 1+2.

---

## 1. Sistema de Identificadores Globales

Cada artefacto tiene un ID único y un enlace bidireccional al código —
no documentación que describe el código "por fuera", sino documentación
que apunta a la línea exacta donde vive la decisión.

| Prefijo | Significa | Vive en | Ejemplo YA implementado |
|---|---|---|---|
| `RN-` | Regla de Negocio | `docs/business_rules/RN-{MOD}-{NNN}.md` | `RN-EVI-001` → `src/modules/auditoria/service.py::calcular_hash_evidencia` |
| `CU-` | Caso de Uso | `docs/use_cases/CU-{MOD}-{NNN}.md` | `CU-AUD-001` → `src/modules/auditoria/router.py::registrar_evidencia` |
| `RF-` | Requisito Funcional | `docs/requirements.md` | `RF-001` (Multi-tenant) → `ADR-001` |
| `TC-` | Caso de Prueba | `tests/test_*.py` | `TC-AUD-001` → `tests/test_auditoria.py` |
| `AC-` | Criterio de Aceptación | Sección ISO/IEC 25010 del documento de propuesta correspondiente | `AC-QR-001` → `docs/architecture/PROPUESTA-QR-EVIDENCIA.md` |
| `EVT-` | Evento de dominio | `src/modules/*/events.py` (Módulo 4+) | `EVT-EVIDENCIA-CREADA` (planeado) |
| `ADR-` | Decisión de Arquitectura | `docs/adr/ADR-{NNN}.md` | `ADR-001` → `docs/adr/ADR-001.md` |

**Código de módulo (3 letras)** usado en todos los IDs:
`TEN`=Tenants · `USR`=Usuarios · `EVI`=Evidencia · `ORQ`=Orquestador ·
`SEC`=Seguridad · `GTW`=Gateway · `TRZ`=Trazabilidad · `QR`=Trazabilidad QR

---

## 2. Estructura Documental

```
docs/
├── PLAN_MAESTRO.md
├── requirements.md               # catálogo RF- (Módulo 3)
├── business_rules/               # RN-{MOD}-{NNN}.md (Módulo 3)
├── use_cases/                    # CU-{MOD}-{NNN}.md (Módulo 3)
├── traceability/
│   └── matrix.md                  # tabla viva (Módulo 3)
├── adr/
│   └── ADR-001.md                 # Multi-Tenant — ✅ ya escrito
└── architecture/
    └── PROPUESTA-QR-EVIDENCIA.md  # ✅ propuesta, sin código todavía
```

---

## 3. Decisiones de Arquitectura (ADRs)

| ADR | Decisión | Estado |
|---|---|---|
| ADR-001 | Multi-tenant: shared DB+`tenant_id` (PoC) → RLS (PyME) → Schemas (Enterprise) → BD dedicada (Gob/Banca/Salud) | ✅ Aprobado, implementado |
| ADR-002 | Todo servicio corre en Docker vía un único `compose.yaml`; Ubuntu se mantiene limpio | ✅ Implementado en código, falta formalizar el .md — Módulo 4 |
| ADR-003 | Auth: JWT/OAuth2 en PoC; OIDC/SAML preparados, sin implementar | ⏳ Módulo 4 |
| ADR-004 | API Gateway como middleware FastAPI en el PoC | ✅ Implementado, falta formalizar el .md — Módulo 4 |
| ADR-005 | Seguridad del endpoint público de consulta QR (AC-QR-006) | ⏳ Decisión pendiente — ver Sección 6 |
| ADR-006 | Separación cliente-servidor: Dashboard es cliente HTTP puro; scripts administrativos (seed, bootstrap) acceden a BD directo como excepción consciente | ✅ Aprobado, documentado en código |

---

## 4. Streamlit — mensajes de reglas de negocio

Confirmado: `st.success()`/`st.error()`/`st.warning()` por regla, `st.toast()`
para alertas en tiempo real, badges de riesgo por color. Se construye sobre
`/qa/dashboard/kpis` y `/qa/evidencia`, ya probados.

---

## 5. Matriz de Trazabilidad — extracto

| Requisito | Regla | Caso de Uso | API | Servicio | Modelo | Test |
|---|---|---|---|---|---|---|
| RF-001 | RN-TEN-001 | CU-TEN-001 | `POST /tenants` | `TenantService.alta_tenant` | `Tenant` | TC-TEN-003 |
| RF-003 | RN-EVI-001 (hash inmutable) | CU-AUD-001 | `POST /qa/evidencia` | `AuditoriaService.registrar_evidencia` | `Evidencia` | TC-AUD-001, TC-AUD-002 |
| RF-004 | RN-EVI-002 (integridad verificable) | CU-AUD-002 | `GET /qa/evidencia/{id}/verificar` | `AuditoriaService.verificar_integridad` | `Evidencia` | TC-AUD-004, TC-AUD-005 |
| RF-005 | RN-ORQ-001 (DELETE siempre HITL) | CU-ORQ-001 | — (interno) | `determinar_tipo_loop` | — | TC-AUD-006 |

---

## 6. Módulo QR — Trazabilidad (propuesta, Módulo 3.5)

Ver `docs/architecture/PROPUESTA-QR-EVIDENCIA.md` para el detalle completo
(arquitectura, modelo de datos, ISO/IEC 25010, RACI, roadmap Sprint 1-4).
Resumen: consumidor delgado de `AuditoriaService`, 0 líneas modificadas en
`auditoria/`, 1 sola tabla nueva (`QRGenerado`). Decisión pendiente tuya:
si el endpoint de consulta pública debe requerir autenticación (AC-QR-006).

---

## 7. Secuencia de Módulos (roadmap actualizado)

| # | Módulo | Contenido | Estado |
|---|---|---|---|
| 1 | Fundación PoC | Tenants, Usuarios/MFA, Auditoría, Orquestador, SQLModel, Docker, ADR-001, 29 tests | ✅ Completo |
| 2 | Datos reales | Seed con `catalogo.xlsx`, Evidencia/Hallazgos reales, write-back real | ✅ Completo |
| 3 | Dashboard | Streamlit con mensajes de reglas de negocio | 🔵 En curso |
| 3.5 | QR Trazabilidad | Ver Sección 6 — propuesta lista, código pendiente | 📋 Propuesto |
| 4 | Gateway + ADRs pendientes | ADR-002, ADR-003, ADR-005 formalizados | ⏳ |
| 5 | Generadores + Alembic real | ERD, catálogos, plantillas Jinja2, migraciones reales | ⏳ |
| 6 | MCP Servers | PostgreSQL, Google Sheets, Jira, GitHub | ⏳ |
| 7 | Evolución Multi-Tenant | RLS → Postgres Schemas | ⏳ |

---

## 8. Infraestructura (confirmado)

No se instala PostgreSQL/Redis/MinIO/Qdrant/Ollama directamente en Ubuntu.
Un único `compose.yaml`: 5 servicios activos por defecto + 7 detrás de
`--profile extended`, activados solo cuando el Módulo correspondiente los
necesite.

---

## 9. Reconciliación — historial

**2026-07-20 (sesión anterior):** tu `api_main.py` función-based reveló que
`ejecutar_accion` era un stub — cerrado en `scripts/seed_catalogo.py`.

**2026-07-20 (esta sesión):** prompt de trazabilidad QR consolidado contra
la arquitectura existente — ver Sección 0 de `PROPUESTA-QR-EVIDENCIA.md`
para el detalle completo de qué ya existía vs. qué es genuinamente nuevo.
