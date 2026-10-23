"""Tests for usage analytics endpoints."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dev_meter.app import create_app
from dev_meter.infrastructure.database.base import Base
from dev_meter.infrastructure.database.engine import create_database_engine
from dev_meter.infrastructure.database.models import Service, UsageRecord
from tests.conftest import auth_headers, make_test_settings


@pytest.fixture
def analytics_client(tmp_path: Path):
    """Create an analytics client backed by isolated SQLite."""
    database_url = f"sqlite:///{tmp_path / 'analytics.db'}"
    settings = make_test_settings(database_url)
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    with TestClient(create_app(settings)) as client:
        yield client


def create_service_and_key(
    client: TestClient,
    owner: str = "development-owner",
) -> tuple[str, str]:
    """Create an owned service and return its ID and key ID."""
    service = client.post(
        "/v1/services",
        headers=auth_headers(client),
        json={
            "name": f"Analytics {owner}",
            "upstream_base_url": "https://analytics.example",
        },
    ).json()
    key = client.post(
        f"/v1/services/{service['id']}/keys",
        headers=auth_headers(client),
        json={"name": "Analytics key"},
    ).json()
    return service["id"], key["id"]


def add_usage(
    client: TestClient,
    service_id: str,
    key_id: str,
    created_at: datetime,
    succeeded: bool,
    duration_ms: int,
    status_code: int,
) -> None:
    """Insert a usage record for deterministic analytics assertions."""
    session = client.app.state.session_factory()
    session.add(
        UsageRecord(
            id=f"{created_at.timestamp()}-{duration_ms}-{status_code}",
            api_key_id=key_id,
            service_id=service_id,
            created_at=created_at,
            upstream_status_code=status_code,
            duration_ms=duration_ms,
            succeeded=succeeded,
        )
    )
    session.commit()
    session.close()


def test_summary_aggregates_mixed_usage(
    analytics_client: TestClient,
) -> None:
    """Summary reports totals, rates, averages, and remaining capacity."""
    service_id, key_id = create_service_and_key(analytics_client)
    day = datetime(2026, 10, 22, 10, tzinfo=UTC)
    add_usage(analytics_client, service_id, key_id, day, True, 100, 200)
    add_usage(
        analytics_client,
        service_id,
        key_id,
        day + timedelta(minutes=1),
        False,
        300,
        502,
    )

    response = analytics_client.get(
        f"/v1/services/{service_id}/usage/summary",
        headers=auth_headers(analytics_client),
    )

    assert response.status_code == 200
    assert response.json() == {
        "total_requests": 2,
        "successful_requests": 1,
        "failed_requests": 1,
        "success_rate_percent": 50.0,
        "average_duration_ms": 200.0,
        "requests_remaining": 98,
        "request_limit_per_key": 100,
    }


def test_daily_usage_groups_and_filters_inclusive_dates(
    analytics_client: TestClient,
) -> None:
    """Daily usage groups UTC dates and includes both filter endpoints."""
    service_id, key_id = create_service_and_key(analytics_client)
    add_usage(
        analytics_client,
        service_id,
        key_id,
        datetime(2026, 10, 20, 23, 59, tzinfo=UTC),
        True,
        100,
        200,
    )
    add_usage(
        analytics_client,
        service_id,
        key_id,
        datetime(2026, 10, 21, 0, 1, tzinfo=UTC),
        False,
        300,
        500,
    )
    add_usage(
        analytics_client,
        service_id,
        key_id,
        datetime(2026, 10, 22, 0, 1, tzinfo=UTC),
        True,
        200,
        200,
    )

    response = analytics_client.get(
        f"/v1/services/{service_id}/usage/daily",
        headers=auth_headers(analytics_client),
        params={"start_date": "2026-10-20", "end_date": "2026-10-21"},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "date": "2026-10-20",
            "total_requests": 1,
            "successful_requests": 1,
            "failed_requests": 0,
            "average_duration_ms": 100.0,
        },
        {
            "date": "2026-10-21",
            "total_requests": 1,
            "successful_requests": 0,
            "failed_requests": 1,
            "average_duration_ms": 300.0,
        },
    ]


def test_empty_usage_and_invalid_ranges(
    analytics_client: TestClient,
) -> None:
    """Empty services return zero summaries and invalid dates return 422."""
    service_id, _ = create_service_and_key(analytics_client)

    headers = auth_headers(analytics_client)
    summary = analytics_client.get(
        f"/v1/services/{service_id}/usage/summary",
        headers=headers,
    )
    daily = analytics_client.get(
        f"/v1/services/{service_id}/usage/daily",
        headers=headers,
    )
    invalid = analytics_client.get(
        f"/v1/services/{service_id}/usage/daily",
        headers=headers,
        params={"start_date": "2026-10-22", "end_date": "2026-10-20"},
    )

    assert summary.json()["total_requests"] == 0
    assert summary.json()["success_rate_percent"] == 0.0
    assert daily.json() == []
    assert invalid.status_code == 422


def test_unknown_and_other_owner_services_are_not_accessible(
    analytics_client: TestClient,
) -> None:
    """Analytics hides unknown and cross-owner service IDs."""
    service_id, _ = create_service_and_key(analytics_client)
    session = analytics_client.app.state.session_factory()
    service = session.get(Service, service_id)
    assert service is not None
    service.owner_id = "other-admin"
    session.commit()
    session.close()
    unknown = "00000000-0000-0000-0000-000000000000"

    other_owner = analytics_client.get(
        f"/v1/services/{service_id}/usage/summary",
        headers=auth_headers(analytics_client),
    )
    missing = analytics_client.get(
        f"/v1/services/{unknown}/usage/daily",
        headers=auth_headers(analytics_client),
    )

    assert other_owner.status_code == 404
    assert missing.status_code == 404
