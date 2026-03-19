"""Unit tests for AuditLogService — CM-010."""

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock


def _make_db():
    """Build a mock db session."""
    db = MagicMock()
    db.add.return_value = None
    db.commit.return_value = None
    db.refresh.return_value = None
    db.rollback.return_value = None
    return db


def _make_entries(count: int = 3):
    """Build mock AuditLogEntry objects."""
    from app.models.audit_log import AuditLogEntry

    entries = []
    for i in range(count):
        e = AuditLogEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            actor_id=f"user-{i}",
            actor_email=f"user{i}@example.com",
            action="auth.login.success",
            status="success",
        )
        entries.append(e)
    return entries


class TestAuditLogServiceWriteEntry:
    """Tests for AuditLogService.write_entry()."""

    def test_write_entry_creates_record(self):
        """write_entry should add an AuditLogEntry to the db session."""
        from app.api.services.audit_log_service import AuditLogService

        db = _make_db()
        service = AuditLogService(db)
        entry = service.write_entry("auth.login.success", actor_email="a@b.com")
        db.add.assert_called_once()
        db.commit.assert_called_once()
        assert entry.action == "auth.login.success"

    def test_write_entry_generates_uuid(self):
        """Every write_entry call must produce a unique UUID id."""
        from app.api.services.audit_log_service import AuditLogService

        db = _make_db()
        service = AuditLogService(db)
        e1 = service.write_entry("sync.triggered")
        e2 = service.write_entry("sync.triggered")
        assert e1.id != e2.id

    def test_write_entry_sets_timestamp(self):
        """Timestamp should be set to a recent UTC datetime."""
        from app.api.services.audit_log_service import AuditLogService

        db = _make_db()
        service = AuditLogService(db)
        before = datetime.now(UTC)
        entry = service.write_entry("sync.triggered")
        after = datetime.now(UTC)
        assert before <= entry.timestamp <= after

    def test_write_entry_extracts_ip_from_request(self):
        """IP address should be extracted from X-Forwarded-For header."""
        from app.api.services.audit_log_service import AuditLogService

        db = _make_db()
        service = AuditLogService(db)
        mock_req = MagicMock()
        mock_req.headers.get.side_effect = lambda k, d=None: (
            "1.2.3.4, 5.6.7.8" if k == "X-Forwarded-For" else None
        )
        mock_req.client = None
        entry = service.write_entry("auth.login.success", request=mock_req)
        assert entry.ip_address == "1.2.3.4"

    def test_write_entry_survives_db_failure(self):
        """write_entry must not raise even if db.commit() raises."""
        from app.api.services.audit_log_service import AuditLogService

        db = _make_db()
        db.commit.side_effect = Exception("DB down")
        service = AuditLogService(db)
        # Must not raise
        service.write_entry("sync.failed", status="failure")
        db.rollback.assert_called_once()

    def test_write_entry_all_fields(self):
        """All optional fields should be stored when provided."""
        from app.api.services.audit_log_service import AuditLogService

        db = _make_db()
        service = AuditLogService(db)
        entry = service.write_entry(
            "bulk.update",
            actor_id="user-123",
            actor_email="admin@example.com",
            resource_type="resource",
            resource_id="res-456",
            tenant_id="tenant-789",
            status="success",
            detail="Updated 50 resources",
            metadata={"count": 50},
            ip_address="10.0.0.1",
            user_agent="Mozilla/5.0",
        )
        assert entry.actor_id == "user-123"
        assert entry.actor_email == "admin@example.com"
        assert entry.resource_type == "resource"
        assert entry.tenant_id == "tenant-789"
        assert entry.metadata_json == {"count": 50}

    def test_write_entry_user_agent_from_request(self):
        """User-Agent should be extracted from request headers."""
        from app.api.services.audit_log_service import AuditLogService

        db = _make_db()
        service = AuditLogService(db)
        mock_req = MagicMock()
        mock_req.headers.get.side_effect = lambda k, d=None: (
            "TestBrowser/1.0" if k == "User-Agent" else None
        )
        mock_req.client = None
        entry = service.write_entry("auth.logout", request=mock_req)
        assert entry.user_agent == "TestBrowser/1.0"

    def test_write_entry_kwargs_override_request(self):
        """Explicit ip_address kwarg should take precedence over request header."""
        from app.api.services.audit_log_service import AuditLogService

        db = _make_db()
        service = AuditLogService(db)
        mock_req = MagicMock()
        mock_req.headers.get.side_effect = lambda k, d=None: (
            "9.9.9.9" if k == "X-Forwarded-For" else None
        )
        entry = service.write_entry("auth.login.success", ip_address="1.1.1.1", request=mock_req)
        assert entry.ip_address == "1.1.1.1"


