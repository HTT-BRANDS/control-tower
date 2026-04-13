"""Convert VARCHAR columns to NVARCHAR on policy_states and cost_snapshots.

Revision ID: 010
Revises: 009
Create Date: 2026-04-14 00:00:00.000000

WHY THIS EXISTS
---------------
SQLAlchemy's String() type maps to NVARCHAR on the mssql dialect, so the ORM
sends NVARCHAR-typed parameters.  However, the actual database columns were
created as VARCHAR (likely because the initial schema was created on SQLite
and then migrated to Azure SQL).  This mismatch causes SQL Server error 2628
("String or binary data would be truncated") when SQLAlchemy's insertmanyvalues
batch INSERT sends NVARCHAR parameters into VARCHAR columns — the implicit
NVARCHAR→VARCHAR conversion inside the INSERT…OUTPUT…SELECT batch pattern
fails.

Evidence from production:
  pyodbc.ProgrammingError ('42000'): String or binary data would be truncated
  in table 'governance.dbo.policy_states', column 'policy_category'.
  Truncated value: 'azure_security_benchmark_v3.0_lt-1,…'

This migration aligns the database schema with SQLAlchemy's expected types,
eliminating the implicit conversion and the truncation error.

IDEMPOTENCY
-----------
- ALTER COLUMN is a metadata-only operation on Azure SQL (sub-millisecond,
  no data rewrite) for VARCHAR→NVARCHAR conversions.
- Safe to re-run; the columns end up as NVARCHAR regardless.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Convert VARCHAR columns to NVARCHAR on policy_states and cost_snapshots.

    NOTE: tenant_id columns (FK to tenants.id) are LEFT as VARCHAR because
    tenants.id is the PK and has 22 FK dependents.  Converting it would
    require dropping all FKs + the PK, altering, and re-adding — too risky
    for a single migration.  Since tenant_id values are always 36-char ASCII
    UUIDs, the implicit NVARCHAR→VARCHAR conversion works safely.
    """
    # --- policy_states ---
    # These columns were VARCHAR but SQLAlchemy sends NVARCHAR parameters,
    # causing error 2628 during batch INSERT.
    op.alter_column(
        "policy_states",
        "subscription_id",
        existing_type=sa.String(36),
        type_=sa.NVARCHAR(36),
        existing_nullable=False,
    )
    op.alter_column(
        "policy_states",
        "policy_definition_id",
        existing_type=sa.String(500),
        type_=sa.NVARCHAR(500),
        existing_nullable=False,
    )
    op.alter_column(
        "policy_states",
        "policy_name",
        existing_type=sa.String(1000),
        type_=sa.NVARCHAR(1000),
        existing_nullable=False,
    )
    op.alter_column(
        "policy_states",
        "policy_category",
        existing_type=sa.String(500),
        type_=sa.NVARCHAR(500),
        existing_nullable=True,
    )
    op.alter_column(
        "policy_states",
        "compliance_state",
        existing_type=sa.String(50),
        type_=sa.NVARCHAR(50),
        existing_nullable=False,
    )
    op.alter_column(
        "policy_states",
        "resource_id",
        existing_type=sa.String(500),
        type_=sa.NVARCHAR(500),
        existing_nullable=True,
    )
    op.alter_column(
        "policy_states",
        "recommendation",
        existing_type=sa.String(1000),
        type_=sa.NVARCHAR(1000),
        existing_nullable=True,
    )

    # --- compliance_snapshots ---
    op.alter_column(
        "compliance_snapshots",
        "subscription_id",
        existing_type=sa.String(36),
        type_=sa.NVARCHAR(36),
        existing_nullable=False,
    )

    # --- cost_snapshots ---
    # Same VARCHAR→NVARCHAR mismatch; prevents future 2628 errors.
    op.alter_column(
        "cost_snapshots",
        "subscription_id",
        existing_type=sa.String(36),
        type_=sa.NVARCHAR(36),
        existing_nullable=False,
    )
    op.alter_column(
        "cost_snapshots",
        "currency",
        existing_type=sa.String(10),
        type_=sa.NVARCHAR(10),
        existing_nullable=True,
    )
    op.alter_column(
        "cost_snapshots",
        "resource_group",
        existing_type=sa.String(255),
        type_=sa.NVARCHAR(255),
        existing_nullable=True,
    )
    op.alter_column(
        "cost_snapshots",
        "service_name",
        existing_type=sa.String(255),
        type_=sa.NVARCHAR(255),
        existing_nullable=True,
    )
    op.alter_column(
        "cost_snapshots",
        "meter_category",
        existing_type=sa.String(255),
        type_=sa.NVARCHAR(255),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Narrow NVARCHAR columns back to VARCHAR.

    WARNING: This may cause data loss if any values contain non-ASCII
    characters that cannot be represented in VARCHAR with the current
    collation.  Review data before running this downgrade.
    """
    # --- cost_snapshots ---
    op.alter_column(
        "cost_snapshots",
        "meter_category",
        existing_type=sa.NVARCHAR(255),
        type_=sa.String(255),
        existing_nullable=True,
    )
    op.alter_column(
        "cost_snapshots",
        "service_name",
        existing_type=sa.NVARCHAR(255),
        type_=sa.String(255),
        existing_nullable=True,
    )
    op.alter_column(
        "cost_snapshots",
        "resource_group",
        existing_type=sa.NVARCHAR(255),
        type_=sa.String(255),
        existing_nullable=True,
    )
    op.alter_column(
        "cost_snapshots",
        "currency",
        existing_type=sa.NVARCHAR(10),
        type_=sa.String(10),
        existing_nullable=True,
    )
    op.alter_column(
        "cost_snapshots",
        "subscription_id",
        existing_type=sa.NVARCHAR(36),
        type_=sa.String(36),
        existing_nullable=False,
    )

    # --- compliance_snapshots ---
    op.alter_column(
        "compliance_snapshots",
        "subscription_id",
        existing_type=sa.NVARCHAR(36),
        type_=sa.String(36),
        existing_nullable=False,
    )

    # --- policy_states ---
    op.alter_column(
        "policy_states",
        "recommendation",
        existing_type=sa.NVARCHAR(1000),
        type_=sa.String(1000),
        existing_nullable=True,
    )
    op.alter_column(
        "policy_states",
        "resource_id",
        existing_type=sa.NVARCHAR(500),
        type_=sa.String(500),
        existing_nullable=True,
    )
    op.alter_column(
        "policy_states",
        "compliance_state",
        existing_type=sa.NVARCHAR(50),
        type_=sa.String(50),
        existing_nullable=False,
    )
    op.alter_column(
        "policy_states",
        "policy_category",
        existing_type=sa.NVARCHAR(500),
        type_=sa.String(500),
        existing_nullable=True,
    )
    op.alter_column(
        "policy_states",
        "policy_name",
        existing_type=sa.NVARCHAR(1000),
        type_=sa.String(1000),
        existing_nullable=False,
    )
    op.alter_column(
        "policy_states",
        "policy_definition_id",
        existing_type=sa.NVARCHAR(500),
        type_=sa.String(500),
        existing_nullable=False,
    )
    op.alter_column(
        "policy_states",
        "subscription_id",
        existing_type=sa.NVARCHAR(36),
        type_=sa.String(36),
        existing_nullable=False,
    )
