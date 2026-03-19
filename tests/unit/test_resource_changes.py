"""Unit tests for RM-010: cross-resource change feed.

Covers:
- ResourceLifecycleService.get_changes() — all filter paths + limit cap
- GET /api/v1/resources/changes — registration, auth, happy path, filter params,
  and tenant isolation (events scoped to accessible tenants only)
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

# ============================================================================
# Helpers
# ============================================================================


def _make_db():
    db = MagicMock()
    db.add.return_value = None
    db.commit.return_value = None
    db.rollback.return_value = None
    return db


def _setup_query(db, *, events=None, total=0):
    """Wire up a mock SQLAlchemy query chain that returns (events, total)."""
    events = events or []
    mock_q = MagicMock()
    mock_q.filter.return_value = mock_q
    mock_q.order_by.return_value = mock_q
    mock_q.offset.return_value = mock_q
    mock_q.limit.return_value = mock_q
    mock_q.count.return_value = total
    mock_q.all.return_value = events
    db.query.return_value = mock_q
    return mock_q


def _make_event(
    resource_id="res-001",
    tenant_id="tenant-001",
    resource_type="Microsoft.Compute/virtualMachines",
    event_type="created",
):
    """Build a minimal mock ResourceLifecycleEvent."""
    e = MagicMock()
    e.resource_id = resource_id
    e.tenant_id = tenant_id
    e.resource_type = resource_type
    e.event_type = event_type
    e.detected_at = datetime.now(UTC)
    e.to_dict.return_value = {
        "id": "evt-001",
        "resource_id": resource_id,
        "tenant_id": tenant_id,
        "resource_type": resource_type,
        "event_type": event_type,
        "detected_at": e.detected_at.isoformat(),
    }
    return e


# ============================================================================
# Service-layer tests
# ============================================================================


class TestGetChangesService:
    """Tests for ResourceLifecycleService.get_changes()."""

    def test_happy_path_returns_tuple_of_list_and_int(self):
        """Default call returns (list[events], int) with no filters."""
        from app.api.services.resource_lifecycle_service import ResourceLifecycleService

        db = _make_db()
        ev = _make_event()
        _setup_query(db, events=[ev], total=1)

        svc = ResourceLifecycleService(db)
        events, total = svc.get_changes()

        assert isinstance(events, list)
        assert isinstance(total, int)
        assert total == 1
        assert events[0] is ev

    def test_filter_by_tenant_id_adds_filter(self):
        """Passing tenant_id causes an extra .filter() call."""
        from app.api.services.resource_lifecycle_service import ResourceLifecycleService

        db = _make_db()
        mock_q = _setup_query(db)

        svc = ResourceLifecycleService(db)
        svc.get_changes(tenant_id="tenant-abc")

        # At least one filter must have been applied
        assert mock_q.filter.call_count >= 1

    def test_filter_by_resource_type_adds_filter(self):
        """Passing resource_type causes an extra .filter() call."""
        from app.api.services.resource_lifecycle_service import ResourceLifecycleService

        db = _make_db()
        mock_q = _setup_query(db)

        svc = ResourceLifecycleService(db)
        svc.get_changes(resource_type="Microsoft.Storage/storageAccounts")

        assert mock_q.filter.call_count >= 1

    def test_filter_by_event_type_adds_filter(self):
        """Passing event_type causes an extra .filter() call."""
        from app.api.services.resource_lifecycle_service import ResourceLifecycleService

        db = _make_db()
        mock_q = _setup_query(db)

        svc = ResourceLifecycleService(db)
        svc.get_changes(event_type="deleted")

        assert mock_q.filter.call_count >= 1

    def test_filter_by_date_range_applies_both_bounds(self):
        """Passing since AND until applies two date-range filters."""
        from app.api.services.resource_lifecycle_service import ResourceLifecycleService

        db = _make_db()
        mock_q = _setup_query(db)

        since = datetime(2026, 1, 1, tzinfo=UTC)
        until = datetime(2026, 3, 1, tzinfo=UTC)

        svc = ResourceLifecycleService(db)
        svc.get_changes(since=since, until=until)

        # since + until → 2 filter calls
        assert mock_q.filter.call_count >= 2

    def test_empty_result_set(self):
        """Returns empty list and zero total when no events exist."""
        from app.api.services.resource_lifecycle_service import ResourceLifecycleService

        db = _make_db()
        _setup_query(db, events=[], total=0)

        svc = ResourceLifecycleService(db)
        events, total = svc.get_changes()

        assert events == []
        assert total == 0

    def test_limit_clamped_to_200(self):
        """limit values above 200 are silently capped at 200."""
        from app.api.services.resource_lifecycle_service import ResourceLifecycleService

        db = _make_db()
        mock_q = _setup_query(db)

        svc = ResourceLifecycleService(db)
        svc.get_changes(limit=9999)

        mock_q.limit.assert_called_with(200)

    def test_pagination_uses_offset(self):
        """offset parameter is forwarded to the query."""
        from app.api.services.resource_lifecycle_service import ResourceLifecycleService

        db = _make_db()
        mock_q = _setup_query(db)

        svc = ResourceLifecycleService(db)
        svc.get_changes(offset=100)

        mock_q.offset.assert_called_with(100)

    def test_all_filters_combined(self):
        """All filters active → 5 filter calls (tenant + resource_type + event_type + since + until)."""
        from app.api.services.resource_lifecycle_service import ResourceLifecycleService

        db = _make_db()
        mock_q = _setup_query(db, events=[_make_event()], total=1)

        svc = ResourceLifecycleService(db)
        events, total = svc.get_changes(
            tenant_id="t-1",
            resource_type="Microsoft.Compute/virtualMachines",
            event_type="updated",
            since=datetime(2026, 1, 1, tzinfo=UTC),
            until=datetime(2026, 6, 1, tzinfo=UTC),
        )

        # 5 filters: tenant + resource_type + event_type + since + until
        assert mock_q.filter.call_count == 5
        assert total == 1


# ============================================================================
# Route-level tests
# ============================================================================


class TestResourceChangesRoute:
    """Tests for GET /api/v1/resources/changes."""

    def test_changes_route_is_registered(self, client):
        """Route must exist — unauthenticated request must NOT return 404."""
        response = client.get("/api/v1/resources/changes")
        assert response.status_code != 404

    def test_changes_route_requires_auth(self, client):
        """Unauthenticated request returns 401."""
        response = client.get("/api/v1/resources/changes")
        assert response.status_code in (401, 403)

    def test_changes_route_authenticated_returns_200(self, authed_client):
        """Authenticated request returns 200 with expected response shape."""
        response = authed_client.get("/api/v1/resources/changes")
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["events"], list)
        assert isinstance(data["total"], int)

    def test_changes_route_default_limit_is_50(self, authed_client):
        """Default limit in response should be 50."""
        response = authed_client.get("/api/v1/resources/changes")
        assert response.status_code == 200
        assert response.json()["limit"] == 50

    def test_changes_route_accepts_filter_params(self, authed_client):
        """Valid filter query params are accepted without validation errors."""
        response = authed_client.get(
            "/api/v1/resources/changes"
            "?resource_type=Microsoft.Compute%2FvirtualMachines"
            "&event_type=created"
            "&limit=10"
            "&offset=0"
        )
        assert response.status_code == 200

    def test_changes_route_accepts_date_filters(self, authed_client):
        """ISO datetime since/until params are accepted."""
        response = authed_client.get(
            "/api/v1/resources/changes?since=2026-01-01T00:00:00&until=2026-12-31T23:59:59"
        )
        assert response.status_code == 200

    @patch("app.api.services.resource_lifecycle_service.ResourceLifecycleService")
    def test_changes_route_returns_events_from_service(self, mock_svc_cls, authed_client):
        """Route correctly serializes events returned by the service."""
        ev = _make_event(resource_id="res-xyz", event_type="deleted")
        mock_svc = MagicMock()
        mock_svc.get_changes.return_value = ([ev], 1)
        mock_svc_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/resources/changes")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["events"]) == 1
        assert data["events"][0]["resource_id"] == "res-xyz"
        assert data["events"][0]["event_type"] == "deleted"

    @patch("app.api.services.resource_lifecycle_service.ResourceLifecycleService")
    def test_changes_scoped_to_accessible_tenants(self, mock_svc_cls, authed_client):
        """Without tenant_id, events are scoped to accessible tenants — not the whole DB.

        The authed_client fixture sets accessible_tenant_ids = ["test-tenant-123"].
        Verifies get_changes is called with tenant_ids=["test-tenant-123"], ensuring
        events from other tenants are never returned.
        """
        mock_svc = MagicMock()
        mock_svc.get_changes.return_value = ([], 0)
        mock_svc_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/resources/changes")
        assert response.status_code == 200

        call_kwargs = mock_svc.get_changes.call_args.kwargs
        assert "tenant_ids" in call_kwargs, "Route must pass tenant_ids for isolation"
        # The mock_authz fixture exposes accessible_tenant_ids = ["test-tenant-123"]
        assert call_kwargs["tenant_ids"] == ["test-tenant-123"]

    def test_changes_route_limit_le_200_enforced(self, authed_client):
        """Requesting limit > 200 should return 422 (FastAPI validation)."""
        response = authed_client.get("/api/v1/resources/changes?limit=201")
        assert response.status_code == 422
