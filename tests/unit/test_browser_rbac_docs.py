"""Contract checks for first-wave browser RBAC documentation."""

from pathlib import Path

RBAC_DOC = Path("docs/testing/browser_rbac_matrix.md")
SMOKE_DOC = Path("docs/testing/browser_smoke_contract.md")
INTEGRATION_TEST = Path("tests/integration/test_riverside_api.py")


class TestBrowserRbacDocs:
    def test_rbac_matrix_doc_exists(self):
        assert RBAC_DOC.exists()

    def test_rbac_matrix_tracks_first_wave_routes_and_protected_action(self):
        content = RBAC_DOC.read_text()
        for expected in [
            "/login",
            "/dashboard",
            "/sync-dashboard",
            "/riverside",
            "/dmarc",
            "/partials/sync-status-card",
            "/partials/sync-history-table",
            "/partials/active-alerts",
            "/partials/tenant-sync-status",
            "/api/v1/riverside/sync",
            "integration RBAC negative check for `reader`",
        ]:
            assert expected in content

    def test_smoke_doc_explicitly_says_rbac_is_separate(self):
        content = SMOKE_DOC.read_text()
        assert "not the authoritative RBAC gate" in content
        assert "docs/testing/browser_rbac_matrix.md" in content

    def test_integration_test_contains_reader_deny_path(self):
        content = INTEGRATION_TEST.read_text()
        assert "def test_sync_requires_admin_or_operator" in content
        assert "riverside_reader_client" in content
        assert "Riverside sync requires operator or admin role" in content
