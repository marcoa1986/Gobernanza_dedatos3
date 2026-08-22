# docker/Dockerfile — SMARTPROMARCO Gobernanza (multistage)
# ==============================================================
# Imagen única compartida por los servicios `api` y `dashboard`
# (el comando lo define compose.yaml). Multistage porque:
#   - build-essential (gcc, headers) solo se necesita para COMPILAR
#     psycopg/bcrypt — no debe viajar en la imagen final (~150MB menos)
#   - la capa de dependencias se cachea aparte del código: cambiar un
#     .py no invalida el cache de `pip install`, solo cambiar
#     requirements.txt lo hace — builds incrementales mucho más rápidos
#     en WSL2, donde I/O de disco es el cuello de botella real.

# ── STAGE 1: builder ──────────────────────────────────────────
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Solo requirements.txt aquí — maximiza el cache hit en rebuilds
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── STAGE 2: runtime ──────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Solo libpq5 (runtime), NO libpq-dev (headers de compilación) ni
# build-essential — eso es lo que reduce el tamaño de verdad.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash smartpromarco

WORKDIR /app

# Copia SOLO los paquetes ya compilados desde el builder — no el toolchain
COPY --from=builder /root/.local /home/smartpromarco/.local
ENV PATH="/home/smartpromarco/.local/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --chown=smartpromarco:smartpromarco . .

USER smartpromarco

EXPOSE 8000 8501

HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fs http://localhost:8000/health || exit 1

CMD ["uvicorn", "api_main:app", "--host", "0.0.0.0", "--port", "8000"]
