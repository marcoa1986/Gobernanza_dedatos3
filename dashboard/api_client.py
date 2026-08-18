"""
dashboard/api_client.py
=========================
Envoltorio delgado sobre requests — el Dashboard NUNCA toca la base de
datos directamente, solo habla con la API vía HTTP, igual que cualquier
otro cliente. Así la frontera entre frontend y backend es real, no de
palabra.
"""

from __future__ import annotations

import os

import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TIMEOUT = 10


class APIError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"[{status_code}] {detail}")


def _manejar(resp: requests.Response) -> dict | list:
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise APIError(resp.status_code, str(detail))
    if resp.status_code == 204 or not resp.content:
        return {}
    return resp.json()


# ── Autenticación ────────────────────────────────────────────

def login(tenant_id: str, username: str, password: str) -> dict:
    resp = requests.post(
        f"{API_BASE_URL}/auth/login",
        json={"tenant_id": tenant_id, "username": username, "password": password},
        timeout=TIMEOUT,
    )
    return _manejar(resp)


def verificar_pin(temp_token: str, pin: str) -> dict:
    resp = requests.post(
        f"{API_BASE_URL}/auth/mfa/pin",
        json={"temp_token": temp_token, "pin": pin},
        timeout=TIMEOUT,
    )
    return _manejar(resp)


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Dashboard / Evidencia ────────────────────────────────────

def get_kpis(token: str, tenant_id: str) -> dict:
    resp = requests.get(
        f"{API_BASE_URL}/qa/dashboard/kpis", params={"tenant_id": tenant_id},
        headers=_headers(token), timeout=TIMEOUT,
    )
    return _manejar(resp)


def listar_evidencia(token: str, tenant_id: str, riesgo: str | None = None, limit: int = 50) -> list:
    params = {"tenant_id": tenant_id, "limit": limit}
    if riesgo:
        params["riesgo"] = riesgo
    resp = requests.get(f"{API_BASE_URL}/qa/evidencia", params=params, headers=_headers(token), timeout=TIMEOUT)
    return _manejar(resp)


def listar_pendientes_hitl(token: str, tenant_id: str) -> list:
    resp = requests.get(
        f"{API_BASE_URL}/orquestador/transacciones/pendientes", params={"tenant_id": tenant_id},
        headers=_headers(token), timeout=TIMEOUT,
    )
    return _manejar(resp)


def decidir_transaccion(token: str, transaction_id: str, decision: str, datos_modificados: dict | None = None) -> dict:
    resp = requests.post(
        f"{API_BASE_URL}/orquestador/transacciones/{transaction_id}/decision",
        json={"decision": decision, "datos_modificados": datos_modificados},
        headers=_headers(token), timeout=TIMEOUT,
    )
    return _manejar(resp)


def listar_hallazgos(token: str, tenant_id: str, periodo: str) -> list:
    resp = requests.get(
        f"{API_BASE_URL}/qa/hallazgos", params={"tenant_id": tenant_id, "periodo": periodo},
        headers=_headers(token), timeout=TIMEOUT,
    )
    return _manejar(resp)


def obtener_evidencia(token: str, transaction_id: str) -> dict:
    resp = requests.get(f"{API_BASE_URL}/qa/evidencia/{transaction_id}", headers=_headers(token), timeout=TIMEOUT)
    return _manejar(resp)


def verificar_integridad(token: str, transaction_id: str) -> dict:
    resp = requests.get(
        f"{API_BASE_URL}/qa/evidencia/{transaction_id}/verificar", headers=_headers(token), timeout=TIMEOUT,
    )
    return _manejar(resp)


def registrar_hallazgo(
    token: str, tenant_id: str, tipo: str, descripcion: str, auditor_id: str,
    evidencia_id: str | None = None, recomendacion: str = "", periodo: str = "",
) -> dict:
    resp = requests.post(
        f"{API_BASE_URL}/qa/hallazgos",
        json={
            "tenant_id": tenant_id, "evidencia_id": evidencia_id, "tipo": tipo,
            "descripcion": descripcion, "recomendacion": recomendacion,
            "auditor_id": auditor_id, "periodo": periodo,
        },
        headers=_headers(token), timeout=TIMEOUT,
    )
    return _manejar(resp)


def cerrar_hallazgo(token: str, hallazgo_id: str) -> dict:
    resp = requests.post(f"{API_BASE_URL}/qa/hallazgos/{hallazgo_id}/cerrar", headers=_headers(token), timeout=TIMEOUT)
    return _manejar(resp)


def listar_trazabilidad(token: str, tenant_id: str) -> list:
    resp = requests.get(
        f"{API_BASE_URL}/qa/trazabilidad", params={"tenant_id": tenant_id},
        headers=_headers(token), timeout=TIMEOUT,
    )
    return _manejar(resp)


# ── QR ────────────────────────────────────────────────────────

def generar_qr(token: str, transaction_id: str, tipo_documento: str = "evidencia") -> bytes:
    resp = requests.post(
        f"{API_BASE_URL}/qr/generar/{transaction_id}", params={"tipo_documento": tipo_documento},
        headers=_headers(token), timeout=TIMEOUT,
    )
    if resp.status_code >= 400:
        raise APIError(resp.status_code, resp.text)
    return resp.content


# ── Decisor / Auditor (debate) ──────────────────────────────

def listar_sectores(token: str) -> list:
    resp = requests.get(f"{API_BASE_URL}/orquestador/debate/sectores", headers=_headers(token), timeout=TIMEOUT)
    data = _manejar(resp)
    return data.get("sectores_disponibles", [])


def ejecutar_debate(token: str, problema: str, contexto: str, sectores: list[str], max_intentos: int = 3) -> dict:
    resp = requests.post(
        f"{API_BASE_URL}/orquestador/debate",
        params={"sectores": sectores} if sectores else {},
        json={"problema": problema, "contexto": contexto, "max_intentos": max_intentos},
        headers=_headers(token), timeout=60,  # el debate llama a Bedrock varias veces — más tiempo
    )
    return _manejar(resp)
