"""Response schemas for usage analytics."""

from datetime import date

from pydantic import BaseModel, Field


class UsageSummaryResponse(BaseModel):
    """Aggregated usage for one service."""

    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate_percent: float
    average_duration_ms: float
    requests_remaining: int
    request_limit_per_key: int


class DailyUsageResponse(BaseModel):
    """Aggregated usage for one UTC calendar day."""

    date: date
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_duration_ms: float


class UsageDateRange(BaseModel):
    """Validated optional inclusive UTC date filters."""

    start_date: date | None = Field(default=None)
    end_date: date | None = Field(default=None)
