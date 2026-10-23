"""SQLAlchemy models for registered services and API keys."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dev_meter.infrastructure.database.base import Base


class Service(Base):
    """A developer-registered upstream API service."""

    __tablename__ = "services"
    __table_args__ = (
        Index("ix_services_owner_id", "owner_id"),
        Index("ix_services_owner_name", "owner_id", "name", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    upstream_base_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    keys: Mapped[list[ApiKey]] = relationship(
        back_populates="service",
        cascade="all, delete-orphan",
    )


class ApiKey(Base):
    """A hashed API key associated with a service."""

    __tablename__ = "api_keys"
    __table_args__ = (
        Index("ix_api_keys_service_id", "service_id"),
        Index("ix_api_keys_prefix", "key_prefix"),
        Index("ix_api_keys_service_revoked", "service_id", "revoked_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    service_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    service: Mapped[Service] = relationship(back_populates="keys")


class UsageRecord(Base):
    """One authenticated forwarding attempt."""

    __tablename__ = "usage_records"
    __table_args__ = (
        Index("ix_usage_records_api_key_id", "api_key_id"),
        Index("ix_usage_records_service_id", "service_id"),
        Index("ix_usage_records_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    api_key_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=False,
    )
    service_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    upstream_status_code: Mapped[int | None] = mapped_column(nullable=True)
    duration_ms: Mapped[int] = mapped_column(nullable=False)
    succeeded: Mapped[bool] = mapped_column(nullable=False)
