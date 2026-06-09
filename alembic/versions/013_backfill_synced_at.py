"""Backfill synced_at on domain tables where NULL.

Revision ID: 013
Revises: 012
Create Date: 2026-06-09

The dashboard queries MAX(synced_at) to show "Synced N ago" on domain cards.
Historical data was inserted before the synced_at default was in place (or
via seed/import paths that skipped the column), so every domain shows
"Synced never" despite data being present.

This migration backfills NULL synced_at values with the current timestamp so
the UI accurately reflects that data exists. Purely cosmetic — no business
logic changes.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Set synced_at = now() for rows where it is NULL."""
    now = datetime.now(UTC)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # Map: table_name -> column_to_update
    _TABLES = [
        ("cost_snapshots", "synced_at"),
        ("compliance_snapshots", "synced_at"),
        ("resources", "synced_at"),
        ("identity_snapshots", "synced_at"),
        ("resource_tags", "synced_at"),
    ]

    for table, column in _TABLES:
        if table not in tables:
            continue
        # Only update rows where the column is actually NULL
        bind.execute(
            sa.text(
                f"UPDATE {table} SET {column} = :ts WHERE {column} IS NULL"
            ).bindparams(ts=now)
        )


def downgrade() -> None:
    """No-op: we cannot un-backfill timestamps safely."""
    pass
