"""Comprehensive unit tests for tenant authorization and access control.

Tests cover:
- TenantAccessError exception
- get_user_tenants() for admin and token-based users
- get_user_tenant_ids() tenant ID extraction
- validate_tenant_access() access validation
- validate_tenants_access() bulk validation
- TenantAuthorization class methods
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from app.core.auth import User
from app.core.authorization import (
    TenantAccessError,
    TenantAuthorization,
    get_user_tenants,
    get_user_tenant_ids,
    validate_tenant_access,
    validate_tenants_access,
)


# =============================================================================
# Test Fixtures & Helpers
# =============================================================================

def make_user(roles=None, tenant_ids=None, user_id="user-1"):
    """Create a test user with specified roles and tenant access."""
    return User(
        id=user_id,
        email="test@example.com",
        name="Test User",
        roles=roles or ["user"],
        tenant_ids=tenant_ids or [],
    )


def make_mock_tenant(tenant_id, is_active=True):
    """Create a mock tenant object."""
    tenant = MagicMock()
    tenant.tenant_id = tenant_id
    tenant.is_active = is_active
    return tenant


# =============================================================================
# Test 1: TenantAccessError - Exception Attributes
# =============================================================================

class TestTenantAccessError:
    """Test TenantAccessError exception with tenant_id and user_id attributes."""

    def test_exception_stores_tenant_and_user_ids(self):
        """Test that TenantAccessError stores tenant_id and user_id attributes."""
        err = TenantAccessError(tenant_id="tenant-123", user_id="user-456")
        
        assert err.tenant_id == "tenant-123"
        assert err.user_id == "user-456"
        assert "user-456" in str(err)
        assert "tenant-123" in str(err)
        assert isinstance(err, Exception)


# =============================================================================
# Test 2-3: get_user_tenants() - Admin vs Token Users
# =============================================================================

class TestGetUserTenants:
    """Test get_user_tenants() for admin and token-based access."""

    def test_admin_gets_all_tenants(self):
        """Test that admin users get access to all tenants."""
        admin_user = make_user(roles=["admin"])
        db = MagicMock()
        
        # Mock the query chain for admin users
        mock_query = MagicMock()
        tenants = [make_mock_tenant("t-1"), make_mock_tenant("t-2"), make_mock_tenant("t-3")]
        mock_query.filter.return_value.all.return_value = tenants
        mock_query.all.return_value = tenants
        db.query.return_value = mock_query
        
        result = get_user_tenants(admin_user, db)
        
        # Admin should get all tenants
        assert len(result) == 3
        assert result[0].tenant_id == "t-1"

    def test_token_user_gets_specific_tenants(self):
        """Test that users with tenant_ids in token get only those tenants."""
        token_user = make_user(tenant_ids=["t-1", "t-2"])
        db = MagicMock()
        
        # Mock the query chain for token-based access
        mock_query = MagicMock()
        tenants = [make_mock_tenant("t-1"), make_mock_tenant("t-2")]
        mock_query.filter.return_value.filter.return_value.all.return_value = tenants
        mock_query.filter.return_value.all.return_value = tenants
        db.query.return_value = mock_query
        
        result = get_user_tenants(token_user, db)
        
        # Token user should only get their assigned tenants
        assert len(result) == 2
        assert all(t.tenant_id in ["t-1", "t-2"] for t in result)


# =============================================================================
# Test 4: get_user_tenant_ids() - Extract Tenant IDs
# =============================================================================

class TestGetUserTenantIds:
    """Test get_user_tenant_ids() returns list of tenant_id strings."""

    @patch("app.core.authorization.get_user_tenants")
    def test_returns_list_of_tenant_id_strings(self, mock_get_tenants):
        """Test that get_user_tenant_ids returns [t.tenant_id for t in tenants]."""
        mock_get_tenants.return_value = [
            make_mock_tenant("tenant-a"),
            make_mock_tenant("tenant-b"),
            make_mock_tenant("tenant-c"),
        ]
        
        user = make_user()
        db = MagicMock()
        
        result = get_user_tenant_ids(user, db)
        
        # Should extract tenant_id strings from tenant objects
        assert result == ["tenant-a", "tenant-b", "tenant-c"]
        assert all(isinstance(tid, str) for tid in result)


# =============================================================================
# Test 5-7: validate_tenant_access() - Admin, Valid, and Invalid Access
# =============================================================================

class TestValidateTenantAccess:
    """Test validate_tenant_access() for various access scenarios."""

    def test_admin_always_has_access(self):
        """Test that admin users always return True for tenant access."""
        admin_user = make_user(roles=["admin"])
        db = MagicMock()
        
        # Admin should have access to any tenant
        assert validate_tenant_access(admin_user, "any-tenant-id", db) is True
        assert validate_tenant_access(admin_user, "another-tenant", db) is True

    def test_valid_token_tenant_returns_true(self):
        """Test that users with matching tenant_id in token get access."""
        token_user = make_user(tenant_ids=["t-1", "t-2", "t-3"])
        db = MagicMock()
        
        # User should have access to their token tenants
        assert validate_tenant_access(token_user, "t-1", db) is True
        assert validate_tenant_access(token_user, "t-2", db) is True

    def test_no_access_raises_http_exception_403(self):
        """Test that users without access get HTTPException with 403 status."""
        limited_user = make_user(tenant_ids=["t-1"])
        db = MagicMock()
        
        # Mock DB lookup returns None (no UserTenant mapping)
        db.query.return_value.join.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            validate_tenant_access(limited_user, "t-unauthorized", db)
        
        assert exc_info.value.status_code == 403
        assert "Access denied" in exc_info.value.detail
        assert "t-unauthorized" in exc_info.value.detail


# =============================================================================
# Test 8-10: validate_tenants_access() - Empty, Admin, Missing Access
# =============================================================================

class TestValidateTenantsAccess:
    """Test validate_tenants_access() for bulk tenant validation."""

    def test_empty_list_returns_true(self):
        """Test that empty tenant list always returns True."""
        user = make_user()
        db = MagicMock()
        
        # Empty list should always pass
        assert validate_tenants_access(user, [], db) is True

    def test_admin_always_has_access_to_all(self):
        """Test that admin users have access to all requested tenants."""
        admin_user = make_user(roles=["admin"])
        db = MagicMock()
        
        # Admin should have access to any combination of tenants
        assert validate_tenants_access(admin_user, ["t-1", "t-2", "t-3"], db) is True
        assert validate_tenants_access(admin_user, ["t-999"], db) is True

    @patch("app.core.authorization.get_user_tenant_ids")
    def test_missing_access_raises_http_exception_403(self, mock_get_ids):
        """Test that requesting inaccessible tenant raises 403."""
        mock_get_ids.return_value = ["t-1", "t-2"]  # User has access to t-1, t-2
        
        user = make_user()
        db = MagicMock()
        
        # Requesting t-999 which user doesn't have access to
        with pytest.raises(HTTPException) as exc_info:
            validate_tenants_access(user, ["t-1", "t-999"], db)
        
        assert exc_info.value.status_code == 403
        assert "Access denied" in exc_info.value.detail
        assert "t-999" in exc_info.value.detail


# =============================================================================
# Test 11-14: TenantAuthorization Class Methods
# =============================================================================

class TestTenantAuthorization:
    """Test TenantAuthorization helper class methods."""

    @patch("app.core.authorization.get_user_tenant_ids")
    def test_can_access_returns_true_for_accessible_tenant(self, mock_get_ids):
        """Test can_access() returns True for accessible tenants."""
        mock_get_ids.return_value = ["t-1", "t-2", "t-3"]
        
        user = make_user()
        db = MagicMock()
        authz = TenantAuthorization(user, db)
        
        # Should return True for accessible tenants
        assert authz.can_access("t-1") is True
        assert authz.can_access("t-2") is True
        # Should return False for inaccessible tenant
        assert authz.can_access("t-999") is False

    @patch("app.core.authorization.get_user_tenant_ids")
    def test_filter_tenant_ids_filters_to_accessible_only(self, mock_get_ids):
        """Test filter_tenant_ids() returns only accessible tenant IDs."""
        mock_get_ids.return_value = ["t-1", "t-2", "t-3"]
        
        user = make_user()
        db = MagicMock()
        authz = TenantAuthorization(user, db)
        
        # Should filter requested tenants to only accessible ones
        requested = ["t-1", "t-999", "t-2", "t-888"]
        result = authz.filter_tenant_ids(requested)
        assert result == ["t-1", "t-2"]
        
        # None should return all accessible tenants
        result_all = authz.filter_tenant_ids(None)
        assert result_all == ["t-1", "t-2", "t-3"]

    @patch("app.core.authorization.get_user_tenant_ids")
    def test_ensure_at_least_one_tenant_raises_for_no_access(self, mock_get_ids):
        """Test ensure_at_least_one_tenant() raises 403 when user has no tenants."""
        mock_get_ids.return_value = []  # No tenant access
        
        user = make_user()
        db = MagicMock()
        authz = TenantAuthorization(user, db)
        
        # Should raise HTTPException with 403
        with pytest.raises(HTTPException) as exc_info:
            authz.ensure_at_least_one_tenant()
        
        assert exc_info.value.status_code == 403
        assert "no access to any tenants" in exc_info.value.detail.lower()

    def test_ensure_at_least_one_tenant_passes_for_admin(self):
        """Test ensure_at_least_one_tenant() passes for admin users."""
        admin_user = make_user(roles=["admin"])
        db = MagicMock()
        authz = TenantAuthorization(admin_user, db)
        
        # Admin should pass without exception
        authz.ensure_at_least_one_tenant()
        # If we get here without exception, test passes
        assert True
