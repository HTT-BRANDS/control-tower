"""Add content_hash / prev_hash chain to audit_log_entries (SOC 2 CC7.2).

Revision ID: 014
Revises: 013
Create Date: 2026-06-09

Adds two nullable VARCHAR(64) columns to audit_log_entries:

  content_hash  SHA-256 of the row's canonical payload fields.
  prev_hash     content_hash of the chronologically preceding row
                (NULL for the genesis row).

Together they form a linked chain that makes DB-admin-level row mutations
detectable via AuditLogService.verify_chain(). Existing rows are left with
NULL hashes (back-fill is a separate ops task; the service handles NULLs
gracefully during verification). New rows written after this migration will
always carry both values.

See also: docs/testing/TESTING_SUITE_AUDIT_2026-06.md Finding 3.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "audit_log_entries"
_CONTENT_HASH_COL = "content_hash"
_PREV_HASH_COL = "prev_hash"
_CONTENT_HASH_IDX = "ix_audit_log_entries_content_hash"


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    existing_cols = {c["name"] for c in inspector.get_columns(_TABLE)}

    if _CONTENT_HASH_COL not in existing_cols:
        op.add_column(
            _TABLE,
            sa.Column(_CONTENT_HASH_COL, sa.String(64), nullable=True),
        )
        op.create_index(_CONTENT_HASH_IDX, _TABLE, [_CONTENT_HASH_COL])

    if _PREV_HASH_COL not in existing_cols:
        op.add_column(
            _TABLE,
            sa.Column(_PREV_HASH_COL, sa.String(64), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    existing_cols = {c["name"] for c in inspector.get_columns(_TABLE)}
    existing_idxs = {i["name"] for i in inspector.get_indexes(_TABLE)}

    if _CONTENT_HASH_IDX in existing_idxs:
        op.drop_index(_CONTENT_HASH_IDX, _TABLE)

    if _CONTENT_HASH_COL in existing_cols:
        op.drop_column(_TABLE, _CONTENT_HASH_COL)

    if _PREV_HASH_COL in existing_cols:
        op.drop_column(_TABLE, _PREV_HASH_COL)
