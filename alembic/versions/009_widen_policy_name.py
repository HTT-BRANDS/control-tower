"""Widen policy_name and policy_category columns.

Revision ID: 009
Revises: 008
Create Date: 2026-04-04 00:00:00.000000

Widens policy_states columns to match the ORM model:
  - policy_name:     NVARCHAR(255) → NVARCHAR(1000)
  - policy_category:  NVARCHAR(255) → NVARCHAR(500)

Long Azure Policy names and categories were causing "String or binary data
would be truncated" errors, poisoning the SQLAlchemy session and cascading
to kill ALL sync jobs.

This is a metadata-only operation on Azure SQL (sub-millisecond, no data rewrite).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Widen policy_name to 1000 and policy_category to 500 (idempotent)."""
    op.alter_column(
        "policy_states",
        "policy_name",
        existing_type=sa.String(255),
        type_=sa.String(1000),
        existing_nullable=False,
    )
    op.alter_column(
        "policy_states",
        "policy_category",
        existing_type=sa.String(255),
        type_=sa.String(500),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Narrow both columns back to 255 characters.

    WARNING: This may cause data loss if any values exceed 255 characters.
    Review data before running this downgrade.
    """
    op.alter_column(
        "policy_states",
        "policy_category",
        existing_type=sa.String(500),
        type_=sa.String(255),
        existing_nullable=True,
    )
    op.alter_column(
        "policy_states",
        "policy_name",
        existing_type=sa.String(1000),
        type_=sa.String(255),
        existing_nullable=False,
    )
