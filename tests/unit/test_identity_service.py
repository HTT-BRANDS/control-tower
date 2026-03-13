"""Unit tests for IdentityService.

Tests for identity governance operations including:
- get_identity_summary (aggregated identity metrics)
- get_privileged_accounts (privileged user listing and filtering)
- get_identity_trends (historical trend analysis)
- _calculate_risk_level (risk scoring logic)
- get_guest_accounts and get_stale_accounts (placeholder methods)

Minimum 11 tests covering all public methods and edge cases.
"""

import sys
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


# Mock the cache decorator BEFORE importing the service
def no_op_cache(cache_key):
    """Decorator that does nothing - bypasses caching."""

    def decorator(func):
        return func

    return decorator


# Patch the cache module before importing identity_service
with patch("app.core.cache.cached", no_op_cache):
    # Remove from cache if already imported
    if "app.api.services.identity_service" in sys.modules:
        del sys.modules["app.api.services.identity_service"]
    from app.api.services.identity_service import IdentityService

from app.models.identity import IdentitySnapshot, PrivilegedUser  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402


class TestIdentityServiceSummary:
    """Test suite for get_identity_summary method."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def identity_service(self, mock_db):
        """Create IdentityService instance."""
        return IdentityService(db=mock_db)

    @pytest.fixture
    def sample_tenants(self):
        """Create sample active tenants."""
        tenants = []
        for i in range(3):
            tenant = MagicMock(spec=Tenant)
            tenant.id = f"tenant-{i + 1}"
            tenant.name = f"Tenant {i + 1}"
            tenant.is_active = True
            tenants.append(tenant)
        return tenants

    @pytest.fixture
    def sample_snapshots(self):
        """Create sample identity snapshots for each tenant."""
        snapshots = []
        for i in range(3):
            snapshot = MagicMock(spec=IdentitySnapshot)
            snapshot.tenant_id = f"tenant-{i + 1}"
            snapshot.snapshot_date = date.today()
            snapshot.total_users = 100 + (i * 10)
            snapshot.active_users = 90 + (i * 10)
            snapshot.guest_users = 10 + i
            snapshot.mfa_enabled_users = 80 + (i * 8)
            snapshot.mfa_disabled_users = 20 + (i * 2)
            snapshot.privileged_users = 5 + i
            snapshot.stale_accounts_30d = 3 + i
            snapshot.stale_accounts_90d = 8 + i
            snapshot.service_principals = 15 + (i * 2)
            snapshots.append(snapshot)
        return snapshots

    @pytest.mark.asyncio
    async def test_get_identity_summary_with_multiple_tenants(
        self, identity_service, mock_db, sample_tenants, sample_snapshots
    ):
        """Test get_identity_summary aggregates data across multiple tenants correctly."""
        # Setup mock queries
        tenant_query_mock = MagicMock()
        tenant_query_mock.filter.return_value.all.return_value = sample_tenants

        snapshot_query_mock = MagicMock()
        # Return the correct snapshot for each tenant query
        snapshot_query_mock.filter.return_value.order_by.return_value.first.side_effect = (
            sample_snapshots
        )

        mock_db.query.side_effect = [
            tenant_query_mock,
            snapshot_query_mock,
            snapshot_query_mock,
            snapshot_query_mock,
        ]

        # Execute
        result = await identity_service.get_identity_summary()

        # Verify aggregations
        assert result.total_users == 330  # 100 + 110 + 120
        assert result.active_users == 300  # 90 + 100 + 110
        assert result.guest_users == 33  # 10 + 11 + 12
        assert result.privileged_users == 18  # 5 + 6 + 7
        assert result.stale_accounts == 12  # 3 + 4 + 5
        assert result.service_principals == 51  # 15 + 17 + 19

        # Verify MFA percentage calculation
        # Total MFA enabled: 80 + 88 + 96 = 264
        # Total users: 330
        # Expected: 264/330 * 100 = 80.0
        assert result.mfa_enabled_percent == pytest.approx(80.0, rel=0.01)

        # Verify tenant summaries
        assert len(result.by_tenant) == 3
        assert result.by_tenant[0].tenant_id == "tenant-1"
        assert result.by_tenant[0].tenant_name == "Tenant 1"
        assert result.by_tenant[0].total_users == 100

    @pytest.mark.asyncio
    async def test_get_identity_summary_with_no_tenants(self, identity_service, mock_db):
        """Test get_identity_summary returns zeros when no active tenants exist."""
        # Setup mock to return no tenants
        tenant_query_mock = MagicMock()
        tenant_query_mock.filter.return_value.all.return_value = []
        mock_db.query.return_value = tenant_query_mock

        # Execute
        result = await identity_service.get_identity_summary()

        # Verify all zeros
        assert result.total_users == 0
        assert result.active_users == 0
        assert result.guest_users == 0
        assert result.mfa_enabled_percent == 0.0
        assert result.privileged_users == 0
        assert result.stale_accounts == 0
        assert result.service_principals == 0
        assert len(result.by_tenant) == 0

    @pytest.mark.asyncio
    async def test_get_identity_summary_with_no_snapshots(
        self, identity_service, mock_db, sample_tenants
    ):
        """Test get_identity_summary handles tenants with no snapshot data."""
        # Setup mocks - tenants exist but no snapshots
        tenant_query_mock = MagicMock()
        tenant_query_mock.filter.return_value.all.return_value = sample_tenants

        snapshot_query_mock = MagicMock()
        snapshot_query_mock.filter.return_value.order_by.return_value.first.return_value = None

        mock_db.query.side_effect = [
            tenant_query_mock,
            snapshot_query_mock,
            snapshot_query_mock,
            snapshot_query_mock,
        ]

        # Execute
        result = await identity_service.get_identity_summary()

        # Verify zeros but tenant count is correct
        assert result.total_users == 0
        assert len(result.by_tenant) == 0  # No summaries added if no snapshots


class TestIdentityServicePrivilegedAccounts:
    """Test suite for get_privileged_accounts method."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def identity_service(self, mock_db):
        """Create IdentityService instance."""
        return IdentityService(db=mock_db)

    @pytest.fixture
    def sample_privileged_users(self):
        """Create sample privileged users with varying attributes."""
        users = []

        # High risk: Guest, no MFA, permanent, no recent sign-in
        user1 = MagicMock(spec=PrivilegedUser)
        user1.tenant_id = "tenant-1"
        user1.user_principal_name = "guest@external.com"
        user1.display_name = "Guest Admin"
        user1.user_type = "Guest"
        user1.role_name = "Global Administrator"
        user1.role_scope = "/"
        user1.is_permanent = True
        user1.mfa_enabled = False
        user1.last_sign_in = datetime.utcnow() - timedelta(days=100)
        users.append(user1)

        # Low risk: Member, MFA enabled, not permanent, recent sign-in
        user2 = MagicMock(spec=PrivilegedUser)
        user2.tenant_id = "tenant-1"
        user2.user_principal_name = "admin@company.com"
        user2.display_name = "Admin User"
        user2.user_type = "Member"
        user2.role_name = "User Administrator"
        user2.role_scope = "/"
        user2.is_permanent = False
        user2.mfa_enabled = True
        user2.last_sign_in = datetime.utcnow() - timedelta(days=1)
        users.append(user2)

        # Medium risk: Member, no MFA, permanent
        user3 = MagicMock(spec=PrivilegedUser)
        user3.tenant_id = "tenant-2"
        user3.user_principal_name = "security@company.com"
        user3.display_name = "Security Admin"
        user3.user_type = "Member"
        user3.role_name = "Security Administrator"
        user3.role_scope = "/subscriptions/sub-1"
        user3.is_permanent = True
        user3.mfa_enabled = False
        user3.last_sign_in = datetime.utcnow() - timedelta(days=15)
        users.append(user3)

        return users

    @pytest.fixture
    def sample_tenants(self):
        """Create sample tenants."""
        tenant1 = MagicMock(spec=Tenant)
        tenant1.id = "tenant-1"
        tenant1.name = "Tenant 1"

        tenant2 = MagicMock(spec=Tenant)
        tenant2.id = "tenant-2"
        tenant2.name = "Tenant 2"

        return [tenant1, tenant2]

    @pytest.mark.asyncio
    async def test_get_privileged_accounts_all(
        self, identity_service, mock_db, sample_privileged_users, sample_tenants
    ):
        """Test get_privileged_accounts returns all privileged users when no filter applied."""
        # Setup mocks
        user_query_mock = MagicMock()
        user_query_mock.order_by.return_value.all.return_value = sample_privileged_users

        tenant_query_mock = MagicMock()
        tenant_query_mock.all.return_value = sample_tenants

        mock_db.query.side_effect = [user_query_mock, tenant_query_mock]

        # Execute
        result = await identity_service.get_privileged_accounts()

        # Verify
        assert len(result) == 3
        assert result[0].user_principal_name == "guest@external.com"
        assert result[0].risk_level == "High"
        assert result[1].user_principal_name == "admin@company.com"
        assert result[1].risk_level == "Low"
        assert result[2].user_principal_name == "security@company.com"
        assert result[2].risk_level == "Medium"

    @pytest.mark.asyncio
    async def test_get_privileged_accounts_filtered_by_tenant(
        self, identity_service, mock_db, sample_privileged_users, sample_tenants
    ):
        """Test get_privileged_accounts filters by tenant_id correctly."""
        # Setup mocks - only return tenant-1 users
        filtered_users = [u for u in sample_privileged_users if u.tenant_id == "tenant-1"]

        user_query_mock = MagicMock()
        filter_mock = MagicMock()
        filter_mock.order_by.return_value.all.return_value = filtered_users
        user_query_mock.filter.return_value = filter_mock

        tenant_query_mock = MagicMock()
        tenant_query_mock.all.return_value = sample_tenants

        mock_db.query.side_effect = [user_query_mock, tenant_query_mock]

        # Execute
        result = await identity_service.get_privileged_accounts(tenant_id="tenant-1")

        # Verify only tenant-1 users returned
        assert len(result) == 2
        assert all(u.tenant_id == "tenant-1" for u in result)


