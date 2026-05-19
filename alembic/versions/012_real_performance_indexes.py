"""Add the performance indexes migration 008 forgot to add.

Revision ID: 012
Revises: 011
Create Date: 2026-05-19 21:00:00.000000

ct-6uj — Migration 008 (``008_add_performance_indexes.py``) was authored
against an incorrect mental model of the schema. It targeted tables that
don't exist (``cost_data``, ``compliance_scores``, ``compliance_frameworks``,
``monitoring_alerts``) and the author's own audit ultimately removed those
``op.create_index`` calls — leaving 008 as a near no-op that only indexed
a handful of cold tables (recommendations, budgets, subscriptions,
backfill_jobs) while the high-traffic tables our entire app pivots on
still have FK columns that do full sequential scans on every query.

The actual hot tables (verified via ``inspect(engine).get_indexes(...)``):

  - ``cost_snapshots``:        FK tenant_id → tenants(id), **0 indexes**
  - ``cost_anomalies``:        FK tenant_id → tenants(id), **0 indexes**
  - ``compliance_snapshots``:  FK tenant_id → tenants(id), **0 indexes**
  - ``identity_snapshots``:    FK tenant_id → tenants(id), **0 indexes**
  - ``privileged_users``:      FK tenant_id → tenants(id), **0 indexes**
  - ``sync_job_logs``:         only ``job_type``, ``started_at`` indexed
                               individually — not ``tenant_id``, not the
                               composite ``(status, started_at desc)`` that
                               every monitoring query uses.

PostgreSQL does NOT auto-index the referencing side of a FK, so every
``WHERE tenant_id = X`` against these tables degrades linearly with row
count. ``cost_snapshots`` already has ~828 rows in dev and grows daily;
production tables of similar shape grow into the millions.

Query patterns this migration targets (sourced from real call sites):

  - ``cost_service.get_cost_summary``        cost_snapshots(tenant_id, date)
  - ``cost_service.get_costs_by_tenant``     cost_snapshots(tenant_id, date)
  - ``cost_service.get_cost_trends``         cost_snapshots(tenant_id, date)
  - ``cost_service.get_anomalies``           cost_anomalies(tenant_id,
                                              is_acknowledged, detected_at)
  - ``compliance_service`` (any rollup)      compliance_snapshots(
                                              tenant_id, snapshot_date)
  - ``identity_service.get_users``           privileged_users(tenant_id)
  - ``identity_service.get_summary``         identity_snapshots(
                                              tenant_id, snapshot_date)
  - ``monitoring_service.get_history``       sync_job_logs(tenant_id)
  - ``monitoring_service.get_metrics``       sync_job_logs(job_type,
                                              status, started_at)
  - ``dashboard.dashboard_data``             sync_job_logs(job_type,
                                              status, started_at) — used
                                              for the per-domain "Synced
                                              N min ago" footer

This migration is idempotent: every ``create_index`` is guarded by an
existence check, so re-running against a partially-applied DB is safe.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.exc import NoSuchTableError

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ── Helpers ──────────────────────────────────────────────────────────


def _index_exists(table: str, index: str) -> bool:
    """Idempotency helper: True only if both the table AND index exist."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        indexes = [idx["name"] for idx in insp.get_indexes(table)]
    except NoSuchTableError:
        return False
    return index in indexes


def _table_exists(table: str) -> bool:
    """Skip-helper: don't try to index tables that aren't in this DB."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return table in set(insp.get_table_names())


# Composite + single-column indexes we want.
# Format: (table, index_name, [column, ...])
_INDEX_SPECS: list[tuple[str, str, list[str]]] = [
    # ── cost_snapshots ──
    ("cost_snapshots", "idx_cost_snapshots_tenant_date", ["tenant_id", "date"]),
    ("cost_snapshots", "idx_cost_snapshots_date", ["date"]),
    # ── cost_anomalies ──
    (
        "cost_anomalies",
        "idx_cost_anomalies_tenant_ack",
        ["tenant_id", "is_acknowledged"],
    ),
    ("cost_anomalies", "idx_cost_anomalies_detected_at", ["detected_at"]),
    # ── compliance_snapshots ──
    (
        "compliance_snapshots",
        "idx_compliance_snapshots_tenant_date",
        ["tenant_id", "snapshot_date"],
    ),
    # ── identity_snapshots ──
    (
        "identity_snapshots",
        "idx_identity_snapshots_tenant_date",
        ["tenant_id", "snapshot_date"],
    ),
    # ── privileged_users ──
    (
        "privileged_users",
        "idx_privileged_users_tenant_id",
        ["tenant_id"],
    ),
    # ── sync_job_logs ── (single-column tenant_id, composite for monitoring)
    (
        "sync_job_logs",
        "idx_sync_job_logs_tenant_id",
        ["tenant_id"],
    ),
    (
        "sync_job_logs",
        "idx_sync_job_logs_status_started",
        ["status", "started_at"],
    ),
    (
        "sync_job_logs",
        "idx_sync_job_logs_jobtype_status_started",
        ["job_type", "status", "started_at"],
    ),
    # ── alerts ── (status + acknowledged pattern from the alerts API)
    (
        "alerts",
        "idx_alerts_tenant_id",
        ["tenant_id"],
    ),
]


def upgrade() -> None:
    """Add the indexes migration 008 should have added."""
    for table, index_name, columns in _INDEX_SPECS:
        if not _table_exists(table):
            # Skip silently — keeps the migration robust against future
            # schema branches where some tables might not yet exist on a
            # newly-cloned DB. ct-6uj's whole point is to not pretend to
            # add indexes to tables we don't have.
            continue
        if _index_exists(table, index_name):
            continue
        op.create_index(
            index_name,
            table,
            columns,
            postgresql_using="btree",
        )


def downgrade() -> None:
    """Drop the indexes added by ``upgrade``."""
    for table, index_name, _columns in _INDEX_SPECS:
        if _index_exists(table, index_name):
            op.drop_index(index_name, table_name=table)
