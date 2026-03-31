"""Add performance indexes for frequently queried columns.

Revision ID: 008
Revises: 007
Create Date: 2026-05-20 00:00:00.000000

Adds database indexes to improve query performance for:
- tenant_id lookups (most common filter)
- user_id lookups (access control)
- timestamp ranges (reporting, sync jobs)
- composite indexes for common query patterns

This migration is idempotent - it checks if indexes exist before creating them.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_exists(table: str, index: str) -> bool:
    """Check if an index already exists on the table."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    indexes = [idx["name"] for idx in insp.get_indexes(table)]
    return index in indexes


def upgrade() -> None:
    """Add performance indexes for frequently queried columns."""
    # Sync jobs indexes
    # Frequently queried by tenant_id for sync status
    if not _index_exists("sync_jobs", "idx_sync_jobs_tenant_id"):
        op.create_index(
            "idx_sync_jobs_tenant_id",
            "sync_jobs",
            ["tenant_id"],
            postgresql_using="btree",
        )

    # Frequently queried by job_type and status for monitoring
    if not _index_exists("sync_jobs", "idx_sync_jobs_job_type_status"):
        op.create_index(
            "idx_sync_jobs_job_type_status",
            "sync_jobs",
            ["job_type", "status"],
            postgresql_using="btree",
        )

    # Frequently queried by started_at for recent sync history
    if not _index_exists("sync_jobs", "idx_sync_jobs_started_at"):
        op.create_index(
            "idx_sync_jobs_started_at",
            "sync_jobs",
            ["started_at"],
            postgresql_using="btree",
        )

    # Recommendations indexes
    # Frequently queried by tenant_id
    if not _index_exists("recommendations", "idx_recommendations_tenant_id"):
        op.create_index(
            "idx_recommendations_tenant_id",
            "recommendations",
            ["tenant_id"],
            postgresql_using="btree",
        )

    # Frequently queried by created_at for reporting
    if not _index_exists("recommendations", "idx_recommendations_created_at"):
        op.create_index(
            "idx_recommendations_created_at",
            "recommendations",
            ["created_at"],
            postgresql_using="btree",
        )

    # Monitoring alerts indexes
    # Frequently queried by tenant_id for active alerts
    if not _index_exists("monitoring_alerts", "idx_monitoring_alerts_tenant_id"):
        op.create_index(
            "idx_monitoring_alerts_tenant_id",
            "monitoring_alerts",
            ["tenant_id"],
            postgresql_using="btree",
        )

    # Frequently queried by status for alert management
    if not _index_exists("monitoring_alerts", "idx_monitoring_alerts_status"):
        op.create_index(
            "idx_monitoring_alerts_status",
            "monitoring_alerts",
            ["status"],
            postgresql_using="btree",
        )

    # Frequently queried by created_at for time-based alerts
    if not _index_exists("monitoring_alerts", "idx_monitoring_alerts_created_at"):
        op.create_index(
            "idx_monitoring_alerts_created_at",
            "monitoring_alerts",
            ["created_at"],
            postgresql_using="btree",
        )

    # Budget indexes
    # Frequently queried by tenant_id (already has FK, adding index for performance)
    if not _index_exists("budgets", "idx_budgets_tenant_id"):
        op.create_index(
            "idx_budgets_tenant_id",
            "budgets",
            ["tenant_id"],
            postgresql_using="btree",
        )

    # Cost data indexes
    # Frequently queried by tenant_id for cost reporting
    if not _index_exists("cost_data", "idx_cost_data_tenant_id"):
        op.create_index(
            "idx_cost_data_tenant_id",
            "cost_data",
            ["tenant_id"],
            postgresql_using="btree",
        )

    # Frequently queried by date for cost trend analysis
    if not _index_exists("cost_data", "idx_cost_data_usage_date"):
        op.create_index(
            "idx_cost_data_usage_date",
            "cost_data",
            ["usage_date"],
            postgresql_using="btree",
        )

    # Resources indexes
    # Frequently queried by tenant_id for resource listings
    if not _index_exists("resources", "idx_resources_tenant_id"):
        op.create_index(
            "idx_resources_tenant_id",
            "resources",
            ["tenant_id"],
            postgresql_using="btree",
        )

    # Compliance indexes
    # Frequently queried by tenant_id for compliance status
    if not _index_exists("compliance_scores", "idx_compliance_scores_tenant_id"):
        op.create_index(
            "idx_compliance_scores_tenant_id",
            "compliance_scores",
            ["tenant_id"],
            postgresql_using="btree",
        )

    if not _index_exists("compliance_frameworks", "idx_compliance_frameworks_tenant_id"):
        op.create_index(
            "idx_compliance_frameworks_tenant_id",
            "compliance_frameworks",
            ["tenant_id"],
            postgresql_using="btree",
        )

    # Subscriptions indexes
    # Frequently queried by tenant_ref for tenant's subscriptions
    if not _index_exists("subscriptions", "idx_subscriptions_tenant_ref"):
        op.create_index(
            "idx_subscriptions_tenant_ref",
            "subscriptions",
            ["tenant_ref"],
            postgresql_using="btree",
        )

    # Backfill jobs indexes
    # Frequently queried by tenant_id for job status
    if not _index_exists("backfill_jobs", "idx_backfill_jobs_tenant_id"):
        op.create_index(
            "idx_backfill_jobs_tenant_id",
            "backfill_jobs",
            ["tenant_id"],
            postgresql_using="btree",
        )

    # Frequently queried by status for job management
    if not _index_exists("backfill_jobs", "idx_backfill_jobs_status"):
        op.create_index(
            "idx_backfill_jobs_status",
            "backfill_jobs",
            ["status"],
            postgresql_using="btree",
        )


