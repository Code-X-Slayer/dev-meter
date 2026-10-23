"""HTTP dependencies for authenticated management requests."""

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from dev_meter.services.auth import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_identity(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    """Validate the management bearer token and return its username."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    try:
        return decode_access_token(request.app.state.settings, credentials.credentials)
    except jwt.InvalidTokenError, ValueError:
        raise _unauthorized() from None


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
