"""
scripts/bootstrap_usuario_demo.py
====================================
El seed de catalogo.xlsx crea Evidencia y Hallazgos, pero NINGÚN usuario
— sin esto no hay con qué iniciar sesión en el Dashboard. Crea un
TENANT_ADMIN con PIN (no TOTP, para no depender de Google Authenticator
en la validación del lunes) sobre el tenant "Suministros Industriales
SMARTPROMARCO" que ya sembró seed_catalogo.py.

Uso:
    python scripts/bootstrap_usuario_demo.py
    python scripts/bootstrap_usuario_demo.py --database-url "sqlite:///demo.db"

ARQUITECTURA (ver docs/adr/ADR-006-separacion-cliente-servidor.md):
este script accede a la base de datos DIRECTAMENTE, sin pasar por la
API — es una excepción consciente para tooling administrativo de una
sola vez, no un descuido. Cualquier funcionalidad de producto debe ser
cliente HTTP, como el Dashboard en dashboard/api_client.py.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config import get_settings  # noqa: E402
from src.core.security import generar_salt, hash_password, hash_pin  # noqa: E402
from src.modules.auditoria.models import Evidencia  # noqa: F401,E402
from src.modules.qr.models import QRGenerado  # noqa: F401,E402
from src.modules.tenants.models import Tenant  # noqa: E402
from src.modules.tenants.repository import TenantRepository  # noqa: E402
from src.modules.usuarios.models import Usuario  # noqa: E402
from src.modules.usuarios.repository import UsuarioRepository  # noqa: E402

USERNAME_DEMO = "marco.admin"
PASSWORD_DEMO = "SmartPro2026!"
PIN_DEMO = "482913"


def main(database_url: str | None = None) -> None:
    settings = get_settings()
    engine = create_engine(database_url or settings.database_url, echo=False)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        tenant = TenantRepository(session).obtener_por_rfc("SUI900101AAA")
        if tenant is None:
            print("❌ No existe el tenant 'Suministros Industriales SMARTPROMARCO'.")
            print("   Corre primero: python scripts/seed_catalogo.py")
            return
        tenant_id = tenant.id  # capturado ANTES de que la sesión se cierre

        repo = UsuarioRepository(session)
        usuario = repo.obtener_por_username(tenant.id, USERNAME_DEMO)
        if usuario is None:
            from src.modules.usuarios.models import UsuarioCreate
            usuario = repo.crear(
                UsuarioCreate(
                    tenant_id=tenant.id, username=USERNAME_DEMO, email="marco@smartpromarco.io",
                    rol="TENANT_ADMIN", password=PASSWORD_DEMO,
                ),
                hashed_password=hash_password(PASSWORD_DEMO),
            )
            print(f"✅ Usuario creado: {usuario.username}")
        else:
            print(f"ℹ️  Usuario ya existía: {usuario.username}")

        salt = generar_salt()
        repo.guardar_pin(usuario.id, hash_pin(PIN_DEMO, salt), salt)
        print("✅ PIN configurado")

    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Credenciales para el Dashboard el lunes")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Tenant ID : {tenant_id}")
    print(f"  Usuario   : {USERNAME_DEMO}")
    print(f"  Password  : {PASSWORD_DEMO}")
    print(f"  PIN (MFA) : {PIN_DEMO}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  ⚠️  Solo para PoC local. Cambia esto antes de exponer el")
    print("      sistema fuera de tu máquina.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crea el usuario demo para validar el Dashboard.")
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()
    main(database_url=args.database_url)
