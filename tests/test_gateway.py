"""Tests for the protected gateway and usage metering."""

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from dev_meter.app import create_app
from dev_meter.infrastructure.database.base import Base
from dev_meter.infrastructure.database.engine import create_database_engine
from dev_meter.infrastructure.database.models import UsageRecord
from tests.conftest import auth_headers, make_test_settings


@pytest.fixture
def gateway_client(tmp_path: Path):
    """Create an API client with an isolated SQLite database."""
    database_url = f"sqlite:///{tmp_path / 'gateway.db'}"
    settings = make_test_settings(database_url)
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    with TestClient(create_app(settings)) as client:
        yield client


def create_service_and_key(client: TestClient) -> tuple[str, str]:
    """Create a service and return its ID and plaintext API key."""
    service = client.post(
        "/v1/services",
        headers=auth_headers(client),
        json={"name": "Gateway service", "upstream_base_url": "https://upstream.test"},
    ).json()
    key = client.post(
        f"/v1/services/{service['id']}/keys",
        headers=auth_headers(client),
        json={"name": "Gateway key"},
    ).json()
    return service["id"], key["secret"]


def use_transport(
    client: TestClient,
    handler,
) -> None:
    """Replace the lifespan client with a mocked upstream transport."""
    client.app.state.http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    )


def test_gateway_forwards_json_and_selected_headers(
    gateway_client: TestClient,
) -> None:
    """The gateway forwards the registered URL and body without authorization."""
    service_id, secret = create_service_and_key(gateway_client)
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["body"] = request.read()
        observed["authorization"] = request.headers.get("authorization")
        observed["content_type"] = request.headers.get("content-type")
        return httpx.Response(201, json={"result": "ok"})

    use_transport(gateway_client, handler)
    response = gateway_client.post(
        f"/v1/gateway/{service_id}",
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
        },
        json={"prompt": "hello"},
    )

    assert response.status_code == 201
    assert response.json() == {"result": "ok"}
    assert observed == {
        "url": "https://upstream.test/",
        "body": b'{"prompt":"hello"}',
        "authorization": None,
        "content_type": "application/json",
    }


@pytest.mark.parametrize(
    "authorization",
    [None, "Basic abc", "Bearer ", "Bearer invalid"],
)
def test_gateway_rejects_invalid_authentication(
    gateway_client: TestClient,
    authorization: str | None,
) -> None:
    """Missing and malformed keys return HTTP 401."""
    service_id, _ = create_service_and_key(gateway_client)
    headers = {} if authorization is None else {"Authorization": authorization}

    response = gateway_client.post(
        f"/v1/gateway/{service_id}",
        headers=headers,
        json={"prompt": "hello"},
    )

    assert response.status_code == 401


def test_gateway_rejects_revoked_and_wrong_service_keys(
    gateway_client: TestClient,
) -> None:
    """Revoked and service-mismatched keys cannot authenticate."""
    service_id, secret = create_service_and_key(gateway_client)
    other_service = gateway_client.post(
        "/v1/services",
        headers=auth_headers(gateway_client),
        json={"name": "Other service", "upstream_base_url": "https://other.test"},
    ).json()
    revoked_key = gateway_client.post(
        f"/v1/services/{service_id}/keys",
        headers=auth_headers(gateway_client),
        json={"name": "Revoked"},
    ).json()
    gateway_client.delete(
        f"/v1/keys/{revoked_key['id']}",
        headers=auth_headers(gateway_client),
    )

    revoked_response = gateway_client.post(
        f"/v1/gateway/{service_id}",
        headers={"Authorization": f"Bearer {revoked_key['secret']}"},
        json={},
    )
    wrong_service_response = gateway_client.post(
        f"/v1/gateway/{other_service['id']}",
        headers={"Authorization": f"Bearer {secret}"},
        json={},
    )

    assert revoked_response.status_code == 401
    assert wrong_service_response.status_code == 401


def test_gateway_quota_returns_429_without_recording_rejected_request(
    gateway_client: TestClient,
) -> None:
    """The configured daily limit blocks the next request."""
    gateway_client.app.state.default_request_limit = 1
    service_id, secret = create_service_and_key(gateway_client)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    use_transport(gateway_client, handler)
    headers = {"Authorization": f"Bearer {secret}"}
    first = gateway_client.post(f"/v1/gateway/{service_id}", headers=headers, json={})
    second = gateway_client.post(f"/v1/gateway/{service_id}", headers=headers, json={})

    assert first.status_code == 200
    assert second.status_code == 429
    session = gateway_client.app.state.session_factory()
    assert session.scalar(select(func.count(UsageRecord.id))) == 1
    session.close()


@pytest.mark.parametrize("error_type", [httpx.ConnectError, httpx.ReadTimeout])
def test_gateway_records_upstream_failure(
    gateway_client: TestClient,
    error_type: type[httpx.RequestError],
) -> None:
    """Connection and timeout failures return 502 and record the attempt."""
    service_id, secret = create_service_and_key(gateway_client)

    def handler(request: httpx.Request) -> httpx.Response:
        raise error_type("unavailable", request=request)

    use_transport(gateway_client, handler)
    response = gateway_client.post(
        f"/v1/gateway/{service_id}",
        headers={"Authorization": f"Bearer {secret}"},
        json={"prompt": "hello"},
    )

    assert response.status_code == 502
    session = gateway_client.app.state.session_factory()
    record = session.scalar(select(UsageRecord))
    assert record is not None
    assert record.upstream_status_code is None
    assert record.succeeded is False
    assert record.duration_ms >= 0
    session.close()
