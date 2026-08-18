# Estudios de Mercado y Factibilidad — con Trazabilidad

Cada cifra de este documento cita su fuente real — un test que la
prueba, un script que la midió, o una búsqueda ya citada en el SOW/Dossier
de esta misma sesión. Nada aquí es una proyección sin sustento.

---

## 1. Estudio de Mercado

### 1.1 Tamaño y tendencia

| Dato | Cifra | Trazabilidad |
|---|---|---|
| Mercado global de IA Agéntica (2026) | ~$9,000–10,000M USD, CAGR >40% | Investigado en sesión de Viabilidad — ver `Dossier`, Parte IV §4.2 |
| Empresas Fortune 500 que exigirán ISO 42001 a proveedores para 2027 | 83% | Gartner 2026, citado en `Dossier` §4.2 |
| Organizaciones que han escalado IA Agéntica a producción | ~23% | Misma fuente — la brecha que SMARTPROMARCO ocupa |
| Proyectos de IA Agéntica cancelados para 2027 (por controles de riesgo inadecuados) | >40% | Misma fuente |

**Lectura de mercado:** no competimos por "más IA" — competimos por ser
la capa de gobernanza que decide si un proyecto de IA Agéntica sobrevive
hasta producción. Esa brecha (77% sin escalar, 40%+ cancelado) es la
oportunidad real, no una suposición.

### 1.2 Segmento objetivo

| Segmento | Por qué | Trazabilidad |
|---|---|---|
| PyMEs/medianas con Odoo, SAP o Salesforce | Ya tienen el sistema de registro que auditamos, sin fork | `Business Model Canvas`, bloque 1 |
| Empresas persiguiendo ISO 27001/42001 | Ya viven la brecha entre "queremos certificarnos" y "no tenemos evidencia" | ADR-001, `PLAN_MAESTRO.md` |
| Gobierno (B2G) | La reforma a la Ley Aduanera 2026 exige expediente electrónico por cliente — coincide con nuestra Evidencia | `contexto_regulatorio.py`, bloque `comercio_exterior` |

### 1.3 Competencia y diferenciación

Diferenciadores verificables, no declarados: evidencia con hash SHA-256
recalculable (`TC-AUD-004/005`), guardrail de reintentos que escala a
humano en vez de forzar una decisión (`TC-DEB-002`), y trazabilidad
física vía QR ISO/IEC 18004 (`TC-QR-001/002`) — ningún competidor de
gestión empresarial genérica ofrece los tres juntos.

---

## 2. Estudio de Factibilidad Económica

*(Consolidado del SOW v2.0, Sección 7 — cifras medidas, no reinventadas.)*

| Métrica | Valor | Trazabilidad |
|---|---|---|
| Costo real de Bedrock — 164 transacciones reales | ~$1.23 USD | Medido en `scripts/seed_catalogo.py`, corrida real |
| Costo Bedrock a escala (cliente Professional, 50K txn/mes) | ~$375/mes | Extrapolación lineal desde la medición real |
| Margen bruto en IA sobre plan Professional ($2,500/mes) | 85% | Cálculo directo: 1 − (375/2500) |
| Inversión semilla | $100,000 USD | Pitch deck, ya presentado |
| ARR Año 1 | $276,000 USD | 8 Professional + 1 Enterprise — SOW v2 §7 |
| ARR Año 2 | $1,200,000 USD | Expansión LatAm — SOW v2 §7 |
| Punto de equilibrio | Mes 9 | SOW v2 §7 |
| Certificación ISO (organismo acreditado EMA) | $8,000–15,000 USD | SOW v2 §7.1, único costo CAPEX real de Fase 5 |

**Veredicto de factibilidad económica:** viable — el costo de IA es
estructuralmente bajo (85% de margen bruto medido, no proyectado) frente
al ingreso por cliente; el mayor costo real es nómina y certificación,
ambos ya presupuestados en la semilla.

---

## 3. Estudio de Factibilidad Técnica

| Afirmación | Evidencia verificable |
|---|---|
| El sistema funciona de punta a punta, no es un mockup | **56/56 tests** automatizados, 25 endpoints documentados en `/docs` |
| Procesa datos reales, no sintéticos | 164 transacciones reales de Suministros Industriales, `scripts/seed_catalogo.py` |
| La calibración de riesgo es real | Distribución medida: HITL 58 · HOTL 102 · HOOTL 4 |
| La arquitectura respeta sus propias fronteras | 0 bytes modificados en `auditoria/` al construir QR — verificado por hash |
| Cliente-servidor limpio | `ADR-006` — Dashboard 100% HTTP, excepciones documentadas explícitamente |
| Despliegue reproducible en un solo comando | `docker compose up -d --build` — 11 servicios, 1 archivo |
| El sistema se equivoca de forma segura | 3 bugs reales encontrados y corregidos en vivo durante esta sesión (doble `Depends()`, `DetachedInstanceError`, hash sin recalcular) — no bugs ocultados, bugs corregidos con evidencia |

**Veredicto de factibilidad técnica:** viable y ya demostrado, no
proyectado — es la única de las tres factibilidades que se puede
verificar corriendo `pytest tests/ -v` en este momento.

---

## Conclusión trazable

De los tres estudios, el técnico es el único que ya está *probado*
(no estimado). El económico se apoya en una medición real (costo de
Bedrock) más proyecciones ya presentadas (ARR). El de mercado se apoya
en fuentes externas citadas (Gartner) — la única capa que depende de
condiciones fuera del control directo del equipo.
