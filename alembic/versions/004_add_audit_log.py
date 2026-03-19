"""Add audit_log_entries table for CM-010.

Revision ID: 004
Revises: 003
Create Date: 2026-03-19 00:00:00.000000

Creates the audit_log_entries table with full composite indexes.
Idempotent: skips table creation if it already exists (e.g. init_db
ran first and created it via Base.metadata.create_all).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "audit_log_entries"


def upgrade() -> None:
    """Create audit_log_entries table if it does not already exist."""
    conn = op.get_bind()
    inspector = inspect(conn)

    if _TABLE in inspector.get_table_names():
        return  # Already exists — nothing to do

    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("actor_id", sa.String(255), nullable=True),
        sa.Column("actor_email", sa.String(255), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="success"),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("metadata_json", sa.JSON, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
    )

    # Single-column indexes
    op.create_index("ix_audit_log_entries_timestamp", _TABLE, ["timestamp"])
    op.create_index("ix_audit_log_entries_actor_id", _TABLE, ["actor_id"])
    op.create_index("ix_audit_log_entries_action", _TABLE, ["action"])
    op.create_index("ix_audit_log_entries_tenant_id", _TABLE, ["tenant_id"])

    # Composite indexes
    op.create_index("ix_audit_log_timestamp_actor", _TABLE, ["timestamp", "actor_id"])
    op.create_index("ix_audit_log_action_tenant", _TABLE, ["action", "tenant_id"])


def downgrade() -> None:
    """Drop audit_log_entries table and all its indexes."""
    conn = op.get_bind()
    inspector = inspect(conn)

    if _TABLE not in inspector.get_table_names():
        return

    for idx in [
        "ix_audit_log_action_tenant",
        "ix_audit_log_timestamp_actor",
        "ix_audit_log_entries_tenant_id",
        "ix_audit_log_entries_action",
        "ix_audit_log_entries_actor_id",
        "ix_audit_log_entries_timestamp",
    ]:
        try:
            op.drop_index(idx, _TABLE)
        except Exception:
            pass

    op.drop_table(_TABLE)
