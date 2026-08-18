"""
api_main.py
============
Shim de compatibilidad. Tu launch.json de VS Code ya apunta a
`api_main:app` — en vez de pedirte cambiar esa configuración, la
respetamos: este archivo solo reexporta la app real desde
src/api/main.py (la composition root de verdad).

Ejecutar:
    uvicorn api_main:app --reload --port 8000
"""

from src.api.main import app

__all__ = ["app"]
