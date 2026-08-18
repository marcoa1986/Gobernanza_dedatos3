# B. UX y Experiencia por Roles

Los 5 roles de negocio pedidos, mapeados contra el RBAC real (4 ya
existían, `SUPERVISOR` se agregó esta sesión — ver `core/security.py`).
Cada uno entra a una experiencia distinta, no al mismo panel genérico.

---

## 1. Operativo → `OPERADOR`

**Qué ve al entrar:** el Copiloto le dice cuántas transacciones esperan
su decisión, ordenadas por riesgo — no una tabla que tiene que interpretar.

> 🔴 3 transacciones de riesgo Alto llevan más de 2 horas esperando.
> La más antigua es un DELETE sobre inventario — revísala primero.

**Acciones:** Aprobar, Rechazar, Modificar (`POST /orquestador/transacciones/{id}/decision`, ya construido y probado).

---

## 2. Supervisor → `SUPERVISOR` (nuevo, esta sesión)

**Qué ve al entrar:** el estado de TODO el HITL pendiente del tenant,
no solo lo suyo — puede intervenir en cualquier pendiente.

> 12 transacciones pendientes en el tenant. 3 llevan más de 4 horas —
> considera resolverlas o reasignarlas.

**Acciones:** mismas que Operativo (`hitl:respond`) pero con visión de
conjunto. **Límite honesto:** hoy no existe asignación explícita
operador→transacción en el modelo de datos — Supervisor ve y actúa
sobre el pool completo, no "el trabajo de Juan vs. el de Ana". Eso es
una fase posterior si se necesita, no algo que finja tener ya.

---

## 3. Auditor → `AUDITOR_INTERNO`

**Qué ve al entrar:** el ciclo de 8 pasos ya documentado en el SOW,
con el Copiloto sugiriendo la muestra a revisar primero (prioriza
riesgo alto + antigüedad sin hallazgo).

> Sugerencia de muestra para tu ciclo de julio: 8 transacciones de
> riesgo Alto sin hallazgo registrado. Empieza por la más antigua.

**Acciones:** consultar evidencia, verificar integridad (`GET /qa/evidencia/{id}/verificar`), registrar hallazgos, cerrar auditoría.

---

## 4. Ejecutivo → `VIEWER`

**Qué ve al entrar:** directo al Resumen Ejecutivo del Copiloto —
nunca una tabla operativa por default.

> Usa `GET /copiloto/resumen-ejecutivo` (ya construido y probado,
> 5 tests) — responde exactamente qué ocurre, por qué, impacto,
> recomendación, evidencia citada (nunca inventada) y decisión requerida.

**Acciones:** solo lectura; puede pedir profundizar en cualquier punto.

---

## 5. Administrador → `TENANT_ADMIN`

**Qué ve al entrar:** salud del sistema, no operación día a día.

> 1 usuario bloqueado por intentos fallidos de MFA. Umbral HITL del
> tenant: 0.80 — sin cambios recientes.

**Acciones:** gestión de usuarios, configuración de tenant, umbrales
de riesgo (`POST/PATCH /tenants`).

---

## Resumen técnico

| Rol UX | Rol RBAC | ¿Nuevo? | Permisos clave |
|---|---|---|---|
| Operativo | `OPERADOR` | No | `hitl:respond`, `evidencia:read` |
| Supervisor | `SUPERVISOR` | **Sí** | `hitl:respond` (todo el tenant), `trazabilidad:read` |
| Auditor | `AUDITOR_INTERNO` | No | `auditoria:write`, `informe:write` |
| Ejecutivo | `VIEWER` | No | `dashboard:read` únicamente |
| Administrador | `TENANT_ADMIN` | No | `usuarios:admin`, `evidencia:write` |
