"""Shared fixtures for sync tests."""

from unittest.mock import AsyncMock, MagicMock

# Import Azure modules BEFORE mocking to ensure namespace packages work properly
try:
    import azure.core.exceptions
    import azure.identity
    import azure.mgmt.compute
    import azure.mgmt.costmanagement
    import azure.mgmt.policyinsights
    import azure.mgmt.resource
    import azure.mgmt.security  # noqa: F401 — imported for availability check

    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    raise  # Re-raise the error since Azure SDK should be installed

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest


@pytest.fixture
def mock_tenant():
    """Create a mock tenant for testing."""
    tenant = MagicMock()
    tenant.id = str(uuid.uuid4())
    tenant.tenant_id = "test-tenant-id-123"
    tenant.name = "Test Tenant"
    tenant.is_active = True
    return tenant


@pytest.fixture
def mock_subscription():
    """Create a mock subscription for testing."""
    return {
        "subscription_id": "sub-12345",
        "display_name": "Test Subscription",
        "state": "Enabled",
    }


@pytest.fixture
def mock_disabled_subscription():
    """Create a mock disabled subscription for testing."""
    return {
        "subscription_id": "sub-67890",
        "display_name": "Disabled Subscription",
        "state": "Disabled",
    }


@pytest.fixture
def mock_cost_client():
    """Create a mock CostManagementClient."""
    client = MagicMock()
    client.query = MagicMock()
    client.query.usage = MagicMock()
    return client


@pytest.fixture
def mock_policy_client():
    """Create a mock PolicyInsightsClient."""
    client = MagicMock()
    client.policy_states = MagicMock()
    return client


@pytest.fixture
def mock_security_client():
    """Create a mock SecurityCenter client."""
    client = MagicMock()
    client.secure_scores = MagicMock()
    return client


@pytest.fixture
def mock_resource_client():
    """Create a mock ResourceManagementClient."""
    client = MagicMock()
    client.resources = MagicMock()
    return client


@pytest.fixture
def mock_graph_client():
    """Create a mock GraphClient."""
    with patch("app.core.sync.identity.GraphClient") as mock:
        client = AsyncMock()
        mock.return_value = client
        yield client


@pytest.fixture
def mock_azure_client_manager(
    mock_cost_client,
    mock_policy_client,
    mock_security_client,
    mock_resource_client,
):
    """Create a mock AzureClientManager with all client types."""
    with (
        patch("app.core.sync.costs.azure_client_manager") as mock_costs,
        patch("app.core.sync.compliance.azure_client_manager") as mock_compliance,
        patch("app.core.sync.resources.azure_client_manager") as mock_resources,
    ):
        # Configure mock_costs
        mock_costs.list_subscriptions = AsyncMock()
        mock_costs.get_cost_client.return_value = mock_cost_client

        # Configure mock_compliance
        mock_compliance.list_subscriptions = AsyncMock()
        mock_compliance.get_policy_client.return_value = mock_policy_client
        mock_compliance.get_security_client.return_value = mock_security_client

        # Configure mock_resources
        mock_resources.list_subscriptions = AsyncMock()
        mock_resources.get_resource_client.return_value = mock_resource_client

        yield {
            "costs": mock_costs,
            "compliance": mock_compliance,
            "resources": mock_resources,
        }


@pytest.fixture
def mock_db_query(mock_tenant):
    """Create a mock database query."""
    query_mock = MagicMock()
    query_mock.filter.return_value = query_mock
    query_mock.all.return_value = [mock_tenant]
    query_mock.first.return_value = None  # Default to None for new resources
    return query_mock


@pytest.fixture
def mock_db_session(mock_db_query):
    """Create a mock database session.

    Queries for SyncJobLog (ghost job cleanup) return empty lists
    so that the ghost-cleanup path does not add extra commits.
    All other queries return the shared mock_db_query.
    """
    from app.models.monitoring import SyncJobLog

    ghost_query = MagicMock()
    ghost_query.filter.return_value.all.return_value = []
    ghost_query.filter.return_value.first.return_value = None

    def _query(model):
        if model is SyncJobLog:
            return ghost_query
        return mock_db_query

    session = MagicMock()
    session.query.side_effect = _query
    session.add = MagicMock()
    session.commit = MagicMock()
    session.close = MagicMock()
    return session


