"""Contract tests for first-wave browser smoke markers and docs."""

from pathlib import Path

import pytest

DOC_PATH = Path("docs/testing/browser_smoke_contract.md")

PAGE_MARKERS = [
    (
        "/login",
        "client",
        ['data-testid="login-shell"', 'data-testid="login-azure-entry"'],
    ),
    (
        "/dashboard",
        "authed_client",
        [
            'data-testid="dashboard-shell"',
            'data-testid="dashboard-kpi-summary"',
            'data-testid="dashboard-overview-grid"',
        ],
    ),
    (
        "/sync-dashboard",
        "authed_client",
        [
            'data-testid="sync-dashboard-shell"',
            'data-testid="sync-status-region"',
            'data-testid="sync-history-region"',
            'data-testid="tenant-sync-region"',
        ],
    ),
    (
        "/riverside",
        "authed_client",
        [
            'data-testid="riverside-shell"',
            'data-testid="riverside-executive-summary-region"',
            'data-testid="riverside-requirements-region"',
        ],
    ),
    (
        "/dmarc",
        "authed_client",
        [
            'data-testid="dmarc-shell"',
            'data-testid="dmarc-alert-banner"',
            'data-testid="dmarc-tenant-scores"',
        ],
    ),
]

PARTIAL_MARKERS = [
    ("/partials/sync-status-card", ['data-testid="sync-status-card"']),
    (
        "/partials/sync-history-table",
        [
            'data-testid="sync-history-table"',
            'data-testid="sync-history-table-grid"',
        ],
    ),
    ("/partials/active-alerts", ['data-testid="active-alerts-panel"']),
    ("/partials/tenant-sync-status", ['data-testid="tenant-sync-grid"']),
]

EMPTY_STATE_MARKERS = [
    ("app/templates/pages/dashboard.html", 'data-testid="dashboard-empty-state"'),
    (
        "app/templates/components/sync/sync_status_card.html",
        'data-testid="sync-status-empty-healthy"',
    ),
    (
        "app/templates/components/sync/sync_history_table.html",
        'data-testid="sync-history-empty-state"',
    ),
    (
        "app/templates/components/sync/active_alerts.html",
        'data-testid="active-alerts-empty-state"',
    ),
    (
        "app/templates/components/sync/tenant_sync_grid.html",
        'data-testid="tenant-sync-empty-state"',
    ),
]


class TestBrowserSmokeContractDocs:
    def test_contract_doc_exists(self):
        assert DOC_PATH.exists()

    def test_contract_doc_tracks_first_wave_routes_and_partials(self):
        content = DOC_PATH.read_text()
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
            "Deterministic empty-state rendering is healthy",
            "not the authoritative RBAC gate",
        ]:
            assert expected in content


class TestBrowserSmokeRouteMarkers:
    @pytest.mark.parametrize("path, fixture_name, markers", PAGE_MARKERS)
    def test_first_wave_pages_render_stable_markers(self, request, path, fixture_name, markers):
        http = request.getfixturevalue(fixture_name)
        resp = http.get(path)

        assert resp.status_code == 200
        assert "Internal Server Error" not in resp.text
        assert "Traceback" not in resp.text
        for marker in markers:
            assert marker in resp.text, f"missing {marker} on {path}"

    @pytest.mark.parametrize("path, markers", PARTIAL_MARKERS)
    def test_first_wave_partials_render_fragment_markers(self, authed_client, path, markers):
        resp = authed_client.get(path)

        assert resp.status_code == 200
        assert "Internal Server Error" not in resp.text
        assert "Traceback" not in resp.text
        for marker in markers:
            assert marker in resp.text, f"missing {marker} on {path}"


class TestBrowserSmokeEmptyStateMarkers:
    @pytest.mark.parametrize("file_path, marker", EMPTY_STATE_MARKERS)
    def test_empty_state_markers_exist_in_templates(self, file_path, marker):
        content = Path(file_path).read_text()
        assert marker in content
