"""Tests for environment-based application configuration."""

import pytest
from pydantic import ValidationError

from dev_meter.core.config import Settings


def test_settings_use_development_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings have stable defaults independent of the developer environment."""
    for name in (
        "DEVMETER_APPLICATION_NAME",
        "DEVMETER_ENVIRONMENT",
        "DEVMETER_DEBUG",
        "DEVMETER_DATABASE_URL",
        "DEVMETER_DEFAULT_REQUEST_LIMIT",
        "DEVMETER_UPSTREAM_TIMEOUT",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.application_name == "DevMeter"
    assert settings.environment == "development"
    assert settings.debug is False
    assert settings.database_url == "sqlite:///./dev_meter.db"
    assert settings.default_request_limit == 100
    assert settings.upstream_timeout == 10.0


def test_settings_support_environment_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Supported environment variables override their defaults."""
    monkeypatch.setenv("DEVMETER_APPLICATION_NAME", "Environment DevMeter")
    monkeypatch.setenv("DEVMETER_ENVIRONMENT", "testing")
    monkeypatch.setenv("DEVMETER_DEBUG", "true")
    monkeypatch.setenv("DEVMETER_DATABASE_URL", "sqlite:///./test.db")

    settings = Settings(_env_file=None)

    assert settings.application_name == "Environment DevMeter"
    assert settings.environment == "testing"
    assert settings.debug is True
    assert settings.database_url == "sqlite:///./test.db"


def test_settings_reject_invalid_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unsupported environment names are rejected by validation."""
    monkeypatch.setenv("DEVMETER_ENVIRONMENT", "staging")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_reject_empty_application_name() -> None:
    """An empty application name is rejected by validation."""
    with pytest.raises(ValidationError):
        Settings(application_name="")


def test_production_settings_require_postgresql() -> None:
    """Production settings do not silently select ephemeral SQLite storage."""
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(environment="production")


def test_production_settings_reject_debug_mode() -> None:
    """Production settings cannot enable verbose debug responses."""
    with pytest.raises(ValidationError, match="DEBUG"):
        Settings(
            environment="production",
            database_url="postgresql+psycopg://user:pass@host/db",
            debug=True,
        )
