"""Seed data script tests — verify seed_data.py creates all expected records.

Guards scripts/seed_data.py which populates 25 tables with 3,300+ demo records.
Uses subprocess to run the actual script against a temp SQLite file, then
queries that file to verify contents. This tests the REAL code path.

Coverage:
  - All 5 tenants created with correct brand configs
  - Cost data: snapshots, anomalies
  - Compliance data: snapshots, policy states
  - Resources: base, tags, idle detection
  - Identity: snapshots, privileged users
  - Sync: jobs, logs, metrics, alerts
  - Recommendations: cost + security
  - DMARC: records, DKIM, reports, alerts
  - Riverside: compliance, MFA, devices, threats, requirements
  - Data integrity: FK references, score ranges
"""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ── Shared Fixture ──────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.parent


@pytest.fixture(scope="module")
def seeded_db():
    """Run seed_data.py --force against a temp database, return a session.

    Scope=module so we pay the seed cost ONCE for all tests.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_seed.db")

        # Run the seed script with DATABASE_URL pointed at temp file
        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite:///{db_path}"

        result = subprocess.run(
            ["uv", "run", "python", "scripts/seed_data.py", "--force"],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert (
            result.returncode == 0
        ), f"seed_data.py failed!\nstdout: {result.stdout}\nstderr: {result.stderr}"
        assert "Seeding complete" in result.stdout, f"Unexpected output: {result.stdout}"

        # Connect to the seeded database
        engine = create_engine(f"sqlite:///{db_path}")
        Session = sessionmaker(bind=engine)
        session = Session()

        yield session

        session.close()
        engine.dispose()


def _count(session, table: str) -> int:
    """Count rows in a table."""
    return session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()


def _query(session, sql: str):
    """Run a SQL query and return all rows."""
    return session.execute(text(sql)).fetchall()


# ── Tenant Tests ────────────────────────────────────────────────
class TestTenants:
    """Verify all 5 HTT brand tenants are created."""

    def test_tenant_count(self, seeded_db):
        assert _count(seeded_db, "tenants") == 5

    def test_tenant_names(self, seeded_db):
        rows = _query(seeded_db, "SELECT name FROM tenants ORDER BY name")
        names = {r[0] for r in rows}
        expected = {
            "HTT Brands Corporate",
            "Bishops Cuts & Color",
            "Frenchies Modern Nail Care",
            "The Lash Lounge",
            "Delta Crown Enterprises",
        }
        assert names == expected

    def test_brand_configs_exist(self, seeded_db):
        assert _count(seeded_db, "brand_configs") == 5

    def test_brand_keys_correct(self, seeded_db):
        rows = _query(seeded_db, "SELECT brand_key FROM brand_configs")
        keys = {r[0] for r in rows}
        expected = {"httbrands", "bishops", "frenchies", "lashlounge", "deltacrown"}
        assert keys == expected

    def test_brand_colors_are_hex(self, seeded_db):
        rows = _query(seeded_db, "SELECT brand_key, primary_color FROM brand_configs")
        for key, color in rows:
            assert color and color.startswith("#"), f"{key} has invalid color: {color}"
            assert len(color) == 7, f"{key} color not #RRGGBB: {color}"

    def test_tenants_have_is_active(self, seeded_db):
        rows = _query(seeded_db, "SELECT name, is_active FROM tenants")
        for name, active in rows:
            assert active == 1, f"Tenant '{name}' is not active"


# ── Cost Data Tests ─────────────────────────────────────────────
class TestCostData:
    def test_cost_snapshots_exist(self, seeded_db):
        count = _count(seeded_db, "cost_snapshots")
        assert count >= 500, f"Expected >= 500 cost snapshots, got {count}"

    def test_cost_snapshots_have_positive_amounts(self, seeded_db):
        rows = _query(seeded_db, "SELECT total_cost FROM cost_snapshots LIMIT 20")
        for (total_cost,) in rows:
            assert total_cost > 0

    def test_cost_snapshots_usd_currency(self, seeded_db):
        rows = _query(seeded_db, "SELECT DISTINCT currency FROM cost_snapshots")
        currencies = {r[0] for r in rows}
        assert currencies == {"USD"}

    def test_cost_anomalies_exist(self, seeded_db):
        assert _count(seeded_db, "cost_anomalies") >= 1


# ── Compliance Data Tests ───────────────────────────────────────
class TestComplianceData:
    def test_compliance_snapshots_exist(self, seeded_db):
        count = _count(seeded_db, "compliance_snapshots")
        assert count >= 100, f"Expected >= 100, got {count}"

    def test_compliance_scores_in_range(self, seeded_db):
        rows = _query(
            seeded_db, "SELECT overall_compliance_percent FROM compliance_snapshots LIMIT 20"
        )
        for (score,) in rows:
            assert 0 <= score <= 100, f"Score out of range: {score}"

    def test_policy_states_exist(self, seeded_db):
        assert _count(seeded_db, "policy_states") >= 10


# ── Resource Data Tests ─────────────────────────────────────────
class TestResourceData:
    def test_resources_exist(self, seeded_db):
        assert _count(seeded_db, "resources") >= 100

    def test_resource_tags_exist(self, seeded_db):
        assert _count(seeded_db, "resource_tags") >= 200

    def test_idle_resources_exist(self, seeded_db):
        assert _count(seeded_db, "idle_resources") >= 10

    def test_idle_resources_have_savings(self, seeded_db):
        rows = _query(seeded_db, "SELECT estimated_monthly_savings FROM idle_resources LIMIT 5")
        for (savings,) in rows:
            assert savings > 0


# ── Identity Data Tests ─────────────────────────────────────────
class TestIdentityData:
    def test_identity_snapshots_exist(self, seeded_db):
        assert _count(seeded_db, "identity_snapshots") >= 100

    def test_privileged_users_exist(self, seeded_db):
        assert _count(seeded_db, "privileged_users") >= 10


# ── Sync Data Tests ─────────────────────────────────────────────
class TestSyncData:
    def test_sync_jobs_exist(self, seeded_db):
        assert _count(seeded_db, "sync_jobs") >= 50

    def test_sync_logs_exist(self, seeded_db):
        assert _count(seeded_db, "sync_job_logs") >= 50

    def test_sync_metrics_exist(self, seeded_db):
        assert _count(seeded_db, "sync_job_metrics") >= 1

    def test_alerts_exist(self, seeded_db):
        assert _count(seeded_db, "alerts") >= 1


# ── Recommendation Tests ────────────────────────────────────────
class TestRecommendations:
    def test_recommendations_exist(self, seeded_db):
        assert _count(seeded_db, "recommendations") >= 10


# ── DMARC Data Tests ────────────────────────────────────────────
class TestDMARCData:
    def test_dmarc_records_exist(self, seeded_db):
        assert _count(seeded_db, "dmarc_records") >= 5

    def test_dkim_records_exist(self, seeded_db):
        assert _count(seeded_db, "dkim_records") >= 5

    def test_dmarc_reports_exist(self, seeded_db):
        count = _count(seeded_db, "dmarc_reports")
        assert count >= 200, f"Expected >= 200 DMARC reports, got {count}"

    def test_dmarc_reports_have_valid_data(self, seeded_db):
        rows = _query(
            seeded_db,
            """
            SELECT messages_total, messages_passed, messages_failed, pct_compliant
            FROM dmarc_reports LIMIT 10
        """,
        )
        for total, passed, failed, pct in rows:
            assert total > 0
            assert passed >= 0
            assert failed >= 0
            assert 0 <= pct <= 100

    def test_dmarc_alerts_exist(self, seeded_db):
        assert _count(seeded_db, "dmarc_alerts") >= 1


# ── Riverside Data Tests ────────────────────────────────────────
class TestRiversideData:
    def test_compliance_records_exist(self, seeded_db):
        assert _count(seeded_db, "riverside_compliance") == 5

    def test_compliance_has_valid_scores(self, seeded_db):
        rows = _query(seeded_db, "SELECT overall_maturity_score FROM riverside_compliance")
        for (score,) in rows:
            assert score is not None
            assert 0 <= score <= 5, f"Maturity score out of range: {score}"

    def test_mfa_records_exist(self, seeded_db):
        assert _count(seeded_db, "riverside_mfa") == 5

    def test_mfa_coverage_valid(self, seeded_db):
        rows = _query(
            seeded_db,
            """
            SELECT total_users, mfa_enrolled_users, mfa_coverage_percentage
            FROM riverside_mfa
        """,
        )
        for total, enrolled, pct in rows:
            assert total >= enrolled, f"More enrolled than total: {enrolled} > {total}"
            assert 0 <= pct <= 100

    def test_device_compliance_exists(self, seeded_db):
        assert _count(seeded_db, "riverside_device_compliance") == 5

    def test_device_compliance_valid(self, seeded_db):
        rows = _query(
            seeded_db,
            """
            SELECT total_devices, compliance_percentage
            FROM riverside_device_compliance
        """,
        )
        for total, pct in rows:
            assert total > 0
            assert 0 <= pct <= 100

    def test_threat_data_exists(self, seeded_db):
        assert _count(seeded_db, "riverside_threat_data") == 5

    def test_requirements_exist(self, seeded_db):
        count = _count(seeded_db, "riverside_requirements")
        assert count >= 50, f"Expected >= 50 requirements, got {count}"

    def test_requirements_valid_status(self, seeded_db):
        rows = _query(seeded_db, "SELECT DISTINCT status FROM riverside_requirements")
        statuses = {r[0] for r in rows}
        valid = {"completed", "in_progress", "not_started", "blocked"}
        assert statuses.issubset(valid), f"Invalid statuses: {statuses - valid}"

    def test_requirements_have_owners(self, seeded_db):
        rows = _query(
            seeded_db,
            """
            SELECT requirement_id, owner FROM riverside_requirements
            WHERE owner IS NULL OR owner = ''
        """,
        )
        assert len(rows) == 0, f"{len(rows)} requirements have no owner"

    def test_requirements_cover_categories(self, seeded_db):
        rows = _query(seeded_db, "SELECT DISTINCT category FROM riverside_requirements")
        categories = {r[0] for r in rows}
        assert "IAM" in categories
        assert "GS" in categories
        assert "DS" in categories


# ── Cross-Cutting Integrity ─────────────────────────────────────
class TestDataIntegrity:
    def test_all_cost_snapshots_reference_valid_tenant(self, seeded_db):
        orphans = _query(
            seeded_db,
            """
            SELECT COUNT(*) FROM cost_snapshots cs
            LEFT JOIN tenants t ON cs.tenant_id = t.id
            WHERE t.id IS NULL
        """,
        )
        assert orphans[0][0] == 0, "Orphaned cost snapshots found"

    def test_all_riverside_data_references_valid_tenant(self, seeded_db):
        orphans = _query(
            seeded_db,
            """
            SELECT COUNT(*) FROM riverside_compliance rc
            LEFT JOIN tenants t ON rc.tenant_id = t.id
            WHERE t.id IS NULL
        """,
        )
        assert orphans[0][0] == 0, "Orphaned riverside compliance records"

    def test_all_dmarc_reports_reference_valid_tenant(self, seeded_db):
        orphans = _query(
            seeded_db,
            """
            SELECT COUNT(*) FROM dmarc_reports dr
            LEFT JOIN tenants t ON dr.tenant_id = t.id
            WHERE t.id IS NULL
        """,
        )
        assert orphans[0][0] == 0, "Orphaned DMARC reports"

    def test_total_record_count(self, seeded_db):
        """Overall record count should be in the 2500-5000 range."""
        tables = [
            "tenants",
            "brand_configs",
            "cost_snapshots",
            "cost_anomalies",
            "compliance_snapshots",
            "policy_states",
            "resources",
            "resource_tags",
            "idle_resources",
            "identity_snapshots",
            "privileged_users",
            "sync_jobs",
            "sync_job_logs",
            "sync_job_metrics",
            "alerts",
            "recommendations",
            "dmarc_records",
            "dkim_records",
            "dmarc_reports",
            "dmarc_alerts",
            "riverside_compliance",
            "riverside_mfa",
            "riverside_device_compliance",
            "riverside_threat_data",
            "riverside_requirements",
        ]
        total = sum(_count(seeded_db, t) for t in tables)
        assert total >= 2500, f"Expected >= 2500 total records, got {total}"

    def test_each_tenant_has_cost_data(self, seeded_db):
        """Every tenant should have at least some cost snapshots."""
        rows = _query(
            seeded_db,
            """
            SELECT t.name, COUNT(cs.id) AS cnt
            FROM tenants t
            LEFT JOIN cost_snapshots cs ON t.id = cs.tenant_id
            GROUP BY t.id
        """,
        )
        for name, cnt in rows:
            assert cnt > 0, f"Tenant '{name}' has no cost data"

    def test_each_tenant_has_compliance_data(self, seeded_db):
        """Every tenant should have compliance snapshots."""
        rows = _query(
            seeded_db,
            """
            SELECT t.name, COUNT(cs.id) AS cnt
            FROM tenants t
            LEFT JOIN compliance_snapshots cs ON t.id = cs.tenant_id
            GROUP BY t.id
        """,
        )
        for name, cnt in rows:
            assert cnt > 0, f"Tenant '{name}' has no compliance data"
