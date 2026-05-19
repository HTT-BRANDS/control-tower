"""Drop tenants.use_lighthouse column (ct-59n Lighthouse demolition).

Revision ID: 011
Revises: 010
Create Date: 2026-05-19 18:00:00.000000

Drops the unused ``use_lighthouse`` column from the ``tenants`` table.

Context: 2026-05-19 audit confirmed Azure Lighthouse is not used at HTT —
zero delegations, no registration definitions, no env wiring. All 5 tenants
have ``use_lighthouse=0``. The column and the entire LighthouseAzureClient
code path were removed in ct-59n. This migration cleans up the now-orphaned
column.

Safety:
- All existing rows have ``use_lighthouse=0`` (verified pre-deploy)
- No code path reads or writes the column after this migration
- Downgrade restores the column with ``DEFAULT 0`` so a rollback is lossless
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop the use_lighthouse column from tenants."""
    # SQLite < 3.35 can't drop columns; batch_alter_table emits the
    # copy-rename dance automatically. Modern SQLite (3.35+) and Azure SQL
    # both support DROP COLUMN natively, but batch mode is portable.
    with op.batch_alter_table("tenants") as batch_op:
        batch_op.drop_column("use_lighthouse")


def downgrade() -> None:
    """Re-add the use_lighthouse column (default False)."""
    with op.batch_alter_table("tenants") as batch_op:
        batch_op.add_column(
            sa.Column(
                "use_lighthouse",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
