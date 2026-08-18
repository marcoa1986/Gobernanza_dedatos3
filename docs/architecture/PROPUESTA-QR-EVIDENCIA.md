# Propuesta: Trazabilidad QR sobre Evidencia Existente

**Estado:** Propuesta — sin código todavía (por instrucción explícita)
**Fecha:** 2026-07-20
**Rol:** Consolidado por líder de proyecto, relacionando esta propuesta con
el resto del trabajo ya construido (no como pieza aislada)

---

## 0. Consolidación — cómo se relaciona con lo ya construido

Antes de diseñar nada nuevo: la mayoría de lo que este prompt pide **ya existe**.
Diseñar el módulo QR como si partiéramos de cero habría violado tu propia regla
("NO reescribir, solo agregar"). Esta tabla es el resultado de esa verificación:

| Lo que pide el prompt | Dónde ya vive | Qué falta agregar |
|---|---|---|
| Thread ID, tenant, hash SHA-256, reglas ejecutadas | `src/modules/auditoria/models.py` (`Evidencia`, `MatrizTrazabilidad`) | Nada |
| "Consultar evidencia mediante FastAPI" | `GET /qa/evidencia/{transaction_id}` y `/verificar` | Nada — el QR solo necesita apuntar aquí |
| "ETL del catálogo" | `scripts/seed_catalogo.py` (transformación de columnas, cálculo de riesgo) | Formalizar como módulo reutilizable, no solo script |
| "catalog_health" | Lógica de `calcular_risk_score()` y gaps en `seed_catalogo.py` | Extraer a `src/modules/catalog_health/` |
| `src/core/thread_manager.py` | `uuid.uuid4()` nativo en `Evidencia.transaction_id`/`thread_id` | No hace falta un manager nuevo |
| Auditoría, MultiTenant, Usuarios, Orquestador, Dashboard | Módulo 1 (completo, 29 tests) | Nada |
| Generación de imagen QR, endpoint público de escaneo, ISO 18004, RACI, BPM | — | **Esto sí es genuinamente nuevo** |

**Conclusión:** la superficie nueva real es mucho más pequeña de lo que el
prompt sugiere — un módulo delgado que envuelve infraestructura que ya pasa
pruebas, no una nueva capa de auditoría paralela.

**Relación con las otras dos peticiones pendientes** (probador/criterios de
aceptación y frontend del Dashboard):
- La sección 6 (ISO/IEC 18004) de este documento **formaliza la convención
  `AC-` (Acceptance Criteria)**, ahora anclada al estándar técnico del
  símbolo QR en vez de a características de calidad genéricas — resuelve
  la petición de "probador" para este módulo específico.
- La vista de consulta de evidencia (sección 1) **es la misma pieza** que
  necesitaba el Dashboard Streamlit — no son dos entregables, son uno.
- La frontera de módulo ("0 líneas modificadas en `auditoria/`", sección 2)
  formaliza por escrito el mismo principio que motivó la pregunta sobre
  agentes desacoplados: nada nuevo depende de nada existente en una sola
  dirección.

---

## 1. Arquitectura

El módulo QR es un **consumidor delgado** de `AuditoriaService` — no una
capa de auditoría nueva. Su única responsabilidad: convertir un
`transaction_id` existente en una imagen escaneable, y ofrecer una vista de
consulta curada (no el JSON crudo de la API interna) para quien escanee.

```
┌─────────────────────────────────────────────┐
│  src/modules/auditoria/  (SIN TOCAR)          │
│  Evidencia · MatrizTrazabilidad · Hallazgo    │
└───────────────────▲───────────────────────────┘
                     │ consume (solo lectura)
┌────────────────────┴──────────────────────────┐
│  src/modules/qr/  (NUEVO)                       │
│  generar_qr() · resolver_referencia()           │
│  GET /evidencia/publica/{transaction_id}        │
└──────────────────────────────────────────────┘
```

**Decisión de seguridad que necesita tu confirmación:** el prompt especifica
que el QR no debe contener información sensible — eso ya está garantizado
(solo lleva un UUID). Pero no especifica si el *endpoint* de consulta debe
ser público o autenticado. Recomendación: autenticado con rol mínimo
`VIEWER` — el QR es la llave, no debería ser también la puerta abierta.
Ver Sección 7, característica de Seguridad, para el detalle de riesgo.

---

## 2. Diseño — estructura de módulos (reconciliada, no la del prompt tal cual)

