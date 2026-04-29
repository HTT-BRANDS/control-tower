"""Azure client for cross-tenant access via Lighthouse delegation.

This module provides a client that uses DefaultAzureCredential (Managed Identity)
to access delegated customer subscriptions via Azure Lighthouse. No credentials
are stored or managed per-tenant - access is granted through Azure Lighthouse
delegation.

Example:
    client = LighthouseAzureClient()

    # Verify delegation is working
    is_valid = await client.verify_delegation(subscription_id="customer-sub-id")

    # Get cost data
    cost_data = await client.get_cost_data(subscription_id="customer-sub-id")

    # List resources
    resources = await client.list_resources(subscription_id="customer-sub-id")
"""

import logging
from typing import Any

from azure.identity import DefaultAzureCredential
from azure.mgmt.costmanagement import CostManagementClient as CostManagementClient
from azure.mgmt.costmanagement.models import QueryDefinition as QueryDefinition
from azure.mgmt.resource import ResourceManagementClient as ResourceManagementClient
from azure.mgmt.security import SecurityCenter as SecurityCenter
from azure.mgmt.subscription import SubscriptionClient as SubscriptionClient

from app.core.resilience import (
    ResilientAzureClient,
)
from app.core.resilience import (
    resilient_api_call as resilient_api_call,
)
from app.services.lighthouse_access import LighthouseAccessMixin
from app.services.lighthouse_cost import LighthouseCostMixin
from app.services.lighthouse_delegation import LighthouseDelegationMixin
from app.services.lighthouse_resources import LighthouseResourceMixin
from app.services.lighthouse_security import LighthouseSecurityMixin

logger = logging.getLogger(__name__)


class LighthouseDelegationError(Exception):
    """Raised when Lighthouse delegation verification fails."""

    def __init__(self, subscription_id: str, message: str) -> None:
        """Initialize the error.

        Args:
            subscription_id: The subscription that failed delegation verification
            message: Detailed error message
        """
        self.subscription_id = subscription_id
        super().__init__(f"Lighthouse delegation failed for {subscription_id}: {message}")


class LighthouseAzureClient(
    LighthouseAccessMixin,
    LighthouseCostMixin,
    LighthouseDelegationMixin,
    LighthouseResourceMixin,
    LighthouseSecurityMixin,
):
    """Azure client for cross-tenant access via Lighthouse delegation.

    Uses DefaultAzureCredential (Managed Identity in Azure, Azure CLI locally)
    to access customer subscriptions that have delegated access via
    Azure Lighthouse.

    Features:
    - No credential storage required (uses Managed Identity)
    - Integrated rate limiting via ResilientAzureClient
    - Circuit breaker protection for resilience
    - Proper error handling for delegation failures
    - Structured data compatible with existing models

    Example:
        client = LighthouseAzureClient()

        # Verify access before operations
        if await client.verify_delegation("sub-123"):
            resources = await client.list_resources("sub-123")
    """

    def __init__(self, credential: DefaultAzureCredential | None = None) -> None:
        """Initialize the Lighthouse Azure client.

        Args:
            credential: Optional Azure credential. If None, uses DefaultAzureCredential.
        """
        self.credential = credential or DefaultAzureCredential()
        self.resilience = ResilientAzureClient(api_name="arm")

        # Initialize per-API resilient clients
        self._arm_resilience = ResilientAzureClient(api_name="arm")
        self._cost_resilience = ResilientAzureClient(api_name="cost")
        self._security_resilience = ResilientAzureClient(api_name="security")

        logger.debug("LighthouseAzureClient initialized with DefaultAzureCredential")

    def get_health_status(self) -> dict[str, Any]:
        """Get health status of the Lighthouse client.

        Returns:
            Dictionary with health information:
            {
                "status": str,
                "resilience_state": dict,
                "credential_type": str
            }
        """
        return {
            "status": "healthy",
            "resilience_state": {
                "arm": self._arm_resilience.get_state(),
                "cost": self._cost_resilience.get_state(),
                "security": self._security_resilience.get_state(),
            },
            "credential_type": type(self.credential).__name__,
        }


# Global client instance for convenience
_lighthouse_client: LighthouseAzureClient | None = None


def get_lighthouse_client() -> LighthouseAzureClient:
    """Get or create the global LighthouseAzureClient instance.

    Returns:
        LighthouseAzureClient singleton instance

    Example:
        client = get_lighthouse_client()
        resources = await client.list_resources("sub-123")
    """
    global _lighthouse_client
    if _lighthouse_client is None:
        _lighthouse_client = LighthouseAzureClient()
    return _lighthouse_client


def reset_lighthouse_client() -> None:
    """Reset the global client instance.

    Useful for testing or after credential changes.
    """
    global _lighthouse_client
    _lighthouse_client = None
    logger.debug("Lighthouse client reset")
