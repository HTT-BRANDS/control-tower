"""Extend brand_config table with design token columns.

Revision ID: 002
Revises: 001
Create Date: 2025-05-01 00:00:00.000000

If the brand_configs table does not yet exist (fresh database where only
Alembic migrations have run, without Base.metadata.create_all), this
migration creates the full table.  If the table already exists (created by
init_db), it adds only the missing design-token columns.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "brand_configs"

# Design-token extension columns (always nullable for backward compat).
_EXTENSION_COLUMNS = [
    ("brand_key", sa.String(50)),
    ("heading_font", sa.String(100)),
    ("body_font", sa.String(100)),
    ("background_color", sa.String(7)),
    ("text_color", sa.String(7)),
    ("border_radius", sa.String(20)),
    ("shadow_style", sa.String(20)),
    ("logo_primary", sa.String(255)),
    ("logo_white", sa.String(255)),
    ("logo_icon", sa.String(255)),
    ("gradient", sa.String(255)),
]


def upgrade() -> None:
    """Create brand_configs table if missing, then add design token columns."""
    conn = op.get_bind()
    inspector = inspect(conn)

    if _TABLE not in inspector.get_table_names():
        # Table doesn't exist — create it with all columns in one shot.
        op.create_table(
            _TABLE,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, unique=True
            ),
            sa.Column("brand_name", sa.String(255), nullable=False),
            sa.Column("primary_color", sa.String(7), nullable=False),
            sa.Column("secondary_color", sa.String(7), nullable=False),
            sa.Column("accent_color", sa.String(7), nullable=True),
            # Design-token extension columns
            *(sa.Column(name, col_type, nullable=True) for name, col_type in _EXTENSION_COLUMNS),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("idx_brand_configs_tenant_id", _TABLE, ["tenant_id"])
        op.create_index("idx_brand_configs_brand_name", _TABLE, ["brand_name"])
        op.create_index("idx_brand_configs_brand_key", _TABLE, ["brand_key"])
    else:
        # Table exists — add only missing extension columns.
        existing = {c["name"] for c in inspector.get_columns(_TABLE)}
        for col_name, col_type in _EXTENSION_COLUMNS:
            if col_name not in existing:
                op.add_column(_TABLE, sa.Column(col_name, col_type, nullable=True))

        # Ensure brand_key index exists
        existing_indexes = {idx["name"] for idx in inspector.get_indexes(_TABLE)}
        if "idx_brand_configs_brand_key" not in existing_indexes:
            op.create_index("idx_brand_configs_brand_key", _TABLE, ["brand_key"])


def downgrade() -> None:
    """Remove design token columns (or drop entire table if we created it)."""
    conn = op.get_bind()
    inspector = inspect(conn)

    if _TABLE not in inspector.get_table_names():
        return

    existing_indexes = {idx["name"] for idx in inspector.get_indexes(_TABLE)}
    if "idx_brand_configs_brand_key" in existing_indexes:
        op.drop_index("idx_brand_configs_brand_key", _TABLE)

    for col_name, _ in reversed(_EXTENSION_COLUMNS):
        try:
            op.drop_column(_TABLE, col_name)
        except Exception:
            pass  # Column may not exist if table was just created
