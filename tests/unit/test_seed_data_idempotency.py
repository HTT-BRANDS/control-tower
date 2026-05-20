"""Regression test for ct-cjg: scripts/seed_data.py must be idempotent
against the four sync-related tables.

Pre-fix repro path:
  1. Any rows in ``sync_job_metrics`` (which has a UNIQUE constraint on
     ``job_type`` — one row per type)
  2. Run ``python scripts/seed_data.py``
  3. Crash:
     ``sqlite3.IntegrityError: UNIQUE constraint failed:
     sync_job_metrics.job_type``

Fix: ``seed_sync_history`` now clears Alert, SyncJobMetrics, SyncJobLog,
and SyncJob before re-seeding, so the script produces a deterministic
state regardless of prior contents.
"""

from __future__ import annotations

from pathlib import Path

SEED_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "seed_data.py"


def test_seed_sync_history_clears_sync_tables_first():
    """The seeder must wipe the four sync-related tables before re-seeding.

    Static source check: this is a regression test specifically for the
    fix, so we want to fail noisily if anyone removes the cleanup.
    """
    src = SEED_SCRIPT.read_text()
    # Locate the seed_sync_history function body.
    marker = "def seed_sync_history("
    assert marker in src, "ct-cjg: seed_sync_history function must exist"
    body = src.split(marker, 1)[1].split("\ndef ", 1)[0]

    # All four tables must be cleared.
    for model in ("Alert", "SyncJobMetrics", "SyncJobLog", "SyncJob"):
        assert f"db.query({model}).delete(" in body, (
            f"ct-cjg: seed_sync_history must delete prior {model} rows"
        )


def test_seed_sync_history_uses_bulk_delete_idiom():
    """Use the bulk-delete idiom — don't ORM-hydrate rows just to delete them.

    ``synchronize_session=False`` skips identity-map synchronization, which
    is the right call here because we delete-then-bulk-insert from scratch.
    """
    src = SEED_SCRIPT.read_text()
    body = src.split("def seed_sync_history(", 1)[1].split("\ndef ", 1)[0]
    assert "synchronize_session=False" in body, (
        "ct-cjg: use bulk-delete idiom (synchronize_session=False) so "
        "deletes are O(1) on large tables, not O(n) with ORM hydration"
    )


def test_seed_sync_history_flushes_before_inserts():
    """Flush after deletes so the unique constraint is checked against a
    clean state, not the pre-delete state.

    SQLite doesn't actually need this (it commits flushed statements
    eagerly), but PostgreSQL transactions can hold the pre-delete rows
    visible to the same connection until flush — and our INSERTs would
    then collide. Belt-and-suspenders.
    """
    src = SEED_SCRIPT.read_text()
    body = src.split("def seed_sync_history(", 1)[1].split("\ndef ", 1)[0]
    # The delete block should be followed by a db.flush() before any add().
    delete_idx = body.find("db.query(Alert).delete(")
    flush_idx = body.find("db.flush()", delete_idx)
    add_idx = body.find("db.add(", delete_idx)
    assert delete_idx >= 0 and flush_idx >= 0 and add_idx >= 0, (
        "ct-cjg: expected delete → flush → add ordering"
    )
    assert flush_idx < add_idx, (
        "ct-cjg: db.flush() must come BEFORE the first db.add() to clear "
        "the pre-delete rows from the transaction's visibility"
    )
