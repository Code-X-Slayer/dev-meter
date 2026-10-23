"""Administrator authentication and signed access-token operations."""

from datetime import UTC, datetime, timedelta
from secrets import compare_digest

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from dev_meter.core.config import Settings

password_hasher = PasswordHasher()


def verify_admin_credentials(
    settings: Settings,
    username: str,
    password: str,
) -> bool:
    """Verify configured administrator credentials without disclosing details."""
    if (
        settings.admin_username is None
        or settings.admin_password_hash is None
        or not compare_digest(username, settings.admin_username)
    ):
        return False
    try:
        return password_hasher.verify(
            settings.admin_password_hash.get_secret_value(),
            password,
        )
    except InvalidHashError, VerificationError, VerifyMismatchError:
        return False


def create_access_token(settings: Settings, username: str) -> tuple[str, datetime]:
    """Create a signed token and return its expiry timestamp."""
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.jwt_expiry_minutes)
    token = jwt.encode(
        {
            "sub": username,
            "exp": expires_at,
        },
        _jwt_secret(settings),
        algorithm="HS256",
    )
    return token, expires_at


def decode_access_token(settings: Settings, token: str) -> str:
    """Validate a signed token and return its administrator identity."""
    payload = jwt.decode(token, _jwt_secret(settings), algorithms=["HS256"])
    username = payload.get("sub")
    if not isinstance(username, str) or not username:
        raise jwt.InvalidTokenError("missing subject")
    return username


def _jwt_secret(settings: Settings) -> str:
    if settings.jwt_secret is None:
        raise ValueError("JWT authentication is not configured")
    return settings.jwt_secret.get_secret_value()
