"""Authentication request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Administrator login credentials."""

    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class LoginResponse(BaseModel):
    """Signed administrator access token."""

    access_token: str
    token_type: str
    expires_at: datetime


class IdentityResponse(BaseModel):
    """Authenticated administrator identity."""

    username: str
