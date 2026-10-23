"""Request and response schemas for service and API-key endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator

from dev_meter.core.validation import validate_upstream_url


class ServiceCreate(BaseModel):
    """Payload for registering an upstream service."""

    name: str = Field(min_length=1, max_length=100)
    upstream_base_url: AnyHttpUrl

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Reject names made only of whitespace."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("service name must not be blank")
        return normalized

    @field_validator("upstream_base_url")
    @classmethod
    def validate_base_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        """Reject unsafe upstream destinations."""
        validate_upstream_url(str(value))
        return value


class ServiceResponse(BaseModel):
    """Public service representation."""

    id: UUID
    name: str
    upstream_base_url: str
    created_at: datetime
    updated_at: datetime


class ApiKeyCreate(BaseModel):
    """Payload for creating an API key."""

    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Reject key names made only of whitespace."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("key name must not be blank")
        return normalized


class ApiKeyResponse(BaseModel):
    """API-key metadata, optionally including the one-time secret."""

    id: UUID
    service_id: UUID
    name: str
    key_prefix: str
    created_at: datetime
    revoked_at: datetime | None
    secret: str | None = None


class ApiKeyMetadata(BaseModel):
    """API-key metadata that never contains a secret."""

    id: UUID
    service_id: UUID
    name: str
    key_prefix: str
    created_at: datetime
    revoked_at: datetime | None