class TestAuditLogServiceQuery:
    """Tests for AuditLogService.query() filtering."""

    def _setup_query(self, db, return_value):
        """Wire the mock db query chain to return a given list."""
        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.offset.return_value = mock_q
        mock_q.limit.return_value = mock_q
        mock_q.all.return_value = return_value
        mock_q.count.return_value = len(return_value)
        db.query.return_value = mock_q
        return mock_q

    def test_query_returns_list(self):
        """query() should always return a list."""
        from app.api.services.audit_log_service import AuditLogService

        db = _make_db()
        entries = _make_entries(3)
        self._setup_query(db, entries)
        service = AuditLogService(db)
        result = service.query()
        assert isinstance(result, list)
        assert len(result) == 3

    def test_query_limit_capped_at_500(self):
        """Limit must be capped at 500 regardless of input."""
        from app.api.services.audit_log_service import AuditLogService

        db = _make_db()
        mock_q = self._setup_query(db, [])
        service = AuditLogService(db)
        service.query(limit=9999)
        mock_q.limit.assert_called_with(500)

    def test_query_empty_result(self):
        """query() should return [] when no records match."""
        from app.api.services.audit_log_service import AuditLogService

        db = _make_db()
        self._setup_query(db, [])
        service = AuditLogService(db)
        result = service.query(actor_id="nonexistent")
        assert result == []

    def test_count_returns_integer(self):
        """count() should return an integer."""
        from app.api.services.audit_log_service import AuditLogService

        db = _make_db()
        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.count.return_value = 42
        db.query.return_value = mock_q
        service = AuditLogService(db)
        assert service.count() == 42

    def test_query_applies_offset(self):
        """offset param should be forwarded to the query chain."""
        from app.api.services.audit_log_service import AuditLogService

        db = _make_db()
        mock_q = self._setup_query(db, [])
        service = AuditLogService(db)
        service.query(offset=50)
        mock_q.offset.assert_called_with(50)


class TestAuditAction:
    """Tests for AuditAction constants."""

    def test_all_action_categories_present(self):
        """All expected action category prefixes must exist."""
        from app.api.services.audit_log_service import AuditAction

        all_actions = [v for k, v in vars(AuditAction).items() if not k.startswith("_")]
        prefixes = {a.split(".")[0] for a in all_actions}
        assert "auth" in prefixes
        assert "sync" in prefixes
        assert "bulk" in prefixes
        assert "compliance" in prefixes

    def test_action_constants_are_strings(self):
        """All AuditAction class attributes should be strings."""
        from app.api.services.audit_log_service import AuditAction

        for k, v in vars(AuditAction).items():
            if not k.startswith("_") and not callable(v):
                assert isinstance(v, str), f"{k} is not a string"

    def test_login_success_constant(self):
        """LOGIN_SUCCESS should be the canonical auth login success string."""
        from app.api.services.audit_log_service import AuditAction

        assert AuditAction.LOGIN_SUCCESS == "auth.login.success"

    def test_sync_triggered_constant(self):
        """SYNC_TRIGGERED should follow the sync.X pattern."""
        from app.api.services.audit_log_service import AuditAction

        assert AuditAction.SYNC_TRIGGERED.startswith("sync.")


class TestAuditLogRoutes:
    """Integration tests for audit log API routes."""

    def test_list_audit_logs_requires_auth(self, client):
        """GET /api/v1/audit-logs without auth should return 401 or 403."""
        response = client.get("/api/v1/audit-logs")
        assert response.status_code in (401, 403)

    def test_list_audit_logs_authenticated(self, authed_client):
        """GET /api/v1/audit-logs with auth should return 200."""
        response = authed_client.get("/api/v1/audit-logs")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "total" in data
        assert "limit" in data
        assert "has_more" in data

    def test_audit_log_summary_authenticated(self, authed_client):
        """GET /api/v1/audit-logs/summary should return category counts."""
        response = authed_client.get("/api/v1/audit-logs/summary")
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "total" in data
        assert "auth" in data["summary"]
        assert "sync" in data["summary"]

    def test_list_audit_logs_pagination_params(self, authed_client):
        """limit and offset query params should be accepted."""
        response = authed_client.get("/api/v1/audit-logs?limit=10&offset=0")
        assert response.status_code == 200

    def test_list_audit_logs_filter_params(self, authed_client):
        """Filter params should be accepted without error."""
        response = authed_client.get(
            "/api/v1/audit-logs?action_prefix=auth.&status=success&limit=5"
        )
        assert response.status_code == 200
