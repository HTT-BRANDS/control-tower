"""Create full base schema for fresh (non-SQLite) databases.

Revision ID: 000
Revises: (none — this is the root migration)
Create Date: 2026-03-27

WHY THIS EXISTS
---------------
init_db() only calls Base.metadata.create_all() for SQLite (local dev/test).
For Azure SQL / PostgreSQL, create_all() was intentionally skipped to avoid
"42S01 object already exists" crashes on re-deploy to an *existing* DB.

That design assumed the base schema was already in place.  On a *fresh*
Azure SQL database (new environment, wiped DB, etc.) the core tables never
get created, and every post-login request that touches a core table returns
HTTP 500.

This migration closes that gap: it checks for the presence of the `tenants`
table (a reliable proxy for "has the base schema ever been applied?") and, if
absent, calls Base.metadata.create_all() using the live Alembic connection.
The checkfirst=True flag makes each individual table creation idempotent, so
partial-schema states are also handled safely.

IDEMPOTENCY
-----------
- Fresh DB:  creates all core tables, then migrations 001-007 layer on top.
- Existing DB (tenants table found):  immediate no-op, zero DDL issued.
- Partial DB:  create_all(checkfirst=True) creates only the missing tables.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision: str = "000"
down_revision: str | None = None  # root — nothing comes before this
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create full base schema if it does not already exist."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "tenants" in existing_tables:
        # Base schema is already present — nothing to do.
        print("  [000] 'tenants' table found — base schema already exists, skipping.")
        return

    print("  [000] 'tenants' table not found — creating full base schema via create_all().")

    # Import here to avoid circular imports at module load time.
    import app.models  # noqa: F401  — registers all models with Base
    from app.core.database import Base

    # create_all with checkfirst=True is safe even if some tables exist
    # (handles partial-schema states gracefully).
    Base.metadata.create_all(bind=bind, checkfirst=True)

    print("  [000] Base schema created successfully.")


def downgrade() -> None:
    """Downgrade is intentionally a no-op.

    Dropping the entire base schema would destroy all data.  If you need to
    wipe and rebuild, do so explicitly via your DBA tooling — not via Alembic.
    """
    pass