class TestIdentityServiceRiskCalculation:
    """Test suite for _calculate_risk_level method."""

    @pytest.fixture
    def identity_service(self):
        """Create IdentityService instance with mock db."""
        return IdentityService(db=MagicMock())

    def test_calculate_risk_level_high_guest_no_mfa_old_signin(self, identity_service):
        """Test high risk: guest user, no MFA, permanent, stale sign-in."""
        user = MagicMock(spec=PrivilegedUser)
        user.user_type = "Guest"
        user.mfa_enabled = False
        user.is_permanent = True
        user.last_sign_in = datetime.utcnow() - timedelta(days=100)

        result = identity_service._calculate_risk_level(user)

        # Risk score: Guest(3) + No MFA(2) + Permanent(1) + 90d+ signin(2) = 8
        assert result == "High"

    def test_calculate_risk_level_medium_member_no_mfa_permanent(self, identity_service):
        """Test medium risk: member, no MFA, permanent assignment."""
        user = MagicMock(spec=PrivilegedUser)
        user.user_type = "Member"
        user.mfa_enabled = False
        user.is_permanent = True
        user.last_sign_in = datetime.utcnow() - timedelta(days=10)

        result = identity_service._calculate_risk_level(user)

        # Risk score: No MFA(2) + Permanent(1) = 3
        assert result == "Medium"

    def test_calculate_risk_level_low_member_mfa_recent_signin(self, identity_service):
        """Test low risk: member with MFA, not permanent, recent activity."""
        user = MagicMock(spec=PrivilegedUser)
        user.user_type = "Member"
        user.mfa_enabled = True
        user.is_permanent = False
        user.last_sign_in = datetime.utcnow() - timedelta(days=1)

        result = identity_service._calculate_risk_level(user)

        # Risk score: 0
        assert result == "Low"

    def test_calculate_risk_level_no_last_signin(self, identity_service):
        """Test risk calculation when last_sign_in is None."""
        user = MagicMock(spec=PrivilegedUser)
        user.user_type = "Member"
        user.mfa_enabled = True
        user.is_permanent = False
        user.last_sign_in = None

        result = identity_service._calculate_risk_level(user)

        # Should not crash, just skip the sign-in checks
        assert result == "Low"


