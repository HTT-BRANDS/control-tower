"""Tests for tenant API endpoints."""

import uuid

import pytest

from app.core.auth import User, get_current_user


@pytest.fixture
def mock_current_user():
    """Return a test user with admin role for authentication."""
    return User(
        id="test-user-123",
        email="test@example.com",
        name="Test User",
        roles=["admin"],
        tenant_ids=[],
        is_active=True,
    )


@pytest.fixture
def mock_tenant_auth(monkeypatch):
    """Mock tenant authorization and rate limiting to allow all access."""
    from app.core import authorization
    from app.core.rate_limit import RateLimiter

    def mock_get_user_tenants(*args, **kwargs):
        """Return empty list - admin has access to all."""
        return []

    def mock_validate_tenant_access(*args, **kwargs):
        """Always return True for access validation."""
        return True

    async def mock_check_rate_limit(*args, **kwargs):
        """Bypass rate limiting for tests."""
        pass

    # Mock authorization functions
    monkeypatch.setattr(authorization, "get_user_tenants", mock_get_user_tenants)
    monkeypatch.setattr(authorization, "validate_tenant_access", mock_validate_tenant_access)

    # Also mock the app.api.routes.tenants imports
    import app.api.routes.tenants as tenants_module

    monkeypatch.setattr(tenants_module, "get_user_tenants", mock_get_user_tenants)
    monkeypatch.setattr(tenants_module, "validate_tenant_access", mock_validate_tenant_access)

    # Mock rate limiting to prevent 429 errors
    monkeypatch.setattr(RateLimiter, "check_rate_limit", mock_check_rate_limit)


@pytest.fixture
def auth_client(db_session, mock_current_user, mock_tenant_auth):
    """Create a test client with authentication mocked."""
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.main import app

    # Override the database dependency
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    # Override the get_current_user dependency
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: mock_current_user

    with TestClient(app) as test_client:
        yield test_client

    # Clean up overrides
    app.dependency_overrides.clear()


def test_list_tenants_empty(auth_client):
    """Test listing tenants when none exist."""
    response = auth_client.get("/api/v1/tenants")
    assert response.status_code == 200
    assert response.json() == []


def test_create_tenant(auth_client):
    """Test creating a new tenant."""
    tenant_data = {
        "name": "Test Tenant",
        "tenant_id": "12345678-1234-1234-1234-123456789012",
        "description": "A test tenant",
    }
    response = auth_client.post("/api/v1/tenants", json=tenant_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == tenant_data["name"]
    assert data["tenant_id"] == tenant_data["tenant_id"]
    assert data["is_active"] is True


def test_create_duplicate_tenant(auth_client):
    """Test that duplicate tenant IDs are rejected."""
    tenant_data = {
        "name": "Test Tenant",
        "tenant_id": "77777777-7777-7777-7777-777777777777",
    }
    # Create first tenant
    response = auth_client.post("/api/v1/tenants", json=tenant_data)
    assert response.status_code == 201

    # Try to create duplicate
    response = auth_client.post("/api/v1/tenants", json=tenant_data)
    assert response.status_code == 409


def test_get_tenant_not_found(auth_client):
    """Test getting a non-existent tenant."""
    response = auth_client.get(f"/api/v1/tenants/{uuid.uuid4()}")
    assert response.status_code == 404


def test_update_tenant(auth_client):
    """Test updating a tenant."""
    # Create tenant (use unique tenant_id to avoid conflicts)
    tenant_data = {
        "name": "Original Name",
        "tenant_id": "55555555-5555-5555-5555-555555555555",
    }
    response = auth_client.post("/api/v1/tenants", json=tenant_data)
    tenant_id = response.json()["id"]

    # Update tenant
    update_data = {"name": "Updated Name", "is_active": False}
    response = auth_client.patch(f"/api/v1/tenants/{tenant_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["is_active"] is False


def test_delete_tenant(auth_client):
    """Test deleting a tenant."""
    # First list tenants to get the current state
    response = auth_client.get("/api/v1/tenants")
    assert response.status_code == 200

    # Create tenant (use unique tenant_id to avoid conflicts with other tests)
    tenant_data = {
        "name": "To Delete",
        "tenant_id": "99999999-9999-9999-9999-999999999999",
    }
    response = auth_client.post("/api/v1/tenants", json=tenant_data)
    assert response.status_code == 201, f"Failed to create tenant: {response.text}"
    data = response.json()
    assert "id" in data, f"Response missing 'id': {data}"
    tenant_id = data["id"]

    # Delete tenant
    response = auth_client.delete(f"/api/v1/tenants/{tenant_id}")
    assert response.status_code == 204

    # Verify deleted
    response = auth_client.get(f"/api/v1/tenants/{tenant_id}")
    assert response.status_code == 404
