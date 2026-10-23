"""Application configuration."""

from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="DEVMETER_",
        extra="ignore",
    )

    application_name: str = Field(default="DevMeter", min_length=1)
    environment: Literal["development", "testing", "production"] = "development"
    debug: bool = False
    database_url: str = "sqlite:///./dev_meter.db"
    default_request_limit: int = Field(default=100, ge=1)
    upstream_timeout: float = Field(default=10.0, gt=0)
    admin_username: str | None = None
    admin_password_hash: SecretStr | None = None
    jwt_secret: SecretStr | None = None
    jwt_expiry_minutes: int = Field(default=30, ge=5, le=1440)

    @model_validator(mode="after")
    def validate_runtime_safety(self) -> Settings:
        """Reject development-only defaults in a production process."""
        if self.environment == "production" and self.debug:
            raise ValueError("DEVMETER_DEBUG must be false in production")
        if self.environment == "production" and self.database_url.startswith("sqlite:"):
            raise ValueError("DEVMETER_DATABASE_URL must use PostgreSQL in production")
        if self.environment == "production":
            if not self.admin_username:
                raise ValueError("DEVMETER_ADMIN_USERNAME is required in production")
            if self.admin_password_hash is None:
                raise ValueError(
                    "DEVMETER_ADMIN_PASSWORD_HASH is required in production"
                )
            if self.jwt_secret is None or len(self.jwt_secret.get_secret_value()) < 32:
                raise ValueError(
                    "DEVMETER_JWT_SECRET must be at least 32 characters in production"
                )
        if (
            self.admin_password_hash is not None
            and not self.admin_password_hash.get_secret_value().startswith("$argon2")
        ):
            raise ValueError("DEVMETER_ADMIN_PASSWORD_HASH must be an Argon2 hash")
        return self
