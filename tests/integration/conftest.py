"""Shared fixtures for integration tests.

These fixtures provide authenticated test clients and seeded databases
for testing the complete request/response cycle of API endpoints.
"""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import User
from app.core.authorization import TenantAuthorization
from app.core.database import Base, get_db
from app.main import app
from app.models.compliance import ComplianceSnapshot, PolicyState
from app.models.cost import CostAnomaly, CostSnapshot
from app.models.identity import IdentitySnapshot, PrivilegedUser
from app.models.resource import Resource, ResourceTag
from app.models.tenant import Subscription, Tenant, UserTenant

@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset in-memory rate limiter state before each test.

    Prevents test ordering from causing 429 failures due to shared state.
    """
    from app.core.rate_limit import rate_limiter
    rate_limiter._memory_cache.clear()
    yield
    rate_limiter._memory_cache.clear()


# Test database setup
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


@pytest.fixture
def test_tenant_id() -> str:
    """Generate consistent tenant ID for tests."""
    return "test-tenant-123"


@pytest.fixture
def second_tenant_id() -> str:
    """Generate second tenant ID for multi-tenant tests."""
    return "test-tenant-456"


@pytest.fixture
def test_user(test_tenant_id: str) -> User:
    """Create a test user with tenant access."""
    return User(
        id="user-123",
        email="test@example.com",
        name="Test User",
        roles=["user"],
        tenant_ids=[test_tenant_id],
        is_active=True,
        auth_provider="internal",
    )


@pytest.fixture
def admin_user(test_tenant_id: str, second_tenant_id: str) -> User:
    """Create an admin user with access to all tenants."""
    return User(
        id="admin-123",
        email="admin@example.com",
        name="Admin User",
        roles=["admin"],
        tenant_ids=[test_tenant_id, second_tenant_id],
        is_active=True,
        auth_provider="internal",
    )


@pytest.fixture
def multi_tenant_user(test_tenant_id: str, second_tenant_id: str) -> User:
    """Create a user with access to multiple tenants."""
    return User(
        id="multi-tenant-user",
        email="multi@example.com",
        name="Multi Tenant User",
        roles=["user"],
        tenant_ids=[test_tenant_id, second_tenant_id],
        is_active=True,
        auth_provider="internal",
    )


@pytest.fixture
def mock_authz(test_tenant_id: str, second_tenant_id: str):
    """Mock TenantAuthorization with appropriate permissions."""
    authz = MagicMock(spec=TenantAuthorization)
    authz.accessible_tenant_ids = [test_tenant_id, second_tenant_id]
    authz.ensure_at_least_one_tenant = MagicMock()
    authz.filter_tenant_ids = MagicMock(return_value=[test_tenant_id])
    authz.validate_access = MagicMock()
    authz.validate_tenant_access = MagicMock(return_value=True)
    return authz


@pytest.fixture
def mock_authz_admin():
    """Mock TenantAuthorization for admin user (all tenants)."""
    authz = MagicMock(spec=TenantAuthorization)
    authz.accessible_tenant_ids = []  # Admin has empty list meaning all
    authz.ensure_at_least_one_tenant = MagicMock()
    authz.filter_tenant_ids = MagicMock(side_effect=lambda x: x)  # Return all
    authz.validate_access = MagicMock()
    authz.validate_tenant_access = MagicMock(return_value=True)
    return authz


@pytest.fixture
def seeded_db(db_session, test_tenant_id: str, second_tenant_id: str):
    """Database session with realistic test data.

    Creates:
    - 2 tenants
    - 2 subscriptions per tenant
    - 30 days of cost snapshots across multiple services
    - 5 cost anomalies (3 unacknowledged, 2 acknowledged)
    - Compliance snapshots and policy states
    - Resources with tags
    - Identity snapshots and privileged users
    """
    # Create tenants
    tenant1 = Tenant(
        id=test_tenant_id,
        tenant_id=test_tenant_id,
        name="Test Tenant 1",
        is_active=True,
    )
    tenant2 = Tenant(
        id=second_tenant_id,
        tenant_id=second_tenant_id,
        name="Test Tenant 2",
        is_active=True,
    )
    db_session.add_all([tenant1, tenant2])

    # Create subscriptions
    sub1 = Subscription(
        id="sub-123",
        tenant_ref="test-tenant-123",
        subscription_id="sub-123",
        display_name="Test Subscription 1",
        state="Enabled",
    )
    sub2 = Subscription(
        id="sub-456",
        tenant_ref="test-tenant-456",
        subscription_id="sub-456",
        display_name="Test Subscription 2",
        state="Enabled",
    )
    db_session.add_all([sub1, sub2])

    # Create 30 days of cost snapshots with realistic patterns
    today = date.today()
    services = ["Compute", "Storage", "Networking", "Database", "AI"]

    for days_ago in range(30):
        snapshot_date = today - timedelta(days=days_ago)

        for service in services:
            # Generate realistic cost patterns
            base_cost = 100.0 if service == "Compute" else 50.0
            trend_factor = 1 + (30 - days_ago) * 0.01
            variation = (days_ago % 7) * 5

            cost = base_cost * trend_factor + variation

            snapshot = CostSnapshot(
                tenant_id=test_tenant_id,
                subscription_id="sub-123",
                date=snapshot_date,
                total_cost=round(cost, 2),
                currency="USD",
                service_name=service,
                meter_category=f"{service} Category",
                synced_at=datetime.utcnow(),
            )
            db_session.add(snapshot)

            # Add some data for second tenant
            if days_ago % 3 == 0:
                snapshot2 = CostSnapshot(
                    tenant_id=second_tenant_id,
                    subscription_id="sub-456",
                    date=snapshot_date,
                    total_cost=round(cost * 0.8, 2),
                    currency="USD",
                    service_name=service,
                    meter_category=f"{service} Category",
                    synced_at=datetime.utcnow(),
                )
                db_session.add(snapshot2)

    # Create cost anomalies
    anomalies_data = [
        {
            "tenant_id": test_tenant_id,
            "subscription_id": "sub-123",
            "anomaly_type": "spike",
            "description": "Unusual compute cost spike detected",
            "expected_cost": 100.0,
            "actual_cost": 250.0,
            "percentage_change": 150.0,
            "service_name": "Compute",
            "is_acknowledged": False,
            "detected_at": datetime.utcnow() - timedelta(days=2),
        },
        {
            "tenant_id": test_tenant_id,
            "subscription_id": "sub-123",
            "anomaly_type": "spike",
            "description": "Storage cost anomaly",
            "expected_cost": 50.0,
            "actual_cost": 120.0,
            "percentage_change": 140.0,
            "service_name": "Storage",
            "is_acknowledged": False,
            "detected_at": datetime.utcnow() - timedelta(days=1),
        },
        {
            "tenant_id": test_tenant_id,
            "subscription_id": "sub-123",
            "anomaly_type": "unusual_service",
            "description": "New AI service usage detected",
            "expected_cost": 0.0,
            "actual_cost": 75.0,
            "percentage_change": 100.0,
            "service_name": "AI",
            "is_acknowledged": False,
            "detected_at": datetime.utcnow() - timedelta(hours=12),
        },
        {
            "tenant_id": test_tenant_id,
            "subscription_id": "sub-123",
            "anomaly_type": "spike",
            "description": "Previous database spike (acknowledged)",
            "expected_cost": 50.0,
            "actual_cost": 150.0,
            "percentage_change": 200.0,
            "service_name": "Database",
            "is_acknowledged": True,
            "acknowledged_by": "user-123",
            "acknowledged_at": datetime.utcnow() - timedelta(days=5),
            "detected_at": datetime.utcnow() - timedelta(days=7),
        },
        {
            "tenant_id": test_tenant_id,
            "subscription_id": "sub-123",
            "anomaly_type": "spike",
            "description": "Old networking spike (acknowledged)",
            "expected_cost": 30.0,
            "actual_cost": 90.0,
            "percentage_change": 200.0,
            "service_name": "Networking",
            "is_acknowledged": True,
            "acknowledged_by": "user-456",
            "acknowledged_at": datetime.utcnow() - timedelta(days=10),
            "detected_at": datetime.utcnow() - timedelta(days=14),
        },
    ]

    for anomaly_data in anomalies_data:
        anomaly = CostAnomaly(**anomaly_data)
        db_session.add(anomaly)

    # Create compliance snapshots
    for days_ago in range(7):
        snapshot_date = datetime.utcnow() - timedelta(days=days_ago)
        comp_snapshot = ComplianceSnapshot(
            tenant_id=test_tenant_id,
            subscription_id="sub-123",
            snapshot_date=snapshot_date,
            overall_compliance_percent=85.0 + (days_ago % 10),
            secure_score=75.0,
            compliant_resources=85,
            non_compliant_resources=15,
            exempt_resources=5,
            synced_at=datetime.utcnow(),
        )
        db_session.add(comp_snapshot)

    # Create policy states
    policies = [
        {
            "policy_definition_id": "/providers/Microsoft.Authorization/policyDefinitions/audit-sql-tde",
            "policy_name": "Audit SQL TDE",
            "policy_category": "SQL",
            "compliance_state": "Compliant",
            "non_compliant_count": 0,
        },
        {
            "policy_definition_id": "/providers/Microsoft.Authorization/policyDefinitions/audit-vm-monitoring",
            "policy_name": "Audit VM Monitoring",
            "policy_category": "Monitoring",
            "compliance_state": "NonCompliant",
            "non_compliant_count": 3,
        },
        {
            "policy_definition_id": "/providers/Microsoft.Authorization/policyDefinitions/audit-storage-encryption",
            "policy_name": "Audit Storage Encryption",
            "policy_category": "Storage",
            "compliance_state": "Compliant",
            "non_compliant_count": 0,
        },
    ]

    for policy in policies:
        policy_state = PolicyState(
            tenant_id=test_tenant_id,
            subscription_id="sub-123",
            **policy,
            synced_at=datetime.utcnow(),
        )
        db_session.add(policy_state)

    # Create resources
    resources = [
        {
            "id": f"/subscriptions/sub-123/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-{i}",
            "tenant_id": test_tenant_id,
            "subscription_id": "sub-123",
            "resource_group": "rg-1",
            "resource_type": "Microsoft.Compute/virtualMachines",
            "name": f"vm-{i}",
            "location": "eastus",
            "provisioning_state": "Succeeded",
            "is_orphaned": 0,
            "estimated_monthly_cost": 100.0,
        }
        for i in range(5)
    ]

    for res_data in resources:
        resource = Resource(**res_data, synced_at=datetime.utcnow())
        db_session.add(resource)

        # Add tags
        for tag_name, tag_value in [("Environment", "Test"), ("Owner", "test@example.com")]:
            tag = ResourceTag(
                resource_id=res_data["id"],
                tag_name=tag_name,
                tag_value=tag_value,
                is_required=1 if tag_name == "Environment" else 0,
            )
            db_session.add(tag)

    # Create identity snapshots
    for days_ago in range(7):
        snapshot_date = date.today() - timedelta(days=days_ago)
        identity_snapshot = IdentitySnapshot(
            tenant_id=test_tenant_id,
            snapshot_date=snapshot_date,
            total_users=100 + days_ago,
            active_users=90,
            guest_users=10,
            mfa_enabled_users=80,
            mfa_disabled_users=20,
            privileged_users=5,
            stale_accounts_30d=2,
            stale_accounts_90d=1,
            service_principals=15,
            synced_at=datetime.utcnow(),
        )
        db_session.add(identity_snapshot)

    # Create privileged users
    privileged_users = [
        {
            "user_principal_name": "admin1@example.com",
            "display_name": "Admin One",
            "user_type": "Member",
            "role_name": "Global Administrator",
            "role_scope": "/",
            "is_permanent": 1,
            "mfa_enabled": 1,
            "last_sign_in": datetime.utcnow() - timedelta(days=1),
        },
        {
            "user_principal_name": "admin2@example.com",
            "display_name": "Admin Two",
            "user_type": "Member",
            "role_name": "User Administrator",
            "role_scope": "/",
            "is_permanent": 0,
            "mfa_enabled": 1,
            "last_sign_in": datetime.utcnow() - timedelta(hours=12),
        },
    ]

    for pu_data in privileged_users:
        pu = PrivilegedUser(
            tenant_id=test_tenant_id,
            **pu_data,
            synced_at=datetime.utcnow(),
        )
        db_session.add(pu)

    # Create user-tenant mappings
    user_tenant = UserTenant(
        id="mapping-1",
        user_id="user-123",
        tenant_id=test_tenant_id,
        role="admin",
        is_active=True,
        can_manage_resources=True,
        can_view_costs=True,
        can_manage_compliance=True,
    )
    db_session.add(user_tenant)

    db_session.commit()
    return db_session


@pytest.fixture
def authenticated_client(seeded_db, test_user, mock_authz):
    """Test client with authentication and database mocked.

    Uses FastAPI's dependency_overrides system to globally mock authentication.
    This is more reliable than patching individual route modules.
    """
    from app.core.auth import get_current_user
    from app.core.authorization import get_tenant_authorization

    def override_get_db():
        try:
            yield seeded_db
        finally:
            pass

    async def override_get_current_user():
        return test_user

    async def override_get_tenant_authorization():
        return mock_authz

    # Override dependencies globally for all routes
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_tenant_authorization] = override_get_tenant_authorization

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def admin_client(seeded_db, admin_user, mock_authz_admin):
    """Test client with admin authentication.

    Uses FastAPI's dependency_overrides system to globally mock authentication.
    """
    from app.core.auth import get_current_user
    from app.core.authorization import get_tenant_authorization

    def override_get_db():
        try:
            yield seeded_db
        finally:
            pass

    async def override_get_current_user():
        return admin_user

    async def override_get_tenant_authorization():
        return mock_authz_admin

    # Override dependencies globally for all routes
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_tenant_authorization] = override_get_tenant_authorization

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def unauthenticated_client(seeded_db):
    """Test client without authentication (for testing 401s)."""

    def override_get_db():
        try:
            yield seeded_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def multi_tenant_users(test_tenant_id: str, second_tenant_id: str) -> dict:
    """Dictionary of users with different tenant access levels."""
    return {
        "tenant1_only": User(
            id="user-tenant1",
            email="tenant1@example.com",
            name="Tenant 1 User",
            roles=["user"],
            tenant_ids=[test_tenant_id],
            is_active=True,
            auth_provider="internal",
        ),
        "tenant2_only": User(
            id="user-tenant2",
            email="tenant2@example.com",
            name="Tenant 2 User",
            roles=["user"],
            tenant_ids=[second_tenant_id],
            is_active=True,
            auth_provider="internal",
        ),
        "both_tenants": User(
            id="user-both",
            email="both@example.com",
            name="Both Tenants User",
            roles=["user"],
            tenant_ids=[test_tenant_id, second_tenant_id],
            is_active=True,
            auth_provider="internal",
        ),
        "admin": User(
            id="user-admin",
            email="admin@example.com",
            name="Admin User",
            roles=["admin"],
            tenant_ids=[],
            is_active=True,
            auth_provider="internal",
        ),
    }
