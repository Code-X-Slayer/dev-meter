"""Usage analytics queries."""

from datetime import UTC, date, datetime, time, timedelta
from typing import TypedDict
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from dev_meter.infrastructure.database.models import ApiKey, UsageRecord
from dev_meter.services.gateway import utc_now


class UsageSummaryValues(TypedDict):
    """Aggregated usage summary values."""

    total_requests: int
    successful_requests: int
    failed_requests: int
    average_duration_ms: float


class DailyUsageValues(TypedDict):
    """Aggregated values for one UTC day."""

    date: date
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_duration_ms: float


def utc_day_bounds(
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[datetime, datetime]:
    """Return an inclusive date range as a half-open UTC datetime range."""
    start = start_date or date.min
    end = end_date or utc_now().date()
    if start > end:
        raise ValueError("start_date must not be after end_date")
    start_datetime = datetime.combine(start, time.min, tzinfo=UTC)
    end_datetime = datetime.combine(end + timedelta(days=1), time.min, tzinfo=UTC)
    return start_datetime, end_datetime


def get_usage_summary(
    session: Session,
    service_id: UUID,
) -> UsageSummaryValues:
    """Aggregate service usage and remaining active-key capacity."""
    totals = session.execute(
        select(
            func.count(UsageRecord.id),
            func.coalesce(
                func.sum(case((UsageRecord.succeeded.is_(True), 1), else_=0)),
                0,
            ),
            func.coalesce(
                func.avg(UsageRecord.duration_ms),
                0,
            ),
        ).where(UsageRecord.service_id == str(service_id))
    ).one()
    total_requests = int(totals[0] or 0)
    successful_requests = int(totals[1] or 0)
    return {
        "total_requests": total_requests,
        "successful_requests": successful_requests,
        "failed_requests": total_requests - successful_requests,
        "average_duration_ms": float(totals[2] or 0),
    }


def get_requests_remaining(
    session: Session,
    service_id: UUID,
    request_limit: int,
) -> int:
    """Sum remaining daily capacity across active keys for a service."""
    start, end = utc_day_bounds()
    key_counts = session.execute(
        select(
            ApiKey.id,
            func.count(UsageRecord.id),
        )
        .outerjoin(
            UsageRecord,
            (UsageRecord.api_key_id == ApiKey.id)
            & (UsageRecord.created_at >= start)
            & (UsageRecord.created_at < end),
        )
        .where(
            ApiKey.service_id == str(service_id),
            ApiKey.revoked_at.is_(None),
        )
        .group_by(ApiKey.id)
    )
    return sum(max(request_limit - int(count), 0) for _, count in key_counts)


def get_daily_usage(
    session: Session,
    service_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[DailyUsageValues]:
    """Aggregate service usage by inclusive UTC calendar date."""
    start, end = utc_day_bounds(start_date, end_date)
    usage_date = func.date(UsageRecord.created_at)
    rows = session.execute(
        select(
            usage_date,
            func.count(UsageRecord.id),
            func.coalesce(
                func.sum(case((UsageRecord.succeeded.is_(True), 1), else_=0)),
                0,
            ),
            func.coalesce(func.avg(UsageRecord.duration_ms), 0),
        )
        .where(
            UsageRecord.service_id == str(service_id),
            UsageRecord.created_at >= start,
            UsageRecord.created_at < end,
        )
        .group_by(usage_date)
        .order_by(usage_date)
    )
    results: list[DailyUsageValues] = []
    for usage_day, total, successful, average in rows:
        parsed_day = (
            usage_day
            if isinstance(usage_day, date)
            else date.fromisoformat(str(usage_day))
        )
        total_requests = int(total)
        successful_requests = int(successful or 0)
        results.append(
            {
                "date": parsed_day,
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "failed_requests": total_requests - successful_requests,
                "average_duration_ms": float(average or 0),
            }
        )
    return results
