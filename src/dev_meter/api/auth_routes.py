"""Administrator authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from dev_meter.api.auth_schemas import (
    IdentityResponse,
    LoginRequest,
    LoginResponse,
)
from dev_meter.api.dependencies import get_current_identity
from dev_meter.services.auth import create_access_token, verify_admin_credentials

router = APIRouter(prefix="/v1/auth")


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request) -> LoginResponse:
    """Authenticate the configured administrator."""
    settings = request.app.state.settings
    if (
        settings.admin_username is None
        or settings.admin_password_hash is None
        or settings.jwt_secret is None
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )
    if not verify_admin_credentials(settings, payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expires_at = create_access_token(settings, payload.username)
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_at=expires_at,
    )


@router.get("/me", response_model=IdentityResponse)
def me(username: str = Depends(get_current_identity)) -> IdentityResponse:
    """Return the identity represented by a valid access token."""
    return IdentityResponse(username=username)
