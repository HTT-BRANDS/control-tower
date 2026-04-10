"""Unit tests for Azure Service Health data models.

Pure dataclass/enum tests — no mocking needed.

Coverage:
 1. IncidentSeverity — has exactly 4 members
 2. IncidentSeverity — CRITICAL value is "Critical"
 3. IncidentSeverity — ERROR value is "Error"
 4. IncidentSeverity — WARNING value is "Warning"
 5. IncidentSeverity — INFORMATIONAL value is "Informational"
 6. IncidentStatus — has exactly 4 members
 7. IncidentStatus — ACTIVE value is "Active"
 8. IncidentStatus — RESOLVED value is "Resolved"
 9. IncidentStatus — MITIGATED / IN_PROGRESS values
10. ResourceHealthStatus — all 4 values present
11. ServiceHealthIncident — duration_minutes with resolution_time
12. ServiceHealthIncident — duration_minutes None without resolution_time
13. ServiceHealthIncident — is_resolved True for RESOLVED status
14. ServiceHealthIncident — is_resolved True for MITIGATED status
15. ServiceHealthIncident — is_resolved False for ACTIVE status
16. ServiceHealthIncident — is_platform_impacting True for matching service
17. ServiceHealthIncident — is_platform_impacting False for non-matching service
18. ServiceHealthIncident — to_dict() serialization round-trip
19. ServiceHealthIncident — to_dict() with None resolution_time
20. ResourceHealthEvent — to_dict() serialization
21. ResourceHealthEvent — to_dict() with None previous_status
22. HealthAlert — construction with defaults
23. HealthAlert — construction with explicit values
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.azure_service_health import (
    HealthAlert,
    IncidentSeverity,
    IncidentStatus,
    ResourceHealthEvent,
    ResourceHealthStatus,
    ServiceHealthIncident,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 4, 3, 12, 0, 0)
ONE_HOUR_LATER = NOW + timedelta(hours=1)
TWO_HOURS_LATER = NOW + timedelta(hours=2)


def _make_incident(**overrides) -> ServiceHealthIncident:
    """Build a ServiceHealthIncident with sensible defaults."""
    defaults = {
        "incident_id": "INC-001",
        "correlation_id": "CORR-001",
        "title": "Test Incident",
        "summary": "Something went wrong",
        "severity": IncidentSeverity.WARNING,
        "status": IncidentStatus.ACTIVE,
        "service": "App Service",
        "region": "East US",
        "start_time": NOW,
        "last_update_time": ONE_HOUR_LATER,
    }
    defaults.update(overrides)
    return ServiceHealthIncident(**defaults)


def _make_resource_health_event(**overrides) -> ResourceHealthEvent:
    """Build a ResourceHealthEvent with sensible defaults."""
    defaults = {
        "resource_id": "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-1",
        "resource_name": "vm-1",
        "resource_type": "Microsoft.Compute/virtualMachines",
        "resource_group": "rg-1",
        "status": ResourceHealthStatus.AVAILABLE,
        "event_type": "AvailabilityStateChange",
        "occurred_time": NOW,
    }
    defaults.update(overrides)
    return ResourceHealthEvent(**defaults)


# ---------------------------------------------------------------------------
# IncidentSeverity
# ---------------------------------------------------------------------------


class TestIncidentSeverity:
    """Tests for the IncidentSeverity enum."""

    def test_has_exactly_four_members(self):
        assert len(IncidentSeverity) == 4

    def test_critical_value(self):
        assert IncidentSeverity.CRITICAL.value == "Critical"

    def test_error_value(self):
        assert IncidentSeverity.ERROR.value == "Error"

    def test_warning_value(self):
        assert IncidentSeverity.WARNING.value == "Warning"

    def test_informational_value(self):
        assert IncidentSeverity.INFORMATIONAL.value == "Informational"


# ---------------------------------------------------------------------------
# IncidentStatus
# ---------------------------------------------------------------------------


class TestIncidentStatus:
    """Tests for the IncidentStatus enum."""

    def test_has_exactly_four_members(self):
        assert len(IncidentStatus) == 4

    def test_active_value(self):
        assert IncidentStatus.ACTIVE.value == "Active"

    def test_resolved_value(self):
        assert IncidentStatus.RESOLVED.value == "Resolved"

    def test_mitigated_value(self):
        assert IncidentStatus.MITIGATED.value == "Mitigated"

    def test_in_progress_value(self):
        assert IncidentStatus.IN_PROGRESS.value == "InProgress"


# ---------------------------------------------------------------------------
# ResourceHealthStatus
# ---------------------------------------------------------------------------


class TestResourceHealthStatus:
    """Tests for the ResourceHealthStatus enum."""

    def test_all_values_present(self):
        expected = {"Available", "Unavailable", "Degraded", "Unknown"}
        actual = {m.value for m in ResourceHealthStatus}
        assert actual == expected


# ---------------------------------------------------------------------------
# ServiceHealthIncident
# ---------------------------------------------------------------------------


class TestServiceHealthIncident:
    """Tests for the ServiceHealthIncident dataclass."""

    def test_duration_minutes_with_resolution(self):
        incident = _make_incident(
            start_time=NOW,
            resolution_time=NOW + timedelta(minutes=90),
        )
        assert incident.duration_minutes == pytest.approx(90.0)

    def test_duration_minutes_none_without_resolution(self):
        incident = _make_incident(resolution_time=None)
        assert incident.duration_minutes is None

    def test_is_resolved_true_for_resolved(self):
        incident = _make_incident(status=IncidentStatus.RESOLVED)
        assert incident.is_resolved is True

    def test_is_resolved_true_for_mitigated(self):
        incident = _make_incident(status=IncidentStatus.MITIGATED)
        assert incident.is_resolved is True

    def test_is_resolved_false_for_active(self):
        incident = _make_incident(status=IncidentStatus.ACTIVE)
        assert incident.is_resolved is False

    def test_is_resolved_false_for_in_progress(self):
        incident = _make_incident(status=IncidentStatus.IN_PROGRESS)
        assert incident.is_resolved is False

    def test_is_platform_impacting_true_for_matching_service(self):
        """App Service is in the platform_services list."""
        incident = _make_incident(service="App Service")
        assert incident.is_platform_impacting is True

    def test_is_platform_impacting_case_insensitive(self):
        """Match should be case-insensitive."""
        incident = _make_incident(service="azure sql")
        assert incident.is_platform_impacting is True

    def test_is_platform_impacting_false_for_nonmatching_service(self):
        incident = _make_incident(service="Cosmos DB")
        assert incident.is_platform_impacting is False

    def test_to_dict_full(self):
        incident = _make_incident(
            incident_id="INC-99",
            correlation_id="CORR-99",
            title="Outage in East US",
            summary="Storage degraded",
            severity=IncidentSeverity.CRITICAL,
            status=IncidentStatus.RESOLVED,
            service="Storage",
            region="East US",
            start_time=NOW,
            last_update_time=ONE_HOUR_LATER,
            resolution_time=TWO_HOURS_LATER,
            tracking_id="TRK-99",
            impact="High impact",
            affected_services=["Storage", "Key Vault"],
        )
        d = incident.to_dict()

        assert d["incident_id"] == "INC-99"
        assert d["correlation_id"] == "CORR-99"
        assert d["title"] == "Outage in East US"
        assert d["summary"] == "Storage degraded"
        assert d["severity"] == "Critical"
        assert d["status"] == "Resolved"
        assert d["service"] == "Storage"
        assert d["region"] == "East US"
        assert d["start_time"] == NOW.isoformat()
        assert d["last_update_time"] == ONE_HOUR_LATER.isoformat()
        assert d["resolution_time"] == TWO_HOURS_LATER.isoformat()
        assert d["tracking_id"] == "TRK-99"
        assert d["impact"] == "High impact"
        assert d["duration_minutes"] == pytest.approx(120.0)
        assert d["is_platform_impacting"] is True
        assert d["affected_services"] == ["Storage", "Key Vault"]

    def test_to_dict_none_resolution(self):
        incident = _make_incident(resolution_time=None)
        d = incident.to_dict()
        assert d["resolution_time"] is None
        assert d["duration_minutes"] is None

    def test_default_fields(self):
        """Optional / default fields initialise correctly."""
        incident = _make_incident()
        assert incident.resolution_time is None
        assert incident.tracking_id is None
        assert incident.impact == ""
        assert incident.updates == []
        assert incident.affected_services == []


# ---------------------------------------------------------------------------
# ResourceHealthEvent
# ---------------------------------------------------------------------------


class TestResourceHealthEvent:
    """Tests for the ResourceHealthEvent dataclass."""

    def test_to_dict_with_previous_status(self):
        event = _make_resource_health_event(
            previous_status=ResourceHealthStatus.UNAVAILABLE,
            description="VM recovered",
            reason_chronicity="Transient",
            reason_type="Unplanned",
            recommended_actions=[{"action": "Monitor"}],
        )
        d = event.to_dict()

        assert d["resource_id"].endswith("vm-1")
        assert d["resource_name"] == "vm-1"
        assert d["resource_type"] == "Microsoft.Compute/virtualMachines"
        assert d["resource_group"] == "rg-1"
        assert d["status"] == "Available"
        assert d["previous_status"] == "Unavailable"
        assert d["event_type"] == "AvailabilityStateChange"
        assert d["occurred_time"] == NOW.isoformat()
        assert d["description"] == "VM recovered"
        assert d["reason_chronicity"] == "Transient"
        assert d["reason_type"] == "Unplanned"
        assert d["recommended_actions"] == [{"action": "Monitor"}]

    def test_to_dict_none_previous_status(self):
        event = _make_resource_health_event(previous_status=None)
        d = event.to_dict()
        assert d["previous_status"] is None


# ---------------------------------------------------------------------------
# HealthAlert
# ---------------------------------------------------------------------------


class TestHealthAlert:
    """Tests for the HealthAlert dataclass."""

    def test_construction_with_defaults(self):
        alert = HealthAlert(
            alert_type="service_health",
            severity_threshold=IncidentSeverity.WARNING,
            notify_channels=["teams"],
        )
        assert alert.alert_type == "service_health"
        assert alert.severity_threshold is IncidentSeverity.WARNING
        assert alert.notify_channels == ["teams"]
        assert alert.webhook_urls == {}
        assert alert.enabled is True

    def test_construction_with_explicit_values(self):
        alert = HealthAlert(
            alert_type="platform_impact",
            severity_threshold=IncidentSeverity.CRITICAL,
            notify_channels=["slack", "email"],
            webhook_urls={"slack": "https://hooks.slack.com/xxx"},
            enabled=False,
        )
        assert alert.alert_type == "platform_impact"
        assert alert.severity_threshold is IncidentSeverity.CRITICAL
        assert alert.notify_channels == ["slack", "email"]
        assert alert.webhook_urls == {"slack": "https://hooks.slack.com/xxx"}
        assert alert.enabled is False
