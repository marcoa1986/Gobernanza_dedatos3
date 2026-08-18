# Validación Local del PoC — Guía para este fin de semana

**Objetivo:** que el lunes tengas el stack completo corriendo en tu WSL2,
con datos reales sembrados y los 46 tests en verde, listo para demo.

**Tiempo estimado:** 20–30 minutos (la mayoría es descarga de imágenes Docker).

---

## 0. Prerrequisitos (verificar antes de empezar)

```powershell
# En PowerShell (Windows) — confirma que WSL2 es la versión por defecto
wsl --status
```

Debe decir `Versión predeterminada: 2`. Si dice 1, corrige con:
```powershell
wsl --set-default-version 2
```

Abre **Docker Desktop → Settings → General** y confirma que
**"Use the WSL 2 based engine"** está activado. Luego en
**Settings → Resources → WSL Integration**, activa la integración con tu
distro (Ubuntu, probablemente).

---

## 1. Dónde colocar el proyecto — esto importa de verdad

**No lo descomprimas en `/mnt/c/Users/...`.** El filesystem montado desde
Windows en WSL2 es notablemente más lento para I/O intensivo (y `pip
install`, `docker build`, y los tests lo son). Trabaja **dentro** del
filesystem nativo de Linux:

```bash
# Dentro de tu terminal WSL2 (Ubuntu):
mkdir -p ~/proyectos && cd ~/proyectos
```

Copia el `.zip` desde Windows hacia ahí (puedes arrastrarlo a
`\\wsl$\Ubuntu\home\<tu_usuario>\proyectos\` desde el Explorador, o usar
`cp` si ya está accesible vía `/mnt/c/Users/.../Downloads/`).

```bash
unzip smartpromarco-gobernanza-modulo3-qr.zip -d smartpromarco-gobernanza
cd smartpromarco-gobernanza
```

---

## 2. Configurar variables de entorno

```bash
cp .env.example .env
nano .env   # o code .env si tienes VS Code + extensión WSL
```

Para la validación local **no necesitas** credenciales AWS reales todavía
— el Agente Auditor solo se invoca cuando llamas a `/orquestador/debate`
o al pipeline de transacciones. Para probar el resto del sistema (Tenants,
Evidencia, QR, Dashboard), el `.env` de ejemplo ya alcanza. Sí cambia:

```bash
POSTGRES_PASSWORD=<algo_tuyo_no_el_de_ejemplo>
JWT_SECRET=<corre: openssl rand -hex 32>
```

---

## 3. Levantar el stack

```bash
# Solo los servicios del PoC (postgres, redis, adminer, api, dashboard):
docker compose up -d --build
```

La primera vez tarda más (descarga imágenes base + compila el Dockerfile
multistage). Builds siguientes son mucho más rápidos por el cache de capas.

**Verifica que todo está sano:**
```bash
docker compose ps
```
Los 5 servicios deben decir `running` (o `healthy` los que tienen
healthcheck: `postgres`, `redis`, `api`).

Si `api` no llega a `healthy`, revisa logs:
```bash
docker compose logs -f api
```

---

## 4. Verificar que la API responde

```bash
curl http://localhost:8000/health
```
Debe responder `{"status":"ok",...}`. Si prefieres el navegador:
**http://localhost:8000/docs** — deberías ver **22 endpoints** documentados
(Tenants, Auth, Auditoría, QR, Decisor/Auditor).

---

## 5. Sembrar datos reales (Suministros Industriales)

```bash
docker compose exec api python scripts/seed_catalogo.py
```

Debe terminar con algo como:
```
✅ 164 Evidencias registradas — HITL=58 HOTL=102 HOOTL=4
✅ 4 Hallazgos registrados
```

Si prefieres correrlo fuera de Docker (contra la Postgres del contenedor,
expuesta en `localhost:5432`):
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/seed_catalogo.py --database-url "postgresql+psycopg://smartpromarco:<tu_password>@localhost:5432/smartpromarco"
```

---

## 6. Correr la suite de pruebas

```bash
docker compose exec api pytest tests/ -v
```
Debe terminar en **46 passed**. Si algo falla, es la primera señal real de
que algo en tu entorno difiere del mío — copia el traceback completo.

---

## 7. Acceder a todo

| Qué | URL |
|---|---|
| API + Swagger | http://localhost:8000/docs |
| Dashboard (Streamlit) | http://localhost:8501 |
| Adminer (inspección de BD) | http://localhost:8081 — sistema `PostgreSQL`, servidor `postgres`, usuario/password de tu `.env` |

---

## 8. Checklist de validación para el lunes

Marca cada uno antes de la demo:

- [ ] `docker compose ps` — los 5 servicios en `running`/`healthy`
- [ ] `curl localhost:8000/health` responde `200 ok`
- [ ] `/docs` muestra 22 endpoints
- [ ] Seed corrió: 164 Evidencias, HITL=58/HOTL=102/HOOTL=4
- [ ] `pytest` → 46 passed
- [ ] Dashboard carga en `:8501` y muestra las 5 secciones de KPIs
- [ ] Al menos 1 transacción HITL visible con botones Aprobar/Rechazar/Modificar
- [ ] Un QR generado se puede escanear (o abrir la URL manualmente) y resuelve a la evidencia correcta

## Troubleshooting común en WSL2

| Síntoma | Causa probable | Solución |
|---|---|---|
| `docker compose up` muy lento | Proyecto en `/mnt/c/...` | Muévelo a `~/proyectos/` (Sección 1) |
| Puerto 8000/8501 "already in use" | Otro proceso Windows lo ocupa | `netstat -ano \| findstr :8000` en PowerShell, o cambia el puerto en `compose.yaml` |
| Docker Desktop no ve tu distro WSL | Integración no activada | Settings → Resources → WSL Integration |
| Contenedor `api` reinicia en loop | Falta variable en `.env` o typo | `docker compose logs api` — el traceback dice exactamente qué falta |
| `pip install` lentísimo la primera vez | Normal — está compilando psycopg/bcrypt | Solo pasa una vez; el layer se cachea |
