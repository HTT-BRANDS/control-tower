"""Test configuration and fixtures."""

# Pre-import Azure modules to fix namespace package issues during test collection
# This must happen before any other imports

# Ensure azure namespace packages are properly loaded
try:
    # Core Azure modules
    import azure.core.credentials  # noqa: F401
    import azure.identity  # noqa: F401

    # Key Vault
    import azure.keyvault.secrets  # noqa: F401
    import azure.mgmt.authorization  # noqa: F401
    import azure.mgmt.costmanagement  # noqa: F401
    import azure.mgmt.policyinsights  # noqa: F401
    import azure.mgmt.resource  # noqa: F401
    import azure.mgmt.security  # noqa: F401

    # Management modules
    import azure.mgmt.subscription  # noqa: F401
except ImportError:
    pass  # Will be mocked in tests anyway

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import User, get_current_user
from app.core.authorization import TenantAuthorization, get_tenant_authorization
from app.core.database import Base, get_db
from app.models.tenant import Tenant

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create test client with overridden database."""
    from fastapi.testclient import TestClient

    from app.main import app

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ============================================================================
# Authenticated client fixtures
# ============================================================================

_TEST_TENANT_ID = "test-tenant-123"


@pytest.fixture(scope="function")
def mock_user():
    """Mock authenticated user with admin access."""
    return User(
        id="user-123",
        email="test@example.com",
        name="Test User",
        roles=["admin"],
        tenant_ids=[_TEST_TENANT_ID],
        is_active=True,
        auth_provider="internal",
    )


@pytest.fixture(scope="function")
def mock_authz(mock_user):
    """Mock TenantAuthorization that grants access to the test tenant."""
    authz = MagicMock(spec=TenantAuthorization)
    authz.user = mock_user
    authz.accessible_tenant_ids = [_TEST_TENANT_ID]
    authz.ensure_at_least_one_tenant = MagicMock()
    authz.filter_tenant_ids = MagicMock(return_value=[_TEST_TENANT_ID])
    authz.validate_access = MagicMock()
    authz.validate_tenants_access = MagicMock()
    return authz


@pytest.fixture(scope="function")
def authed_client(db_session, mock_user, mock_authz):
    """Test client with database AND auth overrides.

    Use this for testing authenticated endpoints — bypasses JWT validation
    and tenant authorization so you can focus on business logic.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    # Seed a tenant — use same string for id and tenant_id so FK refs
    # and authz checks (which compare against tenant_id) both work.
    tenant = Tenant(
        id=_TEST_TENANT_ID,
        tenant_id=_TEST_TENANT_ID,
        name="Test Tenant",
        is_active=True,
    )
    db_session.add(tenant)
    db_session.commit()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_tenant_authorization] = lambda: mock_authz

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