def downgrade() -> None:
    """Remove performance indexes."""
    # Drop sync_jobs indexes
    if _index_exists("sync_jobs", "idx_sync_jobs_tenant_id"):
        op.drop_index("idx_sync_jobs_tenant_id", table_name="sync_jobs")

    if _index_exists("sync_jobs", "idx_sync_jobs_job_type_status"):
        op.drop_index("idx_sync_jobs_job_type_status", table_name="sync_jobs")

    if _index_exists("sync_jobs", "idx_sync_jobs_started_at"):
        op.drop_index("idx_sync_jobs_started_at", table_name="sync_jobs")

    # Drop recommendations indexes
    if _index_exists("recommendations", "idx_recommendations_tenant_id"):
        op.drop_index("idx_recommendations_tenant_id", table_name="recommendations")

    if _index_exists("recommendations", "idx_recommendations_created_at"):
        op.drop_index("idx_recommendations_created_at", table_name="recommendations")

    # Drop monitoring alerts indexes
    if _index_exists("monitoring_alerts", "idx_monitoring_alerts_tenant_id"):
        op.drop_index("idx_monitoring_alerts_tenant_id", table_name="monitoring_alerts")

    if _index_exists("monitoring_alerts", "idx_monitoring_alerts_status"):
        op.drop_index("idx_monitoring_alerts_status", table_name="monitoring_alerts")

    if _index_exists("monitoring_alerts", "idx_monitoring_alerts_created_at"):
        op.drop_index("idx_monitoring_alerts_created_at", table_name="monitoring_alerts")

    # Drop budget indexes
    if _index_exists("budgets", "idx_budgets_tenant_id"):
        op.drop_index("idx_budgets_tenant_id", table_name="budgets")

    # Drop cost data indexes
    if _index_exists("cost_data", "idx_cost_data_tenant_id"):
        op.drop_index("idx_cost_data_tenant_id", table_name="cost_data")

    if _index_exists("cost_data", "idx_cost_data_usage_date"):
        op.drop_index("idx_cost_data_usage_date", table_name="cost_data")

    # Drop resources indexes
    if _index_exists("resources", "idx_resources_tenant_id"):
        op.drop_index("idx_resources_tenant_id", table_name="resources")

    # Drop compliance indexes
    if _index_exists("compliance_scores", "idx_compliance_scores_tenant_id"):
        op.drop_index("idx_compliance_scores_tenant_id", table_name="compliance_scores")

    if _index_exists("compliance_frameworks", "idx_compliance_frameworks_tenant_id"):
        op.drop_index("idx_compliance_frameworks_tenant_id", table_name="compliance_frameworks")

    # Drop subscriptions indexes
    if _index_exists("subscriptions", "idx_subscriptions_tenant_ref"):
        op.drop_index("idx_subscriptions_tenant_ref", table_name="subscriptions")

    # Drop backfill jobs indexes
    if _index_exists("backfill_jobs", "idx_backfill_jobs_tenant_id"):
        op.drop_index("idx_backfill_jobs_tenant_id", table_name="backfill_jobs")

    if _index_exists("backfill_jobs", "idx_backfill_jobs_status"):
        op.drop_index("idx_backfill_jobs_status", table_name="backfill_jobs")
