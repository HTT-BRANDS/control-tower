"""Add resource_lifecycle_events table (RM-004).

Revision ID: 003
Revises: 002
Create Date: 2025-05-15 00:00:00.000000

Creates the resource_lifecycle_events table for tracking create/update/delete
events detected for Azure resources during sync runs.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "resource_lifecycle_events"


def upgrade() -> None:
    """Create resource_lifecycle_events table if it does not already exist."""
    conn = op.get_bind()
    inspector = inspect(conn)

    if _TABLE in inspector.get_table_names():
        return  # Idempotent — table already present (e.g. created by Base.metadata.create_all)

    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("resource_id", sa.String(255), nullable=False),
        sa.Column("resource_name", sa.String(255), nullable=False),
        sa.Column("resource_type", sa.String(200), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("subscription_id", sa.String(36), nullable=True),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_state", sa.JSON(), nullable=True),
        sa.Column("current_state", sa.JSON(), nullable=True),
        sa.Column("changed_fields", sa.JSON(), nullable=True),
        sa.Column("sync_run_id", sa.String(36), nullable=True),
    )

    # Single-column indexes
    op.create_index("ix_resource_lifecycle_events_resource_id", _TABLE, ["resource_id"])
    op.create_index("ix_resource_lifecycle_events_tenant_id", _TABLE, ["tenant_id"])
    op.create_index("ix_resource_lifecycle_events_event_type", _TABLE, ["event_type"])
    op.create_index("ix_resource_lifecycle_events_detected_at", _TABLE, ["detected_at"])

    # Composite indexes
    op.create_index("ix_lifecycle_resource_time", _TABLE, ["resource_id", "detected_at"])
    op.create_index("ix_lifecycle_tenant_type", _TABLE, ["tenant_id", "event_type"])


def downgrade() -> None:
    """Drop the resource_lifecycle_events table."""
    conn = op.get_bind()
    inspector = inspect(conn)

    if _TABLE not in inspector.get_table_names():
        return

    for idx in [
        "ix_lifecycle_tenant_type",
        "ix_lifecycle_resource_time",
        "ix_resource_lifecycle_events_detected_at",
        "ix_resource_lifecycle_events_event_type",
        "ix_resource_lifecycle_events_tenant_id",
        "ix_resource_lifecycle_events_resource_id",
    ]:
        try:
            op.drop_index(idx, _TABLE)
        except Exception:
            pass  # Index may not exist

    op.drop_table(_TABLE)
