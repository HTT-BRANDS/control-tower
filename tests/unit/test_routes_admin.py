"""Tests for admin API routes.

Validates all 6 admin endpoints:
- GET    /api/v1/admin/users
- GET    /api/v1/admin/users/{user_id}
- PUT    /api/v1/admin/users/{user_id}/roles
- GET    /api/v1/admin/roles
- GET    /api/v1/admin/roles/{role_name}
- GET    /api/v1/admin/stats

Run: ``pytest tests/unit/test_routes_admin.py -v``
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.auth import User, get_current_user
from app.core.database import Base, get_db
from app.main import app
from app.models.tenant import Tenant, UserTenant

# ============================================================================
# Fixtures
# ============================================================================

_TEST_TENANT_ID = "test-tenant-aaa"
_SECOND_TENANT_ID = "test-tenant-bbb"


def _make_user(roles: list[str], user_id: str = "admin-user-1") -> User:
    return User(
        id=user_id,
        email="admin@example.com",
        name="Admin User",
        roles=roles,
        tenant_ids=[_TEST_TENANT_ID],
        is_active=True,
        auth_provider="internal",
    )


@pytest.fixture()
def _tables(db_session):
    """Ensure all tables exist in the test DB."""
    Base.metadata.create_all(bind=db_session.get_bind())
    yield


@pytest.fixture()
def seeded_db(db_session, _tables):
    """Seed tenants and user-tenant mappings for admin tests."""
    # -- Tenants --
    t1 = Tenant(
        id=_TEST_TENANT_ID,
        tenant_id=_TEST_TENANT_ID,
        name="Alpha Tenant",
        is_active=True,
    )
    t2 = Tenant(
        id=_SECOND_TENANT_ID,
        tenant_id=_SECOND_TENANT_ID,
        name="Bravo Tenant",
        is_active=True,
    )
    db_session.add_all([t1, t2])
    db_session.flush()

    # -- User-tenant mappings --
    mappings = [
        UserTenant(
            id=str(uuid.uuid4()),
            user_id="user-alice",
            tenant_id=_TEST_TENANT_ID,
            role="viewer",
            is_active=True,
        ),
        UserTenant(
            id=str(uuid.uuid4()),
            user_id="user-alice",
            tenant_id=_SECOND_TENANT_ID,
            role="viewer",
            is_active=True,
        ),
        UserTenant(
            id=str(uuid.uuid4()),
            user_id="user-bob",
            tenant_id=_TEST_TENANT_ID,
            role="analyst",
            is_active=True,
        ),
        UserTenant(
            id=str(uuid.uuid4()),
            user_id="user-carol",
            tenant_id=_TEST_TENANT_ID,
            role="tenant_admin",
            is_active=True,
        ),
        UserTenant(
            id=str(uuid.uuid4()),
            user_id="user-carol",
            tenant_id=_SECOND_TENANT_ID,
            role="tenant_admin",
            is_active=True,
        ),
    ]
    db_session.add_all(mappings)
    db_session.commit()
    return db_session


def _admin_client(seeded_db) -> TestClient:
    """TestClient authenticated as an admin user."""
    admin = _make_user(["admin"])

    def _override_db():
        try:
            yield seeded_db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)
    return client


def _viewer_client(seeded_db) -> TestClient:
    """TestClient authenticated as a viewer (non-admin)."""
    viewer = _make_user(["viewer"], user_id="viewer-user")

    def _override_db():
        try:
            yield seeded_db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: viewer
    client = TestClient(app)
    return client


# ============================================================================
# Auth enforcement — admin required
# ============================================================================


class TestAdminAuthEnforcement:
    """Non-admin users must get 403 on all admin endpoints."""

    def setup_method(self) -> None:
        app.dependency_overrides.clear()

    def teardown_method(self) -> None:
        app.dependency_overrides.clear()

    def test_viewer_cannot_list_users(self, seeded_db) -> None:
        client = _viewer_client(seeded_db)
        assert client.get("/api/v1/admin/users").status_code == 403

    def test_viewer_cannot_get_user(self, seeded_db) -> None:
        client = _viewer_client(seeded_db)
        assert client.get("/api/v1/admin/users/user-alice").status_code == 403

    def test_viewer_cannot_update_roles(self, seeded_db) -> None:
        client = _viewer_client(seeded_db)
        resp = client.put(
            "/api/v1/admin/users/user-alice/roles",
            json={"roles": ["analyst"]},
        )
        assert resp.status_code == 403

    def test_viewer_cannot_list_roles(self, seeded_db) -> None:
        client = _viewer_client(seeded_db)
        assert client.get("/api/v1/admin/roles").status_code == 403

    def test_viewer_cannot_get_role(self, seeded_db) -> None:
        client = _viewer_client(seeded_db)
        assert client.get("/api/v1/admin/roles/viewer").status_code == 403

    def test_viewer_cannot_get_stats(self, seeded_db) -> None:
        client = _viewer_client(seeded_db)
        assert client.get("/api/v1/admin/stats").status_code == 403

    def test_analyst_cannot_access(self, seeded_db) -> None:
        """Analyst (non-admin) also gets 403."""
        analyst = _make_user(["analyst"], user_id="analyst-user")

        def _db():
            try:
                yield seeded_db
            finally:
                pass

        app.dependency_overrides[get_db] = _db
        app.dependency_overrides[get_current_user] = lambda: analyst
        client = TestClient(app)
        assert client.get("/api/v1/admin/users").status_code == 403

    def test_tenant_admin_cannot_access(self, seeded_db) -> None:
        """Tenant admin does NOT have system:admin — denied."""
        ta = _make_user(["tenant_admin"], user_id="ta-user")

        def _db():
            try:
                yield seeded_db
            finally:
                pass

        app.dependency_overrides[get_db] = _db
        app.dependency_overrides[get_current_user] = lambda: ta
        client = TestClient(app)
        assert client.get("/api/v1/admin/users").status_code == 403


# ============================================================================
# GET /api/v1/admin/users
# ============================================================================


class TestListUsers:
    """Admin can list users with pagination, search, and role filter."""

    def setup_method(self) -> None:
        app.dependency_overrides.clear()

    def teardown_method(self) -> None:
        app.dependency_overrides.clear()

    def test_list_users_success(self, seeded_db) -> None:
        client = _admin_client(seeded_db)
        resp = client.get("/api/v1/admin/users")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3  # alice, bob, carol
        assert data["page"] == 1
        assert len(data["items"]) == 3

    def test_pagination(self, seeded_db) -> None:
        client = _admin_client(seeded_db)
        resp = client.get("/api/v1/admin/users?per_page=2&page=1")
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["pages"] == 2

        resp2 = client.get("/api/v1/admin/users?per_page=2&page=2")
        data2 = resp2.json()
        assert len(data2["items"]) == 1

    def test_search_by_user_id(self, seeded_db) -> None:
        client = _admin_client(seeded_db)
        resp = client.get("/api/v1/admin/users?search=alice")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["user_id"] == "user-alice"

    def test_filter_by_role(self, seeded_db) -> None:
        client = _admin_client(seeded_db)
        resp = client.get("/api/v1/admin/users?role=analyst")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["user_id"] == "user-bob"

    def test_alice_has_two_tenants(self, seeded_db) -> None:
        client = _admin_client(seeded_db)
        resp = client.get("/api/v1/admin/users?search=alice")
        data = resp.json()
        assert data["items"][0]["tenant_count"] == 2

    def test_empty_search_returns_zero(self, seeded_db) -> None:
        client = _admin_client(seeded_db)
        resp = client.get("/api/v1/admin/users?search=nonexistent")
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []


# ============================================================================
# GET /api/v1/admin/users/{user_id}
# ============================================================================


class TestGetUser:
    """Admin can retrieve full user detail."""

    def setup_method(self) -> None:
        app.dependency_overrides.clear()

    def teardown_method(self) -> None:
        app.dependency_overrides.clear()

    def test_get_user_success(self, seeded_db) -> None:
        client = _admin_client(seeded_db)
        resp = client.get("/api/v1/admin/users/user-alice")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "user-alice"
        assert "viewer" in data["roles"]
        assert len(data["tenant_access"]) == 2
        assert len(data["permissions"]) > 0

    def test_get_user_not_found(self, seeded_db) -> None:
        client = _admin_client(seeded_db)
        resp = client.get("/api/v1/admin/users/nonexistent")
        assert resp.status_code == 404

    def test_user_permissions_match_role(self, seeded_db) -> None:
        """Bob is an analyst — his permissions should include export perms."""
        client = _admin_client(seeded_db)
        resp = client.get("/api/v1/admin/users/user-bob")
        data = resp.json()
        assert "costs:read" in data["permissions"]
        assert "costs:export" in data["permissions"]
        # Analyst cannot manage
        assert "costs:manage" not in data["permissions"]


# ============================================================================
# PUT /api/v1/admin/users/{user_id}/roles
# ============================================================================


class TestUpdateUserRoles:
    """Admin can update roles; invalid roles are rejected."""

    def setup_method(self) -> None:
        app.dependency_overrides.clear()

    def teardown_method(self) -> None:
        app.dependency_overrides.clear()

    def test_update_roles_success(self, seeded_db) -> None:
        client = _admin_client(seeded_db)
        resp = client.put(
            "/api/v1/admin/users/user-alice/roles",
            json={"roles": ["analyst"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "analyst" in data["roles"]
        # Permissions should now include export
        assert "costs:export" in data["permissions"]

    def test_update_to_tenant_admin(self, seeded_db) -> None:
        client = _admin_client(seeded_db)
        resp = client.put(
            "/api/v1/admin/users/user-bob/roles",
            json={"roles": ["tenant_admin"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "tenant_admin" in data["roles"]
        assert "costs:manage" in data["permissions"]

    def test_multiple_roles_picks_highest(self, seeded_db) -> None:
        """When multiple roles given, highest privilege wins."""
        client = _admin_client(seeded_db)
        resp = client.put(
            "/api/v1/admin/users/user-alice/roles",
            json={"roles": ["viewer", "tenant_admin"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "tenant_admin" in data["roles"]

    def test_invalid_role_rejected(self, seeded_db) -> None:
        client = _admin_client(seeded_db)
        resp = client.put(
            "/api/v1/admin/users/user-alice/roles",
            json={"roles": ["superadmin"]},
        )
        assert resp.status_code == 400
        assert "Invalid role" in resp.json()["detail"]

    def test_empty_roles_rejected(self, seeded_db) -> None:
        client = _admin_client(seeded_db)
        resp = client.put(
            "/api/v1/admin/users/user-alice/roles",
            json={"roles": []},
        )
        assert resp.status_code == 422  # Pydantic min_length=1

    def test_update_nonexistent_user(self, seeded_db) -> None:
        client = _admin_client(seeded_db)
        resp = client.put(
            "/api/v1/admin/users/ghost/roles",
            json={"roles": ["viewer"]},
        )
        assert resp.status_code == 404

    def test_legacy_role_accepted(self, seeded_db) -> None:
        """Legacy 'operator' is accepted and mapped to tenant_admin."""
        client = _admin_client(seeded_db)
        resp = client.put(
            "/api/v1/admin/users/user-bob/roles",
            json={"roles": ["operator"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "tenant_admin" in data["roles"]


# ============================================================================
# GET /api/v1/admin/roles
# ============================================================================


class TestListRoles:
    """Admin can list all available roles."""

    def setup_method(self) -> None:
        app.dependency_overrides.clear()

    def teardown_method(self) -> None:
        app.dependency_overrides.clear()

    def test_list_roles_success(self, seeded_db) -> None:
        client = _admin_client(seeded_db)
        resp = client.get("/api/v1/admin/roles")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4
        slugs = {r["slug"] for r in data}
        assert slugs == {"admin", "tenant_admin", "analyst", "viewer"}

    def test_each_role_has_permissions(self, seeded_db) -> None:
        client = _admin_client(seeded_db)
        resp = client.get("/api/v1/admin/roles")
        for role in resp.json():
            assert role["permission_count"] > 0
            assert len(role["permissions"]) == role["permission_count"]

    def test_admin_role_has_all_permissions(self, seeded_db) -> None:
        client = _admin_client(seeded_db)
        resp = client.get("/api/v1/admin/roles")
        admin_role = next(r for r in resp.json() if r["slug"] == "admin")
        # Admin should have every permission in the registry
        assert admin_role["permission_count"] >= 30


# ============================================================================
# GET /api/v1/admin/roles/{role_name}
# ============================================================================


class TestGetRole:
    """Admin can get a single role's details."""

    def setup_method(self) -> None:
        app.dependency_overrides.clear()

    def teardown_method(self) -> None:
        app.dependency_overrides.clear()

    def test_get_viewer_role(self, seeded_db) -> None:
        client = _admin_client(seeded_db)
        resp = client.get("/api/v1/admin/roles/viewer")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "viewer"
        assert data["name"] == "Viewer"
        assert "costs:read" in data["permissions"]
        assert "costs:manage" not in data["permissions"]

    def test_get_analyst_role(self, seeded_db) -> None:
        client = _admin_client(seeded_db)
        resp = client.get("/api/v1/admin/roles/analyst")
        assert resp.status_code == 200
        data = resp.json()
        assert "costs:export" in data["permissions"]

    def test_unknown_role_returns_404(self, seeded_db) -> None:
        client = _admin_client(seeded_db)
        resp = client.get("/api/v1/admin/roles/superadmin")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ============================================================================
# GET /api/v1/admin/stats
# ============================================================================


class TestAdminStats:
    """Admin can get aggregate platform statistics."""

    def setup_method(self) -> None:
        app.dependency_overrides.clear()

    def teardown_method(self) -> None:
        app.dependency_overrides.clear()

    def test_stats_success(self, seeded_db) -> None:
        client = _admin_client(seeded_db)
        resp = client.get("/api/v1/admin/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_users"] == 3
        assert data["active_tenants"] == 2
        assert data["total_tenants"] == 2
        assert data["total_user_tenant_mappings"] == 5

    def test_users_by_role(self, seeded_db) -> None:
        client = _admin_client(seeded_db)
        resp = client.get("/api/v1/admin/stats")
        by_role = resp.json()["users_by_role"]
        assert by_role.get("viewer") == 1  # alice
        assert by_role.get("analyst") == 1  # bob
        assert by_role.get("tenant_admin") == 1  # carol
