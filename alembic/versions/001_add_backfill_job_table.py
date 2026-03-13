"""Add backfill_job table with checkpoint support.

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create backfill_jobs table."""
    op.create_table(
        "backfill_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, default="pending"),
        sa.Column("start_date", sa.DateTime(), nullable=False),
        sa.Column("end_date", sa.DateTime(), nullable=False),
        sa.Column("current_date", sa.DateTime(), nullable=True),
        sa.Column("progress_percent", sa.Float(), nullable=False, default=0.0),
        sa.Column("records_processed", sa.Integer(), nullable=False, default=0),
        sa.Column("records_inserted", sa.Integer(), nullable=False, default=0),
        sa.Column("records_failed", sa.Integer(), nullable=False, default=0),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=False, default=0),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("paused_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
    )

    # Create indexes for common queries
    op.create_index("idx_backfill_jobs_status", "backfill_jobs", ["status"])
    op.create_index("idx_backfill_jobs_tenant", "backfill_jobs", ["tenant_id"])
    op.create_index("idx_backfill_jobs_type", "backfill_jobs", ["job_type"])


def downgrade() -> None:
    """Drop backfill_jobs table."""
    op.drop_index("idx_backfill_jobs_type", "backfill_jobs")
    op.drop_index("idx_backfill_jobs_tenant", "backfill_jobs")
    op.drop_index("idx_backfill_jobs_status", "backfill_jobs")
    op.drop_table("backfill_jobs")
