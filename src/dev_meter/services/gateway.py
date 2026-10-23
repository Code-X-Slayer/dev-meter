"""Gateway authentication, quota, forwarding, and usage operations."""

import time as time_module
from datetime import UTC, datetime, time, timedelta
from uuid import UUID, uuid4

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dev_meter.infrastructure.database.models import ApiKey, Service, UsageRecord
from dev_meter.services.registry import hash_api_key_secret, utc_now


def find_active_api_key(
    session: Session,
    service_id: UUID,
    secret: str,
) -> ApiKey | None:
    """Find an active key matching both the secret and service."""
    return session.scalar(
        select(ApiKey).where(
            ApiKey.service_id == str(service_id),
            ApiKey.secret_hash == hash_api_key_secret(secret),
            ApiKey.revoked_at.is_(None),
        )
    )


def count_requests_today(session: Session, api_key_id: str) -> int:
    """Count this key's usage records in the current UTC calendar day."""
    now = utc_now()
    start = datetime.combine(now.date(), time.min, tzinfo=UTC)
    end = start + timedelta(days=1)
    return int(
        session.scalar(
            select(func.count(UsageRecord.id)).where(
                UsageRecord.api_key_id == api_key_id,
                UsageRecord.created_at >= start,
                UsageRecord.created_at < end,
            )
        )
        or 0
    )


def record_usage(
    session: Session,
    api_key: ApiKey,
    service: Service,
    status_code: int | None,
    duration_ms: int,
    succeeded: bool,
) -> UsageRecord:
    """Persist one authenticated gateway forwarding attempt."""
    record = UsageRecord(
        id=str(uuid4()),
        api_key_id=api_key.id,
        service_id=service.id,
        created_at=utc_now(),
        upstream_status_code=status_code,
        duration_ms=duration_ms,
        succeeded=succeeded,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


async def forward_request(
    client: httpx.AsyncClient,
    service: Service,
    body: object,
    headers: dict[str, str],
) -> tuple[httpx.Response | None, int, bool]:
    """Forward a JSON request using the registered upstream URL."""
    started = time_module.perf_counter()
    try:
        response = await client.post(
            service.upstream_base_url,
            json=body,
            headers=headers,
            follow_redirects=False,
        )
    except httpx.RequestError:
        duration_ms = int((time_module.perf_counter() - started) * 1000)
        return None, duration_ms, False

    duration_ms = int((time_module.perf_counter() - started) * 1000)
    return response, duration_ms, 200 <= response.status_code < 400
