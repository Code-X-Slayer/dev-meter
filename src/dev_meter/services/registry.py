"""Service and API-key registration operations."""

import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from dev_meter.infrastructure.database.models import ApiKey, Service


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def hash_api_key_secret(secret: str) -> str:
    """Hash an API-key secret for storage or lookup."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def create_service(
    session: Session,
    owner_id: str,
    name: str,
    upstream_base_url: str,
) -> Service:
    """Create and commit a service owned by the authenticated identity."""
    now = utc_now()
    service = Service(
        id=str(uuid4()),
        owner_id=owner_id,
        name=name,
        upstream_base_url=upstream_base_url,
        created_at=now,
        updated_at=now,
    )
    session.add(service)
    session.commit()
    session.refresh(service)
    return service


def list_services(session: Session, owner_id: str) -> list[Service]:
    """List services belonging to the authenticated identity."""
    return list(
        session.scalars(
            select(Service)
            .where(Service.owner_id == owner_id)
            .order_by(Service.created_at, Service.id)
        )
    )


def get_service(
    session: Session,
    owner_id: str,
    service_id: UUID,
) -> Service | None:
    """Find one service belonging to the authenticated identity."""
    return session.scalar(
        select(Service).where(
            Service.id == str(service_id),
            Service.owner_id == owner_id,
        )
    )


def create_api_key(
    session: Session,
    service: Service,
    name: str,
) -> tuple[ApiKey, str]:
    """Create a key, returning its model and one-time plaintext secret."""
    secret = f"dm_{secrets.token_urlsafe(32)}"
    key = ApiKey(
        id=str(uuid4()),
        service_id=service.id,
        name=name,
        key_prefix=secret[:12],
        secret_hash=hash_api_key_secret(secret),
        created_at=utc_now(),
    )
    session.add(key)
    session.commit()
    session.refresh(key)
    return key, secret


def list_api_keys(
    session: Session,
    service: Service,
) -> list[ApiKey]:
    """List key metadata for a service."""
    return list(
        session.scalars(
            select(ApiKey)
            .where(ApiKey.service_id == service.id)
            .order_by(ApiKey.created_at, ApiKey.id)
        )
    )


def revoke_api_key(
    session: Session,
    owner_id: str,
    key_id: UUID,
) -> bool:
    """Revoke an owned key and report whether it was active."""
    key = session.scalar(
        select(ApiKey)
        .join(Service)
        .where(ApiKey.id == str(key_id), Service.owner_id == owner_id)
    )
    if key is None or key.revoked_at is not None:
        return False
    key.revoked_at = utc_now()
    session.commit()
    return True
