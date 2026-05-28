"""Integration tests for the franchise-coach Manager-tier dashboard.

Verifies:
- Manager + Admin can reach the dashboard
- Viewer / Analyst / TenantAdmin are forbidden (read-only design)
- CSV export honors franchise_coach:export
- Brand-voice copy renders in the page
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.auth import User, get_current_user
from app.core.database import get_db
from app.main import app


def _build_user(role: str) -> User:
    return User(
        id=f"user-{role}",
        email=f"{role}@example.com",
        name=f"{role.title()} User",
        roles=[role],
        tenant_ids=[],
        is_active=True,
        auth_provider="internal",
    )


@pytest.fixture
def client_for_role(seeded_db):
    """Factory: build a TestClient authenticated as a specific role."""

    def _build(role: str) -> TestClient:
        def override_db():
            try:
                yield seeded_db
            finally:
                pass

        async def override_user():
            return _build_user(role)

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = override_user
        return TestClient(app)

    yield _build
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "role,expected_status",
    [
        ("admin", 200),  # wildcard
        ("manager", 200),  # the headline role for this view
    ],
)
def test_authorized_roles_can_reach_dashboard(client_for_role, role, expected_status):
    client = client_for_role(role)
    resp = client.get("/franchise-coach")
    assert resp.status_code == expected_status
    assert b"Franchise Coach" in resp.content


@pytest.mark.parametrize("role", ["viewer", "analyst", "tenant_admin"])
def test_unauthorized_roles_blocked_from_dashboard(client_for_role, role):
    """Viewer, Analyst, and TenantAdmin do NOT get franchise-coach access.

    Per ADR-0012, this surface is Manager-tier only (plus Admin wildcard).
    TenantAdmin is intentionally excluded because the coach view crosses
    brand boundaries — only Manager and Admin should see across all brands.
    """
    client = client_for_role(role)
    resp = client.get("/franchise-coach")
    assert resp.status_code == 403, (
        f"{role} should be blocked from franchise-coach but got "
        f"{resp.status_code}: {resp.text[:200]}"
    )


def test_manager_can_export_csv(client_for_role):
    client = client_for_role("manager")
    resp = client.get("/franchise-coach/export.csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    body = resp.text
    # Header row must be present
    assert "brand,severity,mfa_coverage_pct" in body


def test_manager_can_hit_json_api(client_for_role):
    client = client_for_role("manager")
    resp = client.get("/franchise-coach/api")
    assert resp.status_code == 200
    data = resp.json()
    assert "brand_count" in data
    assert "cards" in data
    assert isinstance(data["cards"], list)


def test_dashboard_uses_brand_voice_copy(client_for_role):
    """Spot-check that the rendered page uses brand-voice phrasing."""
    client = client_for_role("manager")
    resp = client.get("/franchise-coach")
    assert resp.status_code == 200
    body = resp.text.lower()
    # 'coach' / 'standard' / 'conversation' are vocabulary from the framework
    assert "coach" in body or "coaching" in body
    assert "conversation" in body or "standard" in body
    # 'as an ai' / 'disruptive' / 'synergies' must NOT appear
    assert "as an ai" not in body
    assert "disruptive" not in body
    assert "synergies" not in body


def test_dashboard_links_to_adr(client_for_role):
    """The 'About this view' link points to ADR-0012."""
    client = client_for_role("manager")
    resp = client.get("/franchise-coach")
    assert resp.status_code == 200
    assert "adr-0012-manager-role-franchise-coach" in resp.text
