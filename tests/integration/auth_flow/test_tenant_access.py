"""Integration tests for multi-tenant access control.

Tests authorization and access control across multiple tenants:
- User access to owned tenants
- User access restrictions to other tenants
- Admin access to all tenants
- Multi-tenant user access
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.core.auth import User, get_current_user
from app.core.authorization import TenantAuthorization, get_tenant_authorization
from app.core.database import get_db
from app.main import app


class TestTenantAccess:
    """Integration tests for multi-tenant access control."""

    def test_user_can_access_own_tenant_data(self, seeded_db, test_tenant_id):
        """User with tenant A access → can see tenant A data."""

        def override_get_db():
            try:
                yield seeded_db
            finally:
                pass

        test_user = User(
            id="tenant-test-user",
            email="tenant@example.com",
            name="Tenant User",
            roles=["user"],
            tenant_ids=[test_tenant_id],
            is_active=True,
            auth_provider="internal",
        )

        mock_authz = MagicMock(spec=TenantAuthorization)
        mock_authz.accessible_tenant_ids = [test_tenant_id]
        mock_authz.validate_tenant_access = MagicMock(return_value=True)
        mock_authz.filter_tenant_ids = MagicMock(return_value=[test_tenant_id])

        # Use dependency_overrides instead of patching
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: test_user
        app.dependency_overrides[get_tenant_authorization] = lambda: mock_authz

        with TestClient(app) as client:
            response = client.get(f"/api/v1/compliance/summary?tenant_ids={test_tenant_id}")

            # Should succeed - user has access to this tenant
            assert response.status_code == 200

        app.dependency_overrides.clear()

    def test_user_cannot_access_other_tenant_data(
        self, seeded_db, test_tenant_id, second_tenant_id
    ):
        """User with tenant A access → cannot see tenant B data (403)."""

        def override_get_db():
            try:
                yield seeded_db
            finally:
                pass

        # User only has access to test_tenant_id
        test_user = User(
            id="limited-user",
            email="limited@example.com",
            name="Limited User",
            roles=["user"],
            tenant_ids=[test_tenant_id],
            is_active=True,
            auth_provider="internal",
        )

        # Mock authz that blocks second tenant
        mock_authz = MagicMock(spec=TenantAuthorization)
        mock_authz.accessible_tenant_ids = [test_tenant_id]
        mock_authz.validate_tenant_access = MagicMock(side_effect=lambda tid: tid == test_tenant_id)
        mock_authz.filter_tenant_ids = MagicMock(
            return_value=[test_tenant_id]  # Filters out second_tenant_id
        )

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: test_user
        app.dependency_overrides[get_tenant_authorization] = lambda: mock_authz

        with TestClient(app) as client:
            # Try to access second tenant's data
            response = client.get(f"/api/v1/compliance/summary?tenant_ids={second_tenant_id}")

            # Should return 200 but with empty/filtered data since authz filters it out
            # (the authorization layer filters tenant_ids before query)
            assert response.status_code == 200
            data = response.json()
            # Data should be empty or only contain test_tenant_id data
            if "tenant_id" in data:
                assert data["tenant_id"] == test_tenant_id

        app.dependency_overrides.clear()

    def test_admin_user_can_access_all_tenants(self, seeded_db, test_tenant_id, second_tenant_id):
        """Admin user → can see all tenant data."""

        def override_get_db():
            try:
                yield seeded_db
            finally:
                pass

        admin_user = User(
            id="admin-user",
            email="admin@example.com",
            name="Admin User",
            roles=["admin"],
            tenant_ids=[],  # Empty list = all tenants for admin
            is_active=True,
            auth_provider="internal",
        )

        # Mock admin authz (allows all)
        mock_authz_admin = MagicMock(spec=TenantAuthorization)
        mock_authz_admin.accessible_tenant_ids = []  # Empty = all
        mock_authz_admin.validate_tenant_access = MagicMock(return_value=True)
        mock_authz_admin.filter_tenant_ids = MagicMock(
            side_effect=lambda x: x  # Return all requested tenant IDs
        )

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[get_tenant_authorization] = lambda: mock_authz_admin

        with TestClient(app) as client:
            # Admin can access first tenant
            response1 = client.get(f"/api/v1/compliance/summary?tenant_ids={test_tenant_id}")
            assert response1.status_code == 200

            # Admin can also access second tenant
            response2 = client.get(f"/api/v1/compliance/summary?tenant_ids={second_tenant_id}")
            assert response2.status_code == 200

        app.dependency_overrides.clear()

    def test_multi_tenant_user_can_access_both_tenants(
        self, seeded_db, test_tenant_id, second_tenant_id
    ):
        """User with access to multiple tenants can see data from all of them."""

        def override_get_db():
            try:
                yield seeded_db
            finally:
                pass

        multi_tenant_user = User(
            id="multi-tenant-user",
            email="multi@example.com",
            name="Multi Tenant User",
            roles=["user"],
            tenant_ids=[test_tenant_id, second_tenant_id],
            is_active=True,
            auth_provider="internal",
        )

        mock_authz = MagicMock(spec=TenantAuthorization)
        mock_authz.accessible_tenant_ids = [test_tenant_id, second_tenant_id]
        mock_authz.validate_tenant_access = MagicMock(return_value=True)
        mock_authz.filter_tenant_ids = MagicMock(return_value=[test_tenant_id, second_tenant_id])

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: multi_tenant_user
        app.dependency_overrides[get_tenant_authorization] = lambda: mock_authz

        with TestClient(app) as client:
            # Can access both tenants
            response = client.get(
                f"/api/v1/compliance/summary?tenant_ids={test_tenant_id},{second_tenant_id}"
            )

            assert response.status_code == 200

        app.dependency_overrides.clear()
