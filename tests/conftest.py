"""Shared test authentication configuration."""

from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from dev_meter.core.config import Settings

TEST_ADMIN_USERNAME = "admin"
TEST_ADMIN_PASSWORD = "test-password"
TEST_JWT_SECRET = "test-jwt-secret-that-is-long-enough"


def make_test_settings(database_url: str) -> Settings:
    """Build settings with isolated test-only administrator credentials."""
    return Settings(
        database_url=database_url,
        environment="testing",
        admin_username=TEST_ADMIN_USERNAME,
        admin_password_hash=PasswordHasher().hash(TEST_ADMIN_PASSWORD),
        jwt_secret=TEST_JWT_SECRET,
    )


def auth_headers(client: TestClient) -> dict[str, str]:
    """Return a bearer header for the configured test administrator."""
    response = client.post(
        "/v1/auth/login",
        json={
            "username": TEST_ADMIN_USERNAME,
            "password": TEST_ADMIN_PASSWORD,
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
