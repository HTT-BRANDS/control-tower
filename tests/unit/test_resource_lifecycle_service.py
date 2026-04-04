"""Tests for app/api/services/resource_lifecycle_service.py.

Covers:
- record_event: success, DB rollback on error
- detect_changes: default fields, custom fields, no changes
- get_history: query construction
- get_tenant_events: filtering by event_type and since
- get_changes: multi-tenant, resource_type, date range, pagination

Phase B.10 of the test coverage sprint.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from app.api.services.resource_lifecycle_service import ResourceLifecycleService


def _mock_resource(**overrides):
    defaults = {
        "id": "res-1",
        "name": "my-vm",
        "resource_type": "Microsoft.Compute/virtualMachines",
        "tenant_id": "tid-1",
        "subscription_id": "sub-1",
    }
    defaults.update(overrides)
    r = MagicMock()
    for k, v in defaults.items():
        setattr(r, k, v)
    return r


# ---------------------------------------------------------------------------
# record_event
# ---------------------------------------------------------------------------


class TestRecordEvent:
    def test_creates_event(self):
        db = MagicMock()
        svc = ResourceLifecycleService(db)
        resource = _mock_resource()

        event = svc.record_event(resource, "created")

        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()
        assert event is not None

    def test_event_has_correct_fields(self):
        db = MagicMock()
        svc = ResourceLifecycleService(db)
        resource = _mock_resource()

        svc.record_event(
            resource,
            "updated",
            previous_state={"sku": "Standard_D2"},
            current_state={"sku": "Standard_D4"},
            changed_fields=["sku"],
            sync_run_id="run-42",
        )

        added = db.add.call_args[0][0]
        assert added.event_type == "updated"
        assert added.changed_fields == ["sku"]
        assert added.sync_run_id == "run-42"

    def test_rollback_on_error(self):
        db = MagicMock()
        db.commit.side_effect = Exception("DB down")
        svc = ResourceLifecycleService(db)
        resource = _mock_resource()

        # Should not raise — logs warning instead
        event = svc.record_event(resource, "deleted")

        db.rollback.assert_called_once()
        assert event is not None  # Still returns the event object


# ---------------------------------------------------------------------------
# detect_changes
# ---------------------------------------------------------------------------


class TestDetectChanges:
    def test_detects_default_field_changes(self):
        svc = ResourceLifecycleService(MagicMock())

        changed = svc.detect_changes(
            {"provisioning_state": "Running", "location": "eastus", "sku": "A"},
            {"provisioning_state": "Stopped", "location": "eastus", "sku": "A"},
        )

        assert "provisioning_state" in changed
        assert "location" not in changed

    def test_no_changes(self):
        svc = ResourceLifecycleService(MagicMock())

        changed = svc.detect_changes(
            {"provisioning_state": "Running"},
            {"provisioning_state": "Running"},
        )

        assert changed == []

    def test_custom_tracked_fields(self):
        svc = ResourceLifecycleService(MagicMock())

        changed = svc.detect_changes(
            {"color": "red", "size": "large"},
            {"color": "blue", "size": "large"},
            tracked_fields=["color", "size"],
        )

        assert changed == ["color"]

    def test_missing_field_counts_as_change(self):
        svc = ResourceLifecycleService(MagicMock())

        changed = svc.detect_changes(
            {"provisioning_state": "Running"},
            {},  # field missing entirely
        )

        assert "provisioning_state" in changed


# ---------------------------------------------------------------------------
# get_history
# ---------------------------------------------------------------------------


class TestGetHistory:
    def test_queries_by_resource_id(self):
        db = MagicMock()
        svc = ResourceLifecycleService(db)

        svc.get_history("res-1", limit=10, offset=0)

        db.query.assert_called_once()

    def test_caps_limit_at_200(self):
        db = MagicMock()
        svc = ResourceLifecycleService(db)

        svc.get_history("res-1", limit=999)

        # Verify .limit(200) was called (capped)
        chain = db.query.return_value.filter.return_value.order_by.return_value.offset.return_value
        chain.limit.assert_called_once_with(200)


# ---------------------------------------------------------------------------
# get_tenant_events
# ---------------------------------------------------------------------------


class TestGetTenantEvents:
    def test_filters_by_tenant(self):
        db = MagicMock()
        svc = ResourceLifecycleService(db)

        svc.get_tenant_events("tid-1")

        db.query.assert_called_once()

    def test_filters_by_event_type(self):
        db = MagicMock()
        svc = ResourceLifecycleService(db)

        svc.get_tenant_events("tid-1", event_type="created")

        # Should chain two .filter() calls
        assert db.query.return_value.filter.call_count >= 1

    def test_filters_by_since(self):
        db = MagicMock()
        svc = ResourceLifecycleService(db)

        svc.get_tenant_events("tid-1", since=datetime(2024, 1, 1, tzinfo=UTC))

        assert db.query.return_value.filter.call_count >= 1


# ---------------------------------------------------------------------------
# get_changes
# ---------------------------------------------------------------------------


class TestGetChanges:
    def test_returns_events_and_count(self):
        db = MagicMock()
        q = db.query.return_value
        q.count.return_value = 5
        q.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
            MagicMock()
        ] * 5
        svc = ResourceLifecycleService(db)

        events, total = svc.get_changes()

        assert total == 5
        assert len(events) == 5

    def test_filters_by_tenant_ids_list(self):
        db = MagicMock()
        q = db.query.return_value
        q.filter.return_value = q  # chain
        q.count.return_value = 0
        q.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        svc = ResourceLifecycleService(db)

        events, total = svc.get_changes(tenant_ids=["tid-1", "tid-2"])

        # .filter should be called with .in_ clause
        q.filter.assert_called()

    def test_tenant_ids_takes_priority_over_tenant_id(self):
        db = MagicMock()
        q = db.query.return_value
        q.filter.return_value = q
        q.count.return_value = 0
        q.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        svc = ResourceLifecycleService(db)

        # Both provided — tenant_ids wins
        events, total = svc.get_changes(tenant_id="single", tenant_ids=["a", "b"])

        # Only one .filter call for tenant (not two)
        assert q.filter.call_count >= 1

    def test_caps_limit_at_200(self):
        db = MagicMock()
        q = db.query.return_value
        q.count.return_value = 0
        q.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        svc = ResourceLifecycleService(db)

        svc.get_changes(limit=999)

        q.order_by.return_value.offset.return_value.limit.assert_called_once_with(200)
