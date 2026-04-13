"""Fitness function tests for sync data integrity (ADR-0010).

These architectural fitness functions ensure the production data sync
fixes from ADR-0010 remain in place and cannot silently regress:

- FF-1: policy_name column is wide enough for Azure Policy names
- FF-2: safe_truncate exists and is used in sync modules
- FF-3: Sync modules use per-tenant session isolation
- FF-4: Scheduler IntervalTrigger jobs fire on startup
- FF-5: Dead SyncService stub stays removed
- FF-6: Migration 009 exists and references policy_name
"""

import ast
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYNC_DIR = PROJECT_ROOT / "app" / "core" / "sync"
MIGRATIONS_DIR = PROJECT_ROOT / "alembic" / "versions"


class TestSyncDataIntegrity:
    """ADR-0010 fitness functions for sync data integrity."""

    def test_ff1_policy_name_column_width_minimum(self):
        """FF-1: PolicyState.policy_name column must be >= 1000 chars.

        The original String(255) caused DataError overflow that poisoned
        the SQLAlchemy session, cascading to kill ALL sync jobs.
        """
        from app.models.compliance import PolicyState

        # Get the column definition
        column = PolicyState.__table__.columns["policy_name"]
        assert column.type.length >= 1000, (
            f"policy_name column is String({column.type.length}) but must be >= 1000. "
            f"ADR-0010 requires this to prevent DataError overflow from long Azure Policy names."
        )

    def test_ff2_safe_truncate_exists_and_is_used(self):
        """FF-2: safe_truncate must exist and be imported in compliance sync.

        The safe_truncate helper provides audit-logged truncation for
        oversized field values (STRIDE T-1, R-1 compliance).
        """
        # Verify the utility module exists
        utils_path = SYNC_DIR / "utils.py"
        assert utils_path.exists(), (
            "app/core/sync/utils.py is missing. "
            "ADR-0010 requires safe_truncate for auditable field truncation."
        )

        # Verify safe_truncate function exists
        from app.core.sync.utils import safe_truncate

        assert callable(safe_truncate), "safe_truncate must be a callable function"

        # Verify it's imported in compliance.py
        compliance_source = (SYNC_DIR / "compliance.py").read_text()
        assert "safe_truncate" in compliance_source, (
            "compliance.py must import and use safe_truncate. "
            "ADR-0010 requires truncation with audit logging for policy fields."
        )

        # Verify it handles None, within-limit, and over-limit correctly
        assert safe_truncate(None, 100, "test") is None
        assert safe_truncate("short", 100, "test") == "short"
        assert safe_truncate("x" * 200, 100, "test") == "x" * 100

    def test_ff3_sync_modules_use_per_tenant_sessions(self):
        """FF-3: Sync modules must use per-tenant get_db_context() sessions.

        The old pattern wrapped all tenants in ONE session. If one tenant
        caused a DataError, the session was poisoned for ALL remaining tenants.
        Per ADR-0010, each tenant must get a fresh session.
        """
        # These 5 modules iterate tenants and must have per-tenant sessions
        tenant_iterating_modules = ["compliance", "costs", "resources", "identity", "dmarc"]

        for module_name in tenant_iterating_modules:
            source = (SYNC_DIR / f"{module_name}.py").read_text()

            # Parse the AST to verify structural pattern
            tree = ast.parse(source)

            # Find the main sync function
            sync_funcs = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.AsyncFunctionDef) and node.name.startswith("sync_")
            ]
            assert sync_funcs, f"{module_name}.py must have an async sync_* function"

            # Verify tenant_data extraction pattern exists
            assert "tenant_data" in source, (
                f"{module_name}.py must extract tenant_data tuples before iterating. "
                f"ADR-0010 requires per-tenant session isolation."
            )

            # Verify get_db_context appears multiple times (not just once wrapping everything)
            db_context_count = source.count("get_db_context()")
            assert db_context_count >= 3, (
                f"{module_name}.py has only {db_context_count} get_db_context() calls. "
                f"Expected >= 3 (tenant list + per-tenant + monitoring). "
                f"ADR-0010 requires per-tenant session isolation."
            )

    def test_ff4_scheduler_jobs_have_next_run_time(self):
        """FF-4: All IntervalTrigger scheduler jobs must have next_run_time.

        Without next_run_time, sync jobs don't fire until their first interval
        elapses (hours later), leaving dashboards empty after deployment.
        """
        scheduler_source = (PROJECT_ROOT / "app" / "core" / "scheduler.py").read_text()

        # Count IntervalTrigger jobs
        interval_count = scheduler_source.count("IntervalTrigger(")
        assert interval_count >= 5, f"Expected >= 5 IntervalTrigger jobs, found {interval_count}"

        # Count next_run_time assignments
        next_run_count = scheduler_source.count("next_run_time=")
        assert next_run_count >= 5, (
            f"Expected >= 5 next_run_time assignments, found {next_run_count}. "
            f"ADR-0010 requires staggered immediate sync on startup."
        )

        # Verify staggered timing (timedelta should appear)
        assert "timedelta" in scheduler_source, (
            "scheduler.py must use timedelta for staggered startup timing"
        )

    def test_ff5_sync_service_stub_removed(self):
        """FF-5: Dead SyncService stub must stay removed.

        The SyncService in app/api/services/sync_service.py was placeholder
        code (every method returned mock data). It must not be recreated.
        """
        stub_path = PROJECT_ROOT / "app" / "api" / "services" / "sync_service.py"
        assert not stub_path.exists(), (
            "app/api/services/sync_service.py still exists! "
            "ADR-0010 removed this dead stub. Do not recreate it."
        )

    def test_ff6_migration_009_exists(self):
        """FF-6: Alembic migration 009 must exist and reference policy_name.

        This migration widens policy_name from String(255) to String(1000).
        Without it, the entrypoint's `alembic upgrade head` won't apply the fix.
        """
        migration_path = MIGRATIONS_DIR / "009_widen_policy_name.py"
        assert migration_path.exists(), (
            "alembic/versions/009_widen_policy_name.py is missing! "
            "ADR-0010 requires this migration to widen policy_name to 1000 chars."
        )

        migration_source = migration_path.read_text()
        assert "policy_name" in migration_source, "Migration 009 must reference policy_name column"
        assert "1000" in migration_source, "Migration 009 must set policy_name to String(1000)"
        # Verify revision chain
        assert "down_revision" in migration_source, (
            "Migration 009 must have a down_revision for Alembic chain integrity"
        )
