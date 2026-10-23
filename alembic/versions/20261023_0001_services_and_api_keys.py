"""Create services and API keys tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261023_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create service and API-key tables."""
    op.create_table(
        "services",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("upstream_base_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_services_owner_id", "services", ["owner_id"])
    op.create_index(
        "ix_services_owner_name",
        "services",
        ["owner_id", "name"],
        unique=True,
    )
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("service_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_keys_service_id", "api_keys", ["service_id"])
    op.create_index("ix_api_keys_prefix", "api_keys", ["key_prefix"])
    op.create_index(
        "ix_api_keys_service_revoked",
        "api_keys",
        ["service_id", "revoked_at"],
    )


def downgrade() -> None:
    """Drop API-key and service tables."""
    op.drop_index("ix_api_keys_service_revoked", table_name="api_keys")
    op.drop_index("ix_api_keys_prefix", table_name="api_keys")
    op.drop_index("ix_api_keys_service_id", table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_index("ix_services_owner_name", table_name="services")
    op.drop_index("ix_services_owner_id", table_name="services")
    op.drop_table("services")
