# ADR-006: Separación Cliente-Servidor — Excepción Consciente para Tooling Administrativo

**Estado:** Aprobado
**Fecha:** 2026-07-28
**Contexto de la decisión:** auditoría de arquitectura cliente-servidor solicitada explícitamente

---

## Contexto

El sistema sigue arquitectura cliente-servidor: el Dashboard (Streamlit) es
cliente puro de la API FastAPI, comunicándose exclusivamente por HTTP vía
`dashboard/api_client.py` — verificado sin ningún import directo de `src.*`.

La auditoría encontró dos excepciones: `scripts/seed_catalogo.py` y
`scripts/bootstrap_usuario_demo.py` importan directamente
`src.database`, `src.modules.tenants.*`, `src.modules.auditoria.*` y
`src.modules.usuarios.*` — es decir, manipulan la base de datos en el
mismo proceso, sin pasar por la API.

## Decisión

Estas dos excepciones se mantienen — son herramientas administrativas
de una sola vez (seed de datos reales, bootstrap de usuario demo), no
parte del flujo de negocio recurrente. El mismo patrón que usan Django
management commands o Rails rake tasks: tooling que opera fuera de la
capa API por rendimiento y simplicidad operativa.

**Regla explícita para no repetir esta ambigüedad:** cualquier script
nuevo bajo `scripts/` que sea *administrativo/de una sola vez* (seed,
migración de datos, mantenimiento) puede acceder a la BD directamente.
Cualquier funcionalidad que sea *parte del producto* — algo que un
usuario o un proceso recurrente ejecute — debe ser un cliente HTTP de
la API, igual que el Dashboard.

## Consecuencias

- Los scripts admin siguen siendo rápidos (164 inserts directos vs. 164
  llamadas HTTP con manejo de JWT solo para una carga masiva).
- Queda documentado que es una decisión, no un descuido — la próxima
  auditoría de arquitectura no debe "corregir" esto sin releer este ADR.
- Si algún día `seed_catalogo.py` deja de ser una herramienta de una
  sola vez y se vuelve parte de un flujo recurrente (ej. sincronización
  periódica con un ERP), debe migrar a cliente HTTP — este ADR deja de
  aplicar en ese caso.

## Verificación

```bash
# Confirma qué toca la BD directamente — debe ser SOLO scripts/, nunca dashboard/
grep -rl "from src\.database import\|from src\.modules\..*\.models import\|from src\.modules\..*\.repository import" scripts/ dashboard/
```