```
src/modules/
├── qr/                        # NUEVO
│   ├── models.py               # QRGenerado (tracking de emisión)
│   ├── service.py               # generar_qr(), resolver_referencia()
│   └── router.py                 # POST /qr/generar, GET /evidencia/publica/{id}
├── catalog_health/             # NUEVO (extraído de seed_catalogo.py)
│   └── service.py                # calcular_risk_score() y detección de gaps, reutilizable
├── auditoria/                  # YA EXISTE — 0 líneas modificadas
├── tenants/                    # YA EXISTE — 0 líneas modificadas
├── usuarios/                   # YA EXISTE — 0 líneas modificadas
└── orquestador/                # YA EXISTE — 0 líneas modificadas
```

No se agrega `src/core/thread_manager.py` ni `src/dashboard/evidence/` como
carpetas separadas — el primero es innecesario (el UUID ya es nativo del
modelo), el segundo es simplemente una sección más del Dashboard Streamlit
que ya está en construcción, no un árbol de carpetas aparte.

---

## 3. Diagrama de flujo BPM

Mostrado arriba — reconciliado etapa por etapa contra lo que ya existe,
lo nuevo, y lo que queda para la Fase 4 (AWS).

---

## 4. Modelo de datos

Solo una tabla nueva — todo lo demás ya existe:

| Campo | Tipo | Nota |
|---|---|---|
| `id` | UUID | PK |
| `transaction_id` | UUID | referencia lógica a `evidencia.transaction_id` |
| `tipo_documento` | str | diagnostico\|cotizacion\|orden_compra\|reporte\|auditoria\|evidencia |
| `generado_por` | str | usuario que emitió el QR |
| `generado_en` | datetime | |
| `veces_escaneado` | int | contador, opcional para Sprint 1 |

---

## 5. Modelo de auditoría

Ya satisface todo lo que el prompt pide mostrar al escanear:

| Campo pedido en el escaneo | Ya existe en |
|---|---|
| Thread ID, Documento, Fecha | `Evidencia.thread_id`, `.transaction_id`, `.timestamp` |
| Tipo de documento | `Evidencia.operacion` |
| Usuario, Tenant | `Evidencia.operador`, `.tenant_id`/`.empresa` |
| Estado | derivable de `.decision` + `.tipo_loop` |
| Hash SHA-256 | `Evidencia.hash` + `AuditoriaService.verificar_integridad()` |
| Reglas de negocio ejecutadas | `MatrizTrazabilidad` (filas ligadas por `evidencia_id`) |
| Catálogo utilizado | `Evidencia.payload_original` |
| Resultado del diagnóstico | `Evidencia.agente_auditor` |
| Auditoría / hallazgos | `HallazgoAuditoria` |
| Evidencias relacionadas | otras `Evidencia` con el mismo `thread_id` |

---

## 6. Modelo QR — Cumplimiento con ISO/IEC 18004

**Qué encierra el QR:** solo la URL con el `transaction_id` — el UUID mide
36 caracteres, la URL completa (`https://app.smartpromarco.mx/evidencia/{id}`)
ronda 70 caracteres. Nunca datos del payload.

**Por qué Byte mode, no Alfanumérico.** El estándar define cuatro modos de
codificación: numérico, alfanumérico, byte, y kanji. El modo alfanumérico
cubre dígitos, mayúsculas y un set reducido de símbolos — pero exige
mayúsculas exclusivamente. Como nuestra URL usa minúsculas (dominio y ruta),
ese modo queda descartado por diseño: las minúsculas fuerzan el modo byte,
que es aproximadamente 1.8 veces menos eficiente que el alfanumérico.
Alternativa descartada por ahora: forzar la URL completa a mayúsculas para
aprovechar el modo alfanumérico — poco convencional y varias rutas son
case-sensitive; se puede revisitar si el tamaño físico del QR impreso se
vuelve un problema real en campo.

**Versión y nivel de corrección.** El estándar define 40 versiones (tamaños
de símbolo): la Versión 1 mide 21×21 módulos, cada versión siguiente agrega
4 módulos por lado, hasta la Versión 40 con 177×177 módulos. La capacidad
máxima teórica en modo byte a nivel de corrección L es de aproximadamente
2,953 bytes en la versión más grande — muy por encima de los ~70 caracteres
que necesitamos. En uso cotidiano (tarjetas, documentos impresos), los
códigos QR suelen rondar 100–500 caracteres con una versión modesta y nivel
de corrección M o superior — exactamente nuestro caso.

