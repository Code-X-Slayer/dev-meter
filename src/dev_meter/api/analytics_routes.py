"""Usage analytics endpoints."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from dev_meter.api.analytics_schemas import (
    DailyUsageResponse,
    UsageSummaryResponse,
)
from dev_meter.api.dependencies import get_current_identity
from dev_meter.infrastructure.database.session import get_db_session
from dev_meter.services.analytics import (
    get_daily_usage,
    get_requests_remaining,
    get_usage_summary,
    utc_day_bounds,
)
from dev_meter.services.registry import get_service

router = APIRouter(prefix="/v1")


def get_owned_service(
    session: Session,
    owner_id: str,
    service_id: UUID,
):
    """Return an owner-visible service or raise a non-disclosing 404."""
    service = get_service(session, owner_id, service_id)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )
    return service


@router.get(
    "/services/{service_id}/usage/summary",
    response_model=UsageSummaryResponse,
)
def usage_summary(
    service_id: UUID,
    request: Request,
    session: Session = Depends(get_db_session),
    owner_id: str = Depends(get_current_identity),
) -> UsageSummaryResponse:
    """Return aggregate usage and remaining service key capacity."""
    get_owned_service(session, owner_id, service_id)
    values = get_usage_summary(
        session,
        service_id,
    )
    total = values["total_requests"]
    success_rate = values["successful_requests"] / total * 100 if total else 0.0
    return UsageSummaryResponse(
        **values,
        success_rate_percent=success_rate,
        requests_remaining=get_requests_remaining(
            session,
            service_id,
            request.app.state.default_request_limit,
        ),
        request_limit_per_key=request.app.state.default_request_limit,
    )


@router.get(
    "/services/{service_id}/usage/daily",
    response_model=list[DailyUsageResponse],
)
def daily_usage(
    service_id: UUID,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    session: Session = Depends(get_db_session),
    owner_id: str = Depends(get_current_identity),
) -> list[DailyUsageResponse]:
    """Return usage grouped by inclusive UTC date range."""
    get_owned_service(session, owner_id, service_id)
    try:
        utc_day_bounds(start_date, end_date)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    return get_daily_usage(session, service_id, start_date, end_date)
