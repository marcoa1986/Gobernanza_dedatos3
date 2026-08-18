"""
src/modules/usuarios/router.py
================================
Endpoints de autenticación. Reemplaza el auth_router mockeado de la
versión anterior — todo aquí lee/escribe en PostgreSQL de verdad.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlmodel import Session

from src.core.security import TokenPayload, TokenResponse, get_current_user
from src.database import get_session
from src.modules.tenants.repository import TenantRepository
from src.modules.usuarios.models import UsuarioCreate, UsuarioRead
from src.modules.usuarios.service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Autenticación"])


class LoginRequest(BaseModel):
    tenant_id: uuid.UUID
    username: str
    password: str


class MFATOTPRequest(BaseModel):
    temp_token: str
    totp_code: str = Field(min_length=6, max_length=6)


class MFAPINRequest(BaseModel):
    temp_token: str
    pin: str = Field(min_length=6, max_length=6)


class TOTPConfirmRequest(BaseModel):
    codigo: str = Field(min_length=6, max_length=6)


class PINSetupRequest(BaseModel):
    pin: str = Field(min_length=6, max_length=6)


class LoginResponse(BaseModel):
    temp_token: str
    mfa_methods: list[str]
    mensaje: str


@router.post("/registro", response_model=UsuarioRead, status_code=status.HTTP_201_CREATED)
def registrar_usuario(data: UsuarioCreate, session: Session = Depends(get_session)):
    """Alta de un usuario dentro de un tenant ya existente."""
    return AuthService(session).registrar_usuario(data)


@router.post("/login", response_model=LoginResponse, summary="Paso 1: credenciales → token temporal")
def login(data: LoginRequest, session: Session = Depends(get_session)):
    temp_token = AuthService(session).login(data.tenant_id, data.username, data.password)
    return LoginResponse(
        temp_token=temp_token,
        mfa_methods=["totp", "pin"],
        mensaje="Ingresa tu código MFA para completar el acceso.",
    )


@router.post("/mfa/totp", response_model=TokenResponse, summary="Paso 2a: TOTP → JWT completo")
def verificar_totp(data: MFATOTPRequest, session: Session = Depends(get_session)):
    return AuthService(session).verificar_totp(data.temp_token, data.totp_code)


@router.post("/mfa/pin", response_model=TokenResponse, summary="Paso 2b: PIN → JWT completo")
def verificar_pin(data: MFAPINRequest, session: Session = Depends(get_session)):
    return AuthService(session).verificar_pin(data.temp_token, data.pin)


@router.post("/mfa/setup/totp", summary="Generar QR de Google Authenticator")
def setup_totp(
    session: Session = Depends(get_session),
    user: TokenPayload = Depends(get_current_user),
):
    tenant = TenantRepository(session).obtener_por_id(uuid.UUID(user.tenant_id))
    tenant_nombre = tenant.nombre if tenant else user.tenant_id
    return AuthService(session).iniciar_setup_totp(uuid.UUID(user.sub), tenant_nombre)


@router.post("/mfa/setup/totp/confirm", status_code=status.HTTP_204_NO_CONTENT, summary="Confirmar y activar TOTP")
def confirmar_totp(
    data: TOTPConfirmRequest,
    session: Session = Depends(get_session),
    user: TokenPayload = Depends(get_current_user),
):
    AuthService(session).confirmar_setup_totp(uuid.UUID(user.sub), data.codigo)


@router.post("/mfa/setup/pin", status_code=status.HTTP_204_NO_CONTENT, summary="Configurar PIN de seguridad")
def setup_pin(
    data: PINSetupRequest,
    session: Session = Depends(get_session),
    user: TokenPayload = Depends(get_current_user),
):
    AuthService(session).configurar_pin(uuid.UUID(user.sub), data.pin)
