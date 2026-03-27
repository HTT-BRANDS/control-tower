"""Add billing_account_id column to tenants table for CO-007.

Revision ID: 006
Revises: 005
Create Date: 2026-03-20 00:00:00.000000

Adds the billing_account_id column required by the ReservationService to
call the Azure Consumption reservationSummaries API at billing-account scope.
The column is nullable so existing tenant records are unaffected.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table: str, column: str) -> bool:
    """Return True if the column already exists in the table."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = [col["name"] for col in insp.get_columns(table)]
    return column in columns


def upgrade() -> None:
    """Add billing_account_id to the tenants table (idempotent)."""
    if not _column_exists("tenants", "billing_account_id"):
        op.add_column(
            "tenants",
            sa.Column("billing_account_id", sa.String(255), nullable=True),
        )


def downgrade() -> None:
    """Drop billing_account_id from the tenants table."""
    if _column_exists("tenants", "billing_account_id"):
        op.drop_column("tenants", "billing_account_id")
