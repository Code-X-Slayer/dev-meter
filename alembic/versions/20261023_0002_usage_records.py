"""Create usage records table."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261023_0002"
down_revision: str | None = "20261023_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the usage records table and indexes."""
    op.create_table(
        "usage_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("api_key_id", sa.String(length=36), nullable=False),
        sa.Column("service_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("upstream_status_code", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["api_key_id"],
            ["api_keys.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_usage_records_api_key_id",
        "usage_records",
        ["api_key_id"],
    )
    op.create_index(
        "ix_usage_records_service_id",
        "usage_records",
        ["service_id"],
    )
    op.create_index(
        "ix_usage_records_created_at",
        "usage_records",
        ["created_at"],
    )


def downgrade() -> None:
    """Drop the usage records table."""
    op.drop_index("ix_usage_records_created_at", table_name="usage_records")
    op.drop_index("ix_usage_records_service_id", table_name="usage_records")
    op.drop_index("ix_usage_records_api_key_id", table_name="usage_records")
    op.drop_table("usage_records")
