"""Extend brand_config table with design token columns.

Revision ID: 002
Revises: 001
Create Date: 2025-05-01 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# All new columns added to brand_configs for the design token system.
_NEW_COLUMNS = [
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

_TABLE = "brand_configs"


def upgrade() -> None:
    """Add design token columns to brand_configs."""
    for col_name, col_type in _NEW_COLUMNS:
        op.add_column(_TABLE, sa.Column(col_name, col_type, nullable=True))

    # brand_key gets an index for fast lookups
    op.create_index("idx_brand_configs_brand_key", _TABLE, ["brand_key"])


def downgrade() -> None:
    """Remove design token columns from brand_configs."""
    op.drop_index("idx_brand_configs_brand_key", _TABLE)

    for col_name, _ in reversed(_NEW_COLUMNS):
        op.drop_column(_TABLE, col_name)
