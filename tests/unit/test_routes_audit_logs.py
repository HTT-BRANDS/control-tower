"""Tests for app/api/routes/audit_logs.py — audit log endpoints.

Covers:
- GET /api/v1/audit-logs: list with filters, pagination, non-admin scoping
- GET /api/v1/audit-logs/summary: category counts

Phase B.9 of the test coverage sprint.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

_BASE = "/api/v1/audit-logs"
_TENANT = "test-tenant-123"
_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)


def _mock_entry(**overrides):
    defaults = {
        "id": "entry-1",
        "actor_id": "user-123",
        "actor_email": "test@example.com",
        "action": "auth.login.success",
        "tenant_id": _TENANT,
        "resource_type": "user",
        "status": "success",
        "timestamp": _NOW,
        "details": {},
    }
    defaults.update(overrides)
    entry = MagicMock()
    entry.to_dict.return_value = defaults
    return entry


# ---------------------------------------------------------------------------
# GET /api/v1/audit-logs
# ---------------------------------------------------------------------------


class TestListAuditLogs:
    @patch("app.api.routes.audit_logs.AuditLogService")
    def test_returns_entries(self, mock_svc_cls, authed_client):
        svc = MagicMock()
        mock_svc_cls.return_value = svc
        svc.query.return_value = [_mock_entry(), _mock_entry(id="entry-2")]
        svc.count.return_value = 2

        resp = authed_client.get(_BASE)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["entries"]) == 2
        assert data["total"] == 2
        assert data["has_more"] is False

    @patch("app.api.routes.audit_logs.AuditLogService")
    def test_pagination_has_more(self, mock_svc_cls, authed_client):
        svc = MagicMock()
        mock_svc_cls.return_value = svc
        svc.query.return_value = [_mock_entry()]
        svc.count.return_value = 150

        resp = authed_client.get(f"{_BASE}?limit=10&offset=0")

        assert resp.status_code == 200
        data = resp.json()
        assert data["has_more"] is True
        assert data["limit"] == 10
        assert data["offset"] == 0

    @patch("app.api.routes.audit_logs.AuditLogService")
    def test_action_filter(self, mock_svc_cls, authed_client):
        svc = MagicMock()
        mock_svc_cls.return_value = svc
        svc.query.return_value = []
        svc.count.return_value = 0

        resp = authed_client.get(f"{_BASE}?action=auth.login.success")

        assert resp.status_code == 200
        call_kwargs = svc.query.call_args.kwargs
        assert call_kwargs["action"] == "auth.login.success"

    @patch("app.api.routes.audit_logs.AuditLogService")
    def test_action_prefix_filter(self, mock_svc_cls, authed_client):
        svc = MagicMock()
        mock_svc_cls.return_value = svc
        svc.query.return_value = []
        svc.count.return_value = 0

        resp = authed_client.get(f"{_BASE}?action_prefix=auth.")

        assert resp.status_code == 200
        assert svc.query.call_args.kwargs["action_prefix"] == "auth."

    @patch("app.api.routes.audit_logs.AuditLogService")
    def test_empty_list(self, mock_svc_cls, authed_client):
        svc = MagicMock()
        mock_svc_cls.return_value = svc
        svc.query.return_value = []
        svc.count.return_value = 0

        resp = authed_client.get(_BASE)

        assert resp.status_code == 200
        assert resp.json()["entries"] == []
        assert resp.json()["total"] == 0

    def test_unauthenticated_returns_401(self, client):
        resp = client.get(_BASE)
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/audit-logs/summary
# ---------------------------------------------------------------------------


class TestAuditLogSummary:
    @patch("app.api.routes.audit_logs.AuditLogService")
    def test_returns_category_summary(self, mock_svc_cls, authed_client):
        svc = MagicMock()
        mock_svc_cls.return_value = svc
        # Return different counts for each category
        svc.count.side_effect = [10, 5, 3, 1, 8, 2]

        resp = authed_client.get(f"{_BASE}/summary")

        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["auth"] == 10
        assert data["summary"]["sync"] == 5
        assert data["total"] == 29  # 10+5+3+1+8+2

    @patch("app.api.routes.audit_logs.AuditLogService")
    def test_summary_with_tenant_filter(self, mock_svc_cls, authed_client):
        svc = MagicMock()
        mock_svc_cls.return_value = svc
        svc.count.return_value = 0

        resp = authed_client.get(f"{_BASE}/summary?tenant_id={_TENANT}")

        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == _TENANT

    def test_summary_unauthenticated(self, client):
        resp = client.get(f"{_BASE}/summary")
        assert resp.status_code == 401