@pytest.fixture
def mock_get_db_context(mock_db_session):
    """Mock the get_db_context context manager."""
    with (
        patch("app.core.sync.costs.get_db_context") as mock_costs_ctx,
        patch("app.core.sync.compliance.get_db_context") as mock_compliance_ctx,
        patch("app.core.sync.resources.get_db_context") as mock_resources_ctx,
        patch("app.core.sync.identity.get_db_context") as mock_identity_ctx,
    ):
        # Create context managers that yield the mock session
        class MockContextManager:
            def __enter__(self):
                return mock_db_session

            def __exit__(self, *args):
                pass

        ctx = MockContextManager()
        mock_costs_ctx.return_value = ctx
        mock_compliance_ctx.return_value = ctx
        mock_resources_ctx.return_value = ctx
        mock_identity_ctx.return_value = ctx

        yield {
            "costs": mock_costs_ctx,
            "compliance": mock_compliance_ctx,
            "resources": mock_resources_ctx,
            "identity": mock_identity_ctx,
        }


@pytest.fixture
def mock_http_response_error():
    """Create a mock HttpResponseError."""
    error = MagicMock()
    error.status_code = 403
    error.message = "Access denied"
    return error


@pytest.fixture
def mock_client_auth_error():
    """Create a mock ClientAuthenticationError."""
    error = MagicMock()
    error.message = "Authentication failed"
    return error


@pytest.fixture
def sample_cost_rows():
    """Sample cost data rows from Azure API."""
    return [
        [10.50, 20240115, "USD", "rg-test", "Storage"],
        [25.00, 20240115, "USD", "rg-test", "Compute"],
        [5.25, 20240116, "USD", "rg-prod", "Storage"],
    ]


@pytest.fixture
def sample_policy_states():
    """Sample policy state objects."""
    state1 = MagicMock()
    state1.policy_definition_id = (
        "/providers/Microsoft.Authorization/policyDefinitions/test-policy-1"
    )
    state1.policy_definition_reference_id = "Test Policy 1"
    state1.compliance_state = MagicMock()
    state1.compliance_state.value = "Compliant"
    state1.resource_id = "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Storage/storageAccounts/testsa"
    state1.policy_definition_group_names = ["Storage"]

    state2 = MagicMock()
    state2.policy_definition_id = (
        "/providers/Microsoft.Authorization/policyDefinitions/test-policy-2"
    )
    state2.policy_definition_reference_id = "Test Policy 2"
    state2.compliance_state = MagicMock()
    state2.compliance_state.value = "NonCompliant"
    state2.resource_id = "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/testvm"
    state2.policy_definition_group_names = ["Compute"]

    return [state1, state2]


@pytest.fixture
def sample_resources():
    """Sample Azure resources."""
    resource1 = MagicMock()
    resource1.id = "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Storage/storageAccounts/testsa"
    resource1.name = "testsa"
    resource1.location = "eastus"
    resource1.type = "Microsoft.Storage/storageAccounts"
    resource1.provisioning_state = "Succeeded"
    resource1.tags = {"environment": "test", "costMonthly": "50.00"}
    resource1.sku = MagicMock()
    resource1.sku.name = "Standard_LRS"

    resource2 = MagicMock()
    resource2.id = "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/testvm"
    resource2.name = "testvm"
    resource2.location = "westus"
    resource2.type = "Microsoft.Compute/virtualMachines"
    resource2.provisioning_state = "Failed"
    resource2.tags = {"orphaned": "true"}
    resource2.sku = None

    return [resource1, resource2]


@pytest.fixture
def sample_users():
    """Sample user data from Graph API."""
    return [
        {
            "id": "user-1",
            "displayName": "Test User",
            "userPrincipalName": "test@example.com",
            "userType": "Member",
            "signInActivity": {
                "lastSignInDateTime": (datetime.utcnow() - timedelta(days=5)).isoformat() + "Z"
            },
        },
        {
            "id": "user-2",
            "displayName": "Guest User",
            "userPrincipalName": "guest@example.com",
            "userType": "Guest",
            "signInActivity": {
                "lastSignInDateTime": (datetime.utcnow() - timedelta(days=60)).isoformat() + "Z"
            },
        },
    ]


@pytest.fixture
def sample_directory_roles():
    """Sample directory role data from Graph API."""
    return [
        {
            "displayName": "Global Administrator",
            "description": "Can manage all aspects of Azure AD",
            "members": [
                {
                    "@odata.type": "#microsoft.graph.user",
                    "id": "user-1",
                    "displayName": "Test User",
                }
            ],
        },
    ]
