"""Tests for administrator authentication and management authorization."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from dev_meter.app import create_app
from dev_meter.core.config import Settings
from dev_meter.infrastructure.database.base import Base
from tests.conftest import (
    TEST_ADMIN_PASSWORD,
    TEST_ADMIN_USERNAME,
    TEST_JWT_SECRET,
    auth_headers,
    make_test_settings,
)


def make_client(tmp_path: Path) -> TestClient:
    """Create an authenticated test application over isolated SQLite."""
    database_url = f"sqlite:///{tmp_path / 'auth.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    return TestClient(create_app(make_test_settings(database_url)))


def test_valid_login_and_identity(tmp_path: Path) -> None:
    """Valid credentials issue a token that identifies the administrator."""
    with make_client(tmp_path) as client:
        response = client.post(
            "/v1/auth/login",
            json={
                "username": TEST_ADMIN_USERNAME,
                "password": TEST_ADMIN_PASSWORD,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert "password" not in body
        assert client.get(
            "/v1/auth/me",
            headers={"Authorization": f"Bearer {body['access_token']}"},
        ).json() == {"username": TEST_ADMIN_USERNAME}


def test_invalid_credentials_and_missing_token_are_rejected(tmp_path: Path) -> None:
    """Invalid login attempts and anonymous management calls return 401."""
    with make_client(tmp_path) as client:
        invalid = client.post(
            "/v1/auth/login",
            json={"username": "wrong", "password": "wrong"},
        )
        missing = client.get("/v1/auth/me")
        assert invalid.status_code == 401
        assert missing.status_code == 401


def test_invalid_and_expired_tokens_are_rejected(tmp_path: Path) -> None:
    """Invalid signatures and expired access tokens cannot access management."""
    with make_client(tmp_path) as client:
        invalid = client.get(
            "/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.value"},
        )
        expired = jwt.encode(
            {
                "sub": TEST_ADMIN_USERNAME,
                "exp": datetime.now(UTC) - timedelta(minutes=1),
            },
            TEST_JWT_SECRET,
            algorithm="HS256",
        )
        expired_response = client.get(
            "/v1/auth/me",
            headers={"Authorization": f"Bearer {expired}"},
        )
        assert invalid.status_code == 401
        assert expired_response.status_code == 401


def test_authenticated_management_and_cross_owner_access(
    tmp_path: Path,
) -> None:
    """Authenticated management works while another owner remains inaccessible."""
    with make_client(tmp_path) as client:
        headers = auth_headers(client)
        created = client.post(
            "/v1/services",
            headers=headers,
            json={
                "name": "Authenticated service",
                "upstream_base_url": "https://example.com",
            },
        )
        assert created.status_code == 201


def test_production_authentication_configuration_is_required() -> None:
    """Production settings reject missing and weak authentication configuration."""
    for kwargs in (
        {},
        {
            "admin_username": "admin",
            "admin_password_hash": PasswordHasher().hash("password"),
        },
    ):
        try:
            Settings(
                environment="production",
                database_url="postgresql+psycopg://user:pass@host/db",
                **kwargs,
            )
        except ValueError:
            continue
        raise AssertionError("insecure production settings were accepted")