No fijamos una versión a mano — la librería la selecciona automáticamente
según el payload. Lo que sí fijamos es el **nivel de corrección: M (~15% de
recuperación)**, frente al 7% de L, 25% de Q o 30% de H — balance razonable
entre tamaño del símbolo y tolerancia a manchas o dobleces en documentos
impresos (cotizaciones, órdenes de compra, reportes).

**Librería recomendada:** `qrcode` (Python puro + Pillow) — sin
dependencias de sistema, lo que importa directamente para la portabilidad
del contenedor Docker (Sección 2).

**Criterios de aceptación** (siguen usando el prefijo `AC-`, ahora anclados
al estándar técnico del símbolo, no a características de calidad genéricas):

| ID | Criterio | Verificación |
|---|---|---|
| **AC-QR-001** | Dado un `transaction_id` válido, cuando se genera el QR, entonces el modo de codificación usado es Byte (no Alfanumérico, por las minúsculas de la URL) | Inspección del objeto `QRCode` generado |
| **AC-QR-002** | Dado el payload máximo esperado (~80 caracteres de URL), cuando se genera el QR, entonces el nivel de corrección se mantiene en M sin degradar a L | Test unitario con el payload más largo real |
| **AC-QR-003** | Dado un QR generado, cuando se escanea con cámara nativa iOS/Android, entonces se reconoce sin app adicional | Prueba manual, Sprint 3 |
| **AC-QR-004** | Dado un documento impreso con el QR, cuando sufre daño parcial (mancha, doblez) dentro del margen de corrección M, entonces sigue siendo legible | Prueba manual con impresión física, Sprint 3 |

**Lo que queda fuera de ISO/IEC 18004 pero sigue siendo una decisión real
pendiente** — el estándar define el símbolo, no quién puede consultarlo:

> **Seguridad del endpoint de consulta.** Mi recomendación se mantiene: el
> endpoint que resuelve el QR debe exigir rol `VIEWER` mínimo — el QR es la
> llave física, no debería ser también la puerta abierta. Ver ADR-005
> (pendiente, Sección 6 del Plan Maestro) — **necesito tu confirmación.**

---

## 7. Matriz RACI — proceso QR

| Actividad | Cliente | Usuario | Consultor | Arquitecto | Desarrollador | QA | Auditor | Admin AWS |
|---|---|---|---|---|---|---|---|---|
| Definir requisitos QR | A | C | R | C | I | I | C | I |
| Diseñar modelo de datos | I | I | C | R/A | C | I | I | I |
| Implementar generación QR | I | I | I | C | R/A | C | I | I |
| Implementar endpoint de consulta | I | I | I | C | R/A | C | I | I |
| Probar (unit/functional/integration) | I | I | I | I | C | R/A | I | I |
| Validar cumplimiento ISO 18004 | C | I | C | R | C | R/A | R | I |
| Desplegar a AWS | I | I | I | C | C | I | I | R/A |
| Auditar uso del QR en campo | I | I | I | I | I | I | R/A | I |

R = Responsable · A = Aprueba · C = Consultado · I = Informado

---

## 8. Roadmap técnico

| Sprint | Alcance | Archivos nuevos | Archivos modificados | Tests |
|---|---|---|---|---|
| **1** | Modelo de datos + servicio base (sin UI) | `src/modules/qr/models.py`, `service.py` | **0** | Unit: `test_qr_service.py` (resolución de referencia) |
| **2** | Endpoint de consulta + integración con Evidencia | `src/modules/qr/router.py` | **0** | Functional: verificación de auth, integración con `AuditoriaService.verificar_integridad()` |
| **3** | Generación visual (imagen) + vista en Streamlit Dashboard | `dashboard/pages/evidencia_qr.py` | `requirements.txt` (agrega `qrcode`, `Pillow`) | Integration: escaneo simulado → resolución → render |
| **4** | Hardening de seguridad + validación ISO 18004 final + preparación AWS (S3 para imágenes QR) | `docs/adr/ADR-005-qr-seguridad.md` | — | Regression: suite completa (29 + nuevos), validación de las 4 AC-QR |

**Dependencias nuevas:** `qrcode`, `Pillow` — ambas sin binarios de sistema
(ver Sección 7, Portability).

**Archivos modificados en total: 1** (`requirements.txt`, Sprint 3) — el
resto del roadmap respeta "no reescribir, solo agregar" de punta a punta.
