"""Unit tests for ResourceLifecycleService — RM-004."""

from unittest.mock import MagicMock


def _make_resource(resource_id: str = "res-001", tenant_id: str = "tenant-001"):
    r = MagicMock()
    r.id = resource_id
    r.name = "test-vm"
    r.resource_type = "Microsoft.Compute/virtualMachines"
    r.tenant_id = tenant_id
    r.subscription_id = "sub-001"
    return r


def _make_db():
    db = MagicMock()
    db.add.return_value = None
    db.commit.return_value = None
    db.refresh.return_value = None
    db.rollback.return_value = None
    return db


class TestResourceLifecycleServiceRecordEvent:
    def test_record_event_created(self):
        from app.api.services.resource_lifecycle_service import ResourceLifecycleService

        db = _make_db()
        svc = ResourceLifecycleService(db)
        resource = _make_resource()
        event = svc.record_event(resource, "created")
        assert event.event_type == "created"
        assert event.resource_id == "res-001"
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_record_event_generates_uuid(self):
        from app.api.services.resource_lifecycle_service import ResourceLifecycleService

        db = _make_db()
        svc = ResourceLifecycleService(db)
        resource = _make_resource()
        e1 = svc.record_event(resource, "created")
        e2 = svc.record_event(resource, "updated")
        assert e1.id != e2.id

    def test_record_event_survives_db_failure(self):
        from app.api.services.resource_lifecycle_service import ResourceLifecycleService

        db = _make_db()
        db.commit.side_effect = Exception("DB error")
        svc = ResourceLifecycleService(db)
        resource = _make_resource()
        svc.record_event(resource, "deleted")  # Must not raise
        db.rollback.assert_called_once()

    def test_record_event_stores_changed_fields(self):
        from app.api.services.resource_lifecycle_service import ResourceLifecycleService

        db = _make_db()
        svc = ResourceLifecycleService(db)
        resource = _make_resource()
        event = svc.record_event(
            resource,
            "updated",
            previous_state={"provisioning_state": "Succeeded"},
            current_state={"provisioning_state": "Deallocated"},
            changed_fields=["provisioning_state"],
        )
        assert event.changed_fields == ["provisioning_state"]


class TestResourceLifecycleServiceDetectChanges:
    def test_detect_no_changes(self):
        from app.api.services.resource_lifecycle_service import ResourceLifecycleService

        db = _make_db()
        svc = ResourceLifecycleService(db)
        state = {"provisioning_state": "Succeeded", "location": "eastus"}
        assert svc.detect_changes(state, state) == []

    def test_detect_provisioning_state_change(self):
        from app.api.services.resource_lifecycle_service import ResourceLifecycleService

        db = _make_db()
        svc = ResourceLifecycleService(db)
        prev = {"provisioning_state": "Succeeded"}
        curr = {"provisioning_state": "Deallocated"}
        changed = svc.detect_changes(prev, curr)
        assert "provisioning_state" in changed

    def test_detect_multiple_changes(self):
        from app.api.services.resource_lifecycle_service import ResourceLifecycleService

        db = _make_db()
        svc = ResourceLifecycleService(db)
        prev = {"provisioning_state": "Succeeded", "location": "eastus", "is_orphaned": False}
        curr = {"provisioning_state": "Deallocated", "location": "westus", "is_orphaned": True}
        changed = svc.detect_changes(prev, curr)
        assert len(changed) == 3

    def test_detect_with_custom_tracked_fields(self):
        from app.api.services.resource_lifecycle_service import ResourceLifecycleService

        db = _make_db()
        svc = ResourceLifecycleService(db)
        prev = {"sku": "B1", "tags_json": "{}"}
        curr = {"sku": "B2", "tags_json": "{}"}
        changed = svc.detect_changes(prev, curr, tracked_fields=["sku"])
        assert changed == ["sku"]


class TestResourceLifecycleServiceQuery:
    def _setup_query(self, db, return_value):
        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.offset.return_value = mock_q
        mock_q.limit.return_value = mock_q
        mock_q.all.return_value = return_value
        db.query.return_value = mock_q
        return mock_q

    def test_get_history_returns_list(self):
        from app.api.services.resource_lifecycle_service import ResourceLifecycleService

        db = _make_db()
        self._setup_query(db, [])
        svc = ResourceLifecycleService(db)
        result = svc.get_history("res-001")
        assert isinstance(result, list)

    def test_get_history_limit_capped_at_200(self):
        from app.api.services.resource_lifecycle_service import ResourceLifecycleService

        db = _make_db()
        mock_q = self._setup_query(db, [])
        svc = ResourceLifecycleService(db)
        svc.get_history("res-001", limit=9999)
        mock_q.limit.assert_called_with(200)

    def test_get_tenant_events_returns_list(self):
        from app.api.services.resource_lifecycle_service import ResourceLifecycleService

        db = _make_db()
        self._setup_query(db, [])
        svc = ResourceLifecycleService(db)
        result = svc.get_tenant_events("tenant-001")
        assert isinstance(result, list)


class TestResourceHistoryRoute:
    def test_history_route_registered(self, client):
        """GET /api/v1/resources/{id}/history must be registered (not 404)."""
        response = client.get("/api/v1/resources/some-id/history")
        assert response.status_code != 404

    def test_history_route_requires_auth(self, client):
        """Route must return 401/403 without authentication."""
        response = client.get("/api/v1/resources/some-id/history")
        assert response.status_code in (401, 403)

    def test_history_route_authenticated(self, authed_client):
        """Authenticated request returns 200 with events list."""
        response = authed_client.get("/api/v1/resources/test-resource-id/history")
        assert response.status_code == 200
        data = response.json()
        assert "resource_id" in data
        assert "events" in data
        assert isinstance(data["events"], list)
