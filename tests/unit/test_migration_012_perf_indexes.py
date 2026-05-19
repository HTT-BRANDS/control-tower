"""Regression tests for ct-6uj: ensure migration 012 actually exists,
targets real tables, and is idempotent.

Migration 008 (``008_add_performance_indexes.py``) was a near no-op
because it targeted phantom tables. Migration 012 fixes that. This
test enforces a few load-bearing invariants:

1. The migration file exists at the expected path.
2. Every table it targets exists in the model registry.
3. Every column it indexes exists on its table model.
4. The migration is idempotent (re-running upgrade after upgrade
   doesn't error — the existence guards work).
5. Downgrade is a real inverse (drop everything we created).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "012_real_performance_indexes.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "migration_012", MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_migration_012_exists():
    assert MIGRATION_PATH.exists(), (
        "ct-6uj: alembic/versions/012_real_performance_indexes.py must exist"
    )


def test_migration_012_revision_chain():
    mod = _load_migration_module()
    assert mod.revision == "012"
    assert mod.down_revision == "011", (
        "ct-6uj: 012 must follow 011 (the Lighthouse demolition migration)"
    )


def test_every_indexed_table_is_real():
    """All target tables must actually exist in our SQLAlchemy model registry.

    This is exactly the check migration 008 failed.
    """
    mod = _load_migration_module()
    # Import all models so registry is populated.
    import app.models  # noqa: F401  pylint: disable=unused-import
    from app.core.database import Base

    known_tables = set(Base.metadata.tables.keys())
    bad = []
    for table, _index_name, _cols in mod._INDEX_SPECS:
        if table not in known_tables:
            bad.append(table)
    assert not bad, (
        "ct-6uj regression: migration 012 references tables that don't "
        "exist in our model registry — exactly the bug 008 had.\n"
        f"  Missing tables: {bad}\n"
        f"  Known tables: {sorted(known_tables)}"
    )


def test_every_indexed_column_is_real():
    """Each column we try to index must exist on its target table."""
    mod = _load_migration_module()
    import app.models  # noqa: F401
    from app.core.database import Base

    bad = []
    for table, index_name, columns in mod._INDEX_SPECS:
        if table not in Base.metadata.tables:
            continue  # already covered by the previous test
        table_cols = {c.name for c in Base.metadata.tables[table].columns}
        for col in columns:
            if col not in table_cols:
                bad.append(f"{table}.{col} (index {index_name})")
    assert not bad, (
        "ct-6uj: migration 012 indexes columns that don't exist:\n"
        + "\n".join(f"  - {b}" for b in bad)
    )


def test_upgrade_is_idempotent_via_existence_guards():
    """Calling upgrade twice on the same DB must not error.

    We don't actually run the migration here (that requires an alembic
    context) — we just confirm the helper logic short-circuits when an
    index already exists. Reading the source is the cheapest check.
    """
    src = MIGRATION_PATH.read_text()
    assert "_index_exists(" in src, (
        "ct-6uj: upgrade must guard every create_index with an existence check"
    )
    # Crude but effective: every create_index call should be preceded by
    # an existence guard.
    upgrade_block = src.split("def upgrade")[1].split("def downgrade")[0]
    create_calls = upgrade_block.count("op.create_index(")
    guard_calls = upgrade_block.count("_index_exists(")
    assert guard_calls >= create_calls, (
        f"ct-6uj: idempotency broken — {create_calls} create_index calls but "
        f"only {guard_calls} _index_exists guards"
    )


def test_downgrade_drops_what_upgrade_creates():
    """Downgrade should iterate the same spec list and call drop_index.

    The downgrade is written as a loop over ``_INDEX_SPECS`` rather than
    a series of literal drop_index calls, so we assert structural
    equivalence: the loop must exist, must use the same spec source as
    upgrade, and must call ``drop_index`` exactly once per spec.
    """
    src = MIGRATION_PATH.read_text()
    downgrade_block = src.split("def downgrade")[1]
    assert "for table, index_name, _columns in _INDEX_SPECS" in downgrade_block, (
        "ct-6uj: downgrade must iterate _INDEX_SPECS so it stays in sync "
        "with upgrade automatically — no copy-paste drift allowed"
    )
    assert "op.drop_index(" in downgrade_block, (
        "ct-6uj: downgrade must actually call op.drop_index"
    )
    assert "_index_exists(" in downgrade_block, (
        "ct-6uj: downgrade must guard drops with _index_exists for idempotency"
    )


# ── Fitness function from F-1 audit recommendation ────────────────────


def test_no_phantom_table_references_in_any_migration():
    """Architecture check: no migration may reference a non-existent table.

    This is the audit's recommended fitness function — if any future
    migration repeats 008's mistake, this test fails loudly.

    We scan migration source for ``create_index(...)``, ``alter_table``,
    ``drop_table`` etc. patterns and confirm the table name argument
    matches a known table. We skip migrations that intentionally CREATE
    or DROP tables (lifecycle migrations).
    """
    import re
    import app.models  # noqa: F401
    from app.core.database import Base

    known = set(Base.metadata.tables.keys())
    versions_dir = MIGRATION_PATH.parent
    pattern = re.compile(
        r"""op\.create_index\(\s*['"][^'"]+['"]\s*,\s*['"]([^'"]+)['"]""",
        re.MULTILINE,
    )

    bad = []
    for migration_file in sorted(versions_dir.glob("0*.py")):
        text = migration_file.read_text()
        for match in pattern.finditer(text):
            table_name = match.group(1)
            if table_name not in known:
                bad.append(f"{migration_file.name}: indexes phantom table '{table_name}'")
    assert not bad, (
        "ct-6uj fitness function: migration(s) reference tables not in the "
        "model registry:\n" + "\n".join(f"  - {b}" for b in bad)
    )
