"""
tests/test_security.py
========================
Cubre RN-SEC-001 (RBAC por permiso), RN-SEC-002 (hashing de PIN con salt),
RN-SEC-003 (TOTP con ventana de tolerancia).
"""

from __future__ import annotations

import pyotp

from src.core.security import (
    ROLE_PERMISSIONS,
    TOTPManager,
    UserRole,
    hash_pin,
    hash_password,
    has_permission,
    verify_password,
    verify_pin,
)


class TestRBAC:
    """RN-SEC-001: cada rol solo tiene acceso a los permisos que le corresponden."""

    def test_TC_SEC_001_super_admin_tiene_acceso_total(self):
        assert has_permission(UserRole.SUPER_ADMIN, "cualquier:cosa") is True

    def test_TC_SEC_002_viewer_no_puede_escribir_evidencia(self):
        assert has_permission(UserRole.VIEWER, "evidencia:write") is False

    def test_TC_SEC_003_operador_puede_responder_hitl(self):
        assert has_permission(UserRole.OPERADOR, "hitl:respond") is True

    def test_TC_SEC_004_auditor_interno_no_administra_usuarios(self):
        assert has_permission(UserRole.AUDITOR_INTERNO, "usuarios:admin") is False

    def test_TC_SEC_011_supervisor_puede_responder_hitl_de_todo_el_tenant(self):
        assert has_permission(UserRole.SUPERVISOR, "hitl:respond") is True

    def test_TC_SEC_012_supervisor_no_administra_usuarios_ni_tenant(self):
        """El límite explícito: Supervisor respalda/escala, no configura — eso es TENANT_ADMIN."""
        assert has_permission(UserRole.SUPERVISOR, "usuarios:admin") is False
        assert has_permission(UserRole.SUPERVISOR, "auditoria:write") is False

    def test_TC_SEC_005_todos_los_roles_tienen_lista_de_permisos_definida(self):
        for rol in UserRole:
            assert rol in ROLE_PERMISSIONS


class TestHashing:
    def test_TC_SEC_006_password_hash_no_es_reversible_por_comparacion_directa(self):
        hashed = hash_password("mi-password-segura")
        assert hashed != "mi-password-segura"
        assert verify_password("mi-password-segura", hashed) is True
        assert verify_password("password-incorrecta", hashed) is False

    def test_TC_SEC_007_pin_hash_depende_del_salt(self):
        """RN-SEC-002: el mismo PIN con distinto salt produce hashes distintos."""
        h1 = hash_pin("123456", "salt-a")
        h2 = hash_pin("123456", "salt-b")
        assert h1 != h2
        assert verify_pin("123456", "salt-a", h1) is True
        assert verify_pin("999999", "salt-a", h1) is False


class TestTOTP:
    def test_TC_SEC_008_codigo_valido_pasa_verificacion(self):
        """RN-SEC-003."""
        secret = TOTPManager.generate_secret()
        codigo_actual = pyotp.TOTP(secret).now()
        assert TOTPManager.verify_code(secret, codigo_actual) is True

    def test_TC_SEC_009_codigo_incorrecto_falla(self):
        secret = TOTPManager.generate_secret()
        assert TOTPManager.verify_code(secret, "000000") is False

    def test_TC_SEC_010_backup_codes_son_unicos(self):
        codigos = TOTPManager.generate_backup_codes(n=8)
        assert len(codigos) == 8
        assert len(set(codigos)) == 8