class TestIdentityServiceTrends:
    """Test suite for get_identity_trends method."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def identity_service(self, mock_db):
        """Create IdentityService instance."""
        return IdentityService(db=mock_db)

    @pytest.fixture
    def sample_trend_snapshots(self):
        """Create sample snapshots over 7 days for trends."""
        snapshots = []
        base_date = date.today()

        for i in range(7):
            snapshot = MagicMock(spec=IdentitySnapshot)
            snapshot.snapshot_date = base_date - timedelta(days=i)
            snapshot.tenant_id = "tenant-1"
            snapshot.total_users = 100 + i
            snapshot.mfa_enabled_users = 80 + i
            snapshot.mfa_disabled_users = 20
            snapshot.guest_users = 10 + i
            snapshot.privileged_users = 5
            snapshot.stale_accounts_30d = 3
            snapshot.stale_accounts_90d = 8
            snapshot.service_principals = 15
            snapshots.append(snapshot)

        return snapshots

    @pytest.mark.asyncio
    async def test_get_identity_trends_basic(
        self, identity_service, mock_db, sample_trend_snapshots
    ):
        """Test get_identity_trends returns trend data correctly."""
        # Setup mock query chain
        query_mock = MagicMock()
        filter_mock = MagicMock()
        order_mock = MagicMock()

        order_mock.all.return_value = sample_trend_snapshots
        filter_mock.order_by.return_value = order_mock
        query_mock.filter.return_value = filter_mock
        mock_db.query.return_value = query_mock

        # Execute
        result = await identity_service.get_identity_trends(days=7)

        # Verify
        assert len(result) == 7

        # Check first trend point
        first_trend = result[0]
        assert "date" in first_trend
        assert "total_users" in first_trend
        assert "mfa_adoption_rate" in first_trend
        assert "guest_users" in first_trend
        assert "privileged_users" in first_trend
        assert "stale_accounts_30d" in first_trend

        # Verify MFA adoption calculation for at least one point
        # Should be (mfa_enabled / total_users * 100)
        assert first_trend["mfa_adoption_rate"] > 70.0  # Roughly 80+/100+

    @pytest.mark.asyncio
    async def test_get_identity_trends_filtered_by_tenants(
        self, identity_service, mock_db, sample_trend_snapshots
    ):
        """Test get_identity_trends filters by tenant_ids list."""
        # Setup mock query chain with in_ filter
        query_mock = MagicMock()
        filter_mock = MagicMock()
        order_mock = MagicMock()

        # Mock the filter calls (date range + tenant filter)
        order_mock.all.return_value = sample_trend_snapshots
        filter_mock.order_by.return_value = order_mock

        # Create a chain that handles both filter calls
        filter_chain = MagicMock()
        filter_chain.filter.return_value = filter_mock
        query_mock.filter.return_value = filter_chain

        mock_db.query.return_value = query_mock

        # Execute with tenant filter
        result = await identity_service.get_identity_trends(
            tenant_ids=["tenant-1", "tenant-2"], days=7
        )

        # Verify filter was called (checking call count)
        assert filter_chain.filter.called
        assert len(result) == 7

    @pytest.mark.asyncio
    async def test_get_identity_trends_no_data(self, identity_service, mock_db):
        """Test get_identity_trends returns empty list when no snapshots exist."""
        # Setup mock to return no snapshots
        query_mock = MagicMock()
        filter_mock = MagicMock()
        order_mock = MagicMock()

        order_mock.all.return_value = []
        filter_mock.order_by.return_value = order_mock
        query_mock.filter.return_value = filter_mock
        mock_db.query.return_value = query_mock

        # Execute
        result = await identity_service.get_identity_trends(days=30)

        # Verify empty result
        assert len(result) == 0


class TestIdentityServicePlaceholders:
    """Test suite for placeholder methods (guest and stale accounts)."""

    @pytest.fixture
    def identity_service(self):
        """Create IdentityService instance with mock db."""
        return IdentityService(db=MagicMock())

    def test_get_guest_accounts_returns_empty(self, identity_service):
        """Test get_guest_accounts returns empty list (placeholder implementation)."""
        result = identity_service.get_guest_accounts()
        assert result == []

        result_with_params = identity_service.get_guest_accounts(
            tenant_id="tenant-1", stale_only=True
        )
        assert result_with_params == []

    def test_get_stale_accounts_returns_empty(self, identity_service):
        """Test get_stale_accounts returns empty list (placeholder implementation)."""
        result = identity_service.get_stale_accounts()
        assert result == []

        result_with_params = identity_service.get_stale_accounts(
            days_inactive=60, tenant_id="tenant-2"
        )
        assert result_with_params == []
