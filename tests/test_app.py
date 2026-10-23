"""Tests for the DevMeter application foundation."""

from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from dev_meter.app import app, create_app
from dev_meter.core.config import Settings
from dev_meter.infrastructure.database.lifecycle import get_application_engine
from tests.conftest import make_test_settings


def test_application_can_be_created_and_imported() -> None:
    """The application factory returns an importable FastAPI application."""
    application = create_app()

    assert application is not None
    assert application.title == "DevMeter"
    assert application.debug is False
    assert app is not None


def test_application_accepts_explicit_settings() -> None:
    """The application factory uses settings supplied by the caller."""
    settings = Settings(
        application_name="Configured DevMeter",
        environment="testing",
        debug=True,
        admin_username="admin",
        admin_password_hash=PasswordHasher().hash("test-password"),
        jwt_secret="test-jwt-secret-that-is-long-enough",
    )

    application = create_app(settings)

    assert application.title == "Configured DevMeter"
    assert application.debug is True


def test_application_lifespan_creates_and_disposes_engine(tmp_path) -> None:
    """The application owns its engine only while its lifespan is active."""
    settings = make_test_settings(f"sqlite:///{tmp_path / 'test.db'}")
    application = create_app(settings)

    with TestClient(application):
        engine = get_application_engine(application)
        assert engine.url.database == str(tmp_path / "test.db")

    assert engine.pool.checkedout() == 0


def test_application_lifespan_closes_http_client(tmp_path) -> None:
    """The application closes its shared upstream client at shutdown."""
    settings = make_test_settings(f"sqlite:///{tmp_path / 'test.db'}")
    application = create_app(settings)

    with TestClient(application):
        http_client = application.state.http_client
        assert http_client.is_closed is False

    assert http_client.is_closed is True


def test_health_endpoint_returns_success() -> None:
    """The health endpoint responds successfully."""
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200


def test_health_endpoint_returns_expected_json() -> None:
    """The health endpoint returns the expected response shape."""
    client = TestClient(app)

    response = client.get("/health")

    assert response.json() == {"status": "ok"}


def test_unknown_endpoint_returns_not_found() -> None:
    """Unknown routes return HTTP 404."""
    client = TestClient(app)

    response = client.get("/does-not-exist")

    assert response.status_code == 404
