"""Tests for service and API-key endpoints."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from dev_meter.app import create_app
from dev_meter.infrastructure.database.base import Base
from dev_meter.infrastructure.database.engine import create_database_engine
from dev_meter.infrastructure.database.models import ApiKey, Service
from tests.conftest import auth_headers, make_test_settings


@pytest.fixture
def api_client(tmp_path: Path):
    """Create an API client backed by an isolated SQLite database."""
    database_url = f"sqlite:///{tmp_path / 'api.db'}"
    settings = make_test_settings(database_url)
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    engine.dispose()

    with TestClient(create_app(settings)) as client:
        yield client


def test_service_creation_and_listing(api_client: TestClient) -> None:
    """Services can be registered and listed for the development owner."""
    response = api_client.post(
        "/v1/services",
        headers=auth_headers(api_client),
        json={"name": "Text API", "upstream_base_url": "https://example.com/v1"},
    )

    assert response.status_code == 201
    service = response.json()
    assert service["name"] == "Text API"
    assert service["upstream_base_url"] == "https://example.com/v1"

    listing = api_client.get("/v1/services", headers=auth_headers(api_client))

    assert listing.status_code == 200
    assert listing.json() == [service]


def test_api_key_creation_hashing_and_metadata_listing(
    api_client: TestClient,
) -> None:
    """A key secret is returned once and never appears in stored metadata."""
    service_response = api_client.post(
        "/v1/services",
        headers=auth_headers(api_client),
        json={"name": "Embeddings", "upstream_base_url": "https://example.com"},
    )
    service_id = service_response.json()["id"]

    creation = api_client.post(
        f"/v1/services/{service_id}/keys",
        headers=auth_headers(api_client),
        json={"name": "Local development"},
    )

    assert creation.status_code == 201
    key = creation.json()
    assert key["secret"].startswith("dm_")
    assert key["key_prefix"] == key["secret"][:12]

    session = api_client.app.state.session_factory()
    stored = session.scalar(select(ApiKey).where(ApiKey.id == key["id"]))
    assert stored is not None
    assert (
        stored.secret_hash == hashlib.sha256(key["secret"].encode("utf-8")).hexdigest()
    )
    assert stored.secret_hash != key["secret"]
    session.close()

    listing = api_client.get(
        f"/v1/services/{service_id}/keys",
        headers=auth_headers(api_client),
    )

    assert listing.status_code == 200
    metadata = listing.json()[0]
    assert "secret" not in metadata
    assert "secret_hash" not in metadata
    assert metadata["key_prefix"] == key["key_prefix"]


def test_key_revocation_and_repeated_revocation(api_client: TestClient) -> None:
    """Revocation is visible in metadata and repeated revocation is not found."""
    service = api_client.post(
        "/v1/services",
        headers=auth_headers(api_client),
        json={"name": "Chat API", "upstream_base_url": "https://example.com"},
    ).json()
    key = api_client.post(
        f"/v1/services/{service['id']}/keys",
        headers=auth_headers(api_client),
        json={"name": "Gateway"},
    ).json()

    first = api_client.delete(f"/v1/keys/{key['id']}", headers=auth_headers(api_client))
    second = api_client.delete(
        f"/v1/keys/{key['id']}", headers=auth_headers(api_client)
    )

    assert first.status_code == 204
    assert second.status_code == 404
    metadata = api_client.get(
        f"/v1/services/{service['id']}/keys",
        headers=auth_headers(api_client),
    ).json()[0]
    assert metadata["revoked_at"] is not None


@pytest.mark.parametrize(
    ("payload", "detail"),
    [
        ({"name": " ", "upstream_base_url": "https://example.com"}, "name"),
        (
            {"name": "Private", "upstream_base_url": "http://127.0.0.1:8080"},
            "unsafe",
        ),
        ({"name": "No scheme", "upstream_base_url": "example.com"}, "url"),
    ],
)
def test_invalid_service_input_returns_bad_request(
    api_client: TestClient,
    payload: dict[str, str],
    detail: str,
) -> None:
    """Invalid names and unsafe or malformed URLs are rejected."""
    response = api_client.post(
        "/v1/services",
        headers=auth_headers(api_client),
        json=payload,
    )

    assert response.status_code == 422
    assert detail in response.text.lower()


def test_unknown_service_and_key_ids_return_not_found(
    api_client: TestClient,
) -> None:
    """Unknown resources do not leak data and return predictable errors."""
    unknown_id = "00000000-0000-0000-0000-000000000000"

    headers = auth_headers(api_client)
    assert (
        api_client.get(
            f"/v1/services/{unknown_id}/keys",
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        api_client.post(
            f"/v1/services/{unknown_id}/keys",
            headers=headers,
            json={"name": "Missing"},
        ).status_code
        == 404
    )
    assert (
        api_client.delete(f"/v1/keys/{unknown_id}", headers=headers).status_code == 404
    )


def test_management_resources_are_isolated_by_authenticated_identity(
    api_client: TestClient,
) -> None:
    """An authenticated administrator cannot access another identity's service."""
    session = api_client.app.state.session_factory()
    service = Service(
        id="00000000-0000-0000-0000-000000000001",
        owner_id="other-admin",
        name="Private",
        upstream_base_url="https://example.com",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(service)
    session.commit()
    session.close()
    headers = auth_headers(api_client)

    services = api_client.get(
        "/v1/services",
        headers=headers,
    )
    keys = api_client.get(
        f"/v1/services/{service.id}/keys",
        headers=headers,
    )

    assert services.json() == []
    assert keys.status_code == 404
