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
from datetime import datetime, timedelta
from typing import Any

from azure.identity import DefaultAzureCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import QueryDefinition
from azure.mgmt.resource import ResourceManagementClient, SubscriptionClient
from azure.mgmt.security import SecurityCenter

from app.core.resilience import (
    ResilientAzureClient,
    resilient_api_call,
)

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


class LighthouseAzureClient:
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

    async def verify_delegation(self, subscription_id: str) -> dict[str, Any]:
        """Verify that Lighthouse delegation is working for a subscription.

        Attempts to access the subscription and returns delegation status.

        Args:
            subscription_id: The Azure subscription ID to verify

        Returns:
            Dictionary with delegation status:
            {
                "success": bool,
                "is_delegated": bool,
                "subscription_id": str,
                "display_name": str | None,
                "state": str | None,
                "tenant_id": str | None,
                "error": str | None
            }

        Raises:
            LighthouseDelegationError: If there's an actual API error (auth failure, network timeout)

        Example:
            result = await client.verify_delegation("12345-abc")
            if result["success"]:
                print(f"Access confirmed: {result['display_name']}")
        """
        logger.info(f"Verifying Lighthouse delegation for subscription: {subscription_id}")

        try:
            # Use resilient API call with rate limiting
            subscription = await resilient_api_call(
                func=self._get_subscription_sync,
                api_name="arm",
                max_retries=2,
                subscription_id=subscription_id,
            )

            if subscription:
                # Check if subscription is disabled
                state = subscription.get("state")
                if state and state.lower() == "disabled":
                    logger.warning(f"Subscription {subscription_id} is disabled")
                    return {
                        "success": False,
                        "is_delegated": False,
                        "subscription_id": subscription_id,
                        "display_name": subscription.get("display_name"),
                        "state": state,
                        "tenant_id": subscription.get("tenant_id"),
                        "error": "Subscription is disabled",
                    }

                logger.info(
                    f"Delegation verified for {subscription_id}: {subscription.get('display_name')}"
                )
                return {
                    "success": True,
                    "is_delegated": True,
                    "subscription_id": subscription_id,
                    "display_name": subscription.get("display_name"),
                    "state": subscription.get("state"),
                    "tenant_id": subscription.get("tenant_id"),
                    "error": None,
                }
            else:
                logger.warning(f"Subscription {subscription_id} not found via Lighthouse")
                return {
                    "success": False,
                    "is_delegated": False,
                    "subscription_id": subscription_id,
                    "display_name": None,
                    "state": None,
                    "tenant_id": None,
                    "error": "Subscription not found via Lighthouse delegation",
                }

        except Exception as e:
            # Check if this is an authentication or network error - these should raise
            # For ResilienceError, check the underlying last_error
            error_to_check = e
            if hasattr(e, "last_error") and e.last_error:
                error_to_check = e.last_error

            error_str = str(error_to_check).lower()
            if any(
                err in error_str
                for err in ["authentication", "unauthorized", "forbidden", "timeout", "network"]
            ):
                logger.error(
                    f"Delegation verification failed with API error for {subscription_id}: {error_to_check}"
                )
                raise LighthouseDelegationError(
                    subscription_id,
                    f"API error during delegation verification: {str(error_to_check)}",
                ) from e

            # Other errors return as failure result
            logger.error(f"Delegation verification failed for {subscription_id}: {e}")
            return {
                "success": False,
                "is_delegated": False,
                "subscription_id": subscription_id,
                "display_name": None,
                "state": None,
                "tenant_id": None,
                "error": f"Failed to verify delegation: {str(e)}",
            }

    def _get_subscription_sync(self, subscription_id: str) -> dict[str, Any] | None:
        """Synchronous helper to get subscription details.

        Args:
            subscription_id: The Azure subscription ID

        Returns:
            Subscription details or None if not found

        Raises:
            Exception: If API call fails (authentication, network, etc.)
        """
        client = SubscriptionClient(self.credential)
        # For Lighthouse, list all accessible subscriptions and filter
        for sub in client.subscriptions.list():
            if sub.subscription_id == subscription_id:
                return {
                    "subscription_id": sub.subscription_id,
                    "display_name": sub.display_name,
                    "state": sub.state.value if hasattr(sub.state, "value") else str(sub.state),
                    "tenant_id": sub.tenant_id,
                }
        # Subscription not found in accessible list
        return None

    async def list_resources(
        self,
        subscription_id: str,
        resource_group: str | None = None,
        resource_type: str | None = None,
    ) -> dict[str, Any]:
        """List Azure resources in a subscription via Lighthouse.

        Args:
            subscription_id: The delegated subscription ID
            resource_group: Optional resource group name to filter
            resource_type: Optional resource type to filter (e.g., "Microsoft.Compute/virtualMachines")

        Returns:
            Dictionary with resources:
            {
                "success": bool,
                "resources": list[dict],
                "count": int,
                "subscription_id": str,
                "error": str | None
            }
            Where each resource has:
            - id: Full resource ID
            - name: Resource name
            - type: Resource type
            - location: Azure region
            - tags: Resource tags
            - resource_group: Resource group name

        Raises:
            LighthouseDelegationError: If delegation verification fails

        Example:
            result = await client.list_resources("sub-123")
            for r in result["resources"]:
                print(f"{r['name']}: {r['type']} in {r['location']}")
        """
        logger.debug(f"Listing resources for subscription: {subscription_id}")

        # Verify delegation first
        delegation_check = await self.verify_delegation(subscription_id)
        if not delegation_check["is_delegated"]:
            raise LighthouseDelegationError(
                subscription_id, delegation_check.get("error", "Delegation not verified")
            )

        try:
            resources = await resilient_api_call(
                func=self._list_resources_sync,
                api_name="arm",
                max_retries=3,
                subscription_id=subscription_id,
                resource_group=resource_group,
                resource_type=resource_type,
            )

            logger.info(f"Retrieved {len(resources)} resources from {subscription_id}")
            return {
                "success": True,
                "resources": resources,
                "count": len(resources),
                "subscription_id": subscription_id,
                "error": None,
            }

        except Exception as e:
            logger.error(f"Failed to list resources for {subscription_id}: {e}")
            raise

    def _list_resources_sync(
        self,
        subscription_id: str,
        resource_group: str | None = None,
        resource_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Synchronous helper to list resources.

        Args:
            subscription_id: The Azure subscription ID
            resource_group: Optional resource group filter
            resource_type: Optional resource type filter

        Returns:
            List of resource dictionaries
        """
        client = ResourceManagementClient(self.credential, subscription_id)
        resources = []

        try:
            if resource_group:
                # List resources in specific resource group
                for resource in client.resources.list_by_resource_group(resource_group):
                    resource_dict = self._resource_to_dict(resource)
                    # Apply resource_type filter if specified
                    if resource_type is None or resource_dict.get("type") == resource_type:
                        resources.append(resource_dict)
            else:
                # List all resources in subscription
                for resource in client.resources.list():
                    resource_dict = self._resource_to_dict(resource)
                    # Apply resource_type filter if specified
                    if resource_type is None or resource_dict.get("type") == resource_type:
                        resources.append(resource_dict)

        except Exception as e:
            logger.error(f"Error listing resources: {e}")
            raise

        return resources

    def _resource_to_dict(self, resource) -> dict[str, Any]:
        """Convert Azure resource object to dictionary.

        Args:
            resource: Azure SDK resource object

        Returns:
            Dictionary representation of the resource
        """
        # Extract resource group from ID
        resource_group = None
        if resource.id and "/resourceGroups/" in resource.id:
            try:
                rg_start = resource.id.index("/resourceGroups/") + len("/resourceGroups/")
                rg_end = resource.id.index("/", rg_start)
                resource_group = resource.id[rg_start:rg_end]
            except (ValueError, IndexError):
                pass

        return {
            "id": resource.id,
            "name": resource.name,
            "type": resource.type,
            "location": resource.location,
            "tags": resource.tags or {},
            "resource_group": resource_group,
            "sku": resource.sku.name if resource.sku else None,
            "kind": resource.kind,
            "managed_by": resource.managed_by,
        }

    async def get_cost_data(
        self,
        subscription_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        granularity: str = "Daily",
        group_by: list[str] | None = None,
    ) -> dict[str, Any]:
        """Retrieve cost data for a delegated subscription via Lighthouse.

        Args:
            subscription_id: The delegated subscription ID
            start_date: Start date for cost query (defaults to 30 days ago)
            end_date: End date for cost query (defaults to today)
            granularity: Granularity - "Daily" or "Monthly"
            group_by: Optional list of dimensions to group by (e.g., ["ServiceName", "ResourceGroup"])

        Returns:
            Dictionary with cost data:
            {
                "success": bool,
                "subscription_id": str,
                "cost": float,
                "currency": str,
                "start_date": str,
                "end_date": str,
                "rows": list[dict] | None,
                "breakdown": list[dict] | None,
                "error": str | None
            }

        Raises:
            LighthouseDelegationError: If delegation verification fails

        Example:
            cost_data = await client.get_cost_data(
                subscription_id="sub-123",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 31),
                group_by=["ServiceName", "ResourceGroup"]
            )
        """
        logger.debug(f"Retrieving cost data for subscription: {subscription_id}")

        # Verify delegation first
        delegation_check = await self.verify_delegation(subscription_id)
        if not delegation_check["is_delegated"]:
            raise LighthouseDelegationError(
                subscription_id, delegation_check.get("error", "Delegation not verified")
            )

        # Set default date range if not provided
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        try:
            cost_data = await resilient_api_call(
                func=self._get_cost_data_sync,
                api_name="cost",
                max_retries=3,
                subscription_id=subscription_id,
                start_date=start_date,
                end_date=end_date,
                granularity=granularity,
                group_by=group_by,
            )

            logger.info(
                f"Retrieved cost data for {subscription_id}: {cost_data['cost']} {cost_data['currency']}"
            )
            return cost_data

        except Exception as e:
            logger.error(f"Failed to get cost data for {subscription_id}: {e}")
            raise

    def _get_cost_data_sync(
        self,
        subscription_id: str,
        start_date: datetime,
        end_date: datetime,
        granularity: str,
        group_by: list[str] | None = None,
    ) -> dict[str, Any]:
        """Synchronous helper to get cost data.

        Args:
            subscription_id: The Azure subscription ID
            start_date: Query start date
            end_date: Query end date
            granularity: Daily or Monthly
            group_by: Optional list of dimensions to group by

        Returns:
            Dictionary with cost data
        """
        client = CostManagementClient(self.credential, subscription_id)
        scope = f"/subscriptions/{subscription_id}"

        # Format dates for Azure API
        from_date = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        to_date = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Build grouping configuration
        # Default grouping if not specified
        if group_by is None:
            grouping_config = [
                {"type": "Dimension", "name": "ResourceGroup"},
                {"type": "Dimension", "name": "ServiceName"},
            ]
        else:
            # Map group_by dimensions to Azure API format
            dimension_map = {
                "ResourceGroup": "ResourceGroup",
                "ServiceName": "ServiceName",
                "ResourceType": "ResourceType",
                "MeterCategory": "MeterCategory",
            }
            grouping_config = [
                {"type": "Dimension", "name": dimension_map.get(dim, dim)}
                for dim in group_by
                if dim in dimension_map
            ]

        query = QueryDefinition(
            type="Usage",
            timeframe="Custom",
            time_period={"from": from_date, "to": to_date},
            dataset={
                "granularity": granularity,
                "aggregation": {"totalCost": {"name": "PreTaxCost", "function": "Sum"}},
                "grouping": grouping_config,
            },
        )

        try:
            result = client.query.usage(scope, query)

            # Parse results
            rows = []
            total_cost = 0.0
            currency = "USD"

            if result.rows:
                for row in result.rows:
                    # Azure cost query returns columns based on grouping
                    # Always: [Cost, Currency, Date] + grouped dimensions
                    row_dict = {
                        "cost": float(row[0]) if len(row) > 0 else 0.0,
                        "currency": str(row[1]) if len(row) > 1 else "USD",
                        "date": str(row[2]) if len(row) > 2 else None,
                    }

                    # Add grouping dimensions dynamically
                    if len(row) > 3 and group_by:
                        for i, dim in enumerate(group_by):
                            if len(row) > 3 + i:
                                row_dict[dim] = str(row[3 + i])
                    elif len(row) > 3:
                        # Default grouping
                        row_dict["resource_group"] = str(row[3]) if len(row) > 3 else None
                        row_dict["service_name"] = str(row[4]) if len(row) > 4 else None

                    rows.append(row_dict)
                    total_cost += row_dict["cost"]
                    currency = row_dict["currency"]

            # Return in format expected by tests
            return {
                "success": True,
                "subscription_id": subscription_id,
                "cost": total_cost,
                "currency": currency,
                "start_date": from_date,
                "end_date": to_date,
                "rows": rows if len(rows) > 0 else None,
                "breakdown": rows if len(rows) > 0 else None,  # Alias for tests
                "error": None,
            }

        except Exception as e:
            logger.error(f"Cost query failed: {e}")
            raise

    async def get_security_assessments(
        self,
        subscription_id: str,
    ) -> dict[str, Any]:
        """Get security assessments for a delegated subscription.

        Retrieves security score and assessment results from Azure Security Center.

        Args:
            subscription_id: The delegated subscription ID

        Returns:
            Dictionary with security data:
            {
                "success": bool,
                "subscription_id": str,
                "secure_score": float | None,
                "max_score": float | None,
                "percentage": float,
                "assessments": list[dict],
                "recommendations_count": int,
                "error": str | None
            }

        Raises:
            LighthouseDelegationError: If delegation verification fails

        Example:
            security = await client.get_security_assessments("sub-123")
            print(f"Secure Score: {security['percentage']:.1f}%")
        """
        logger.debug(f"Retrieving security assessments for subscription: {subscription_id}")

        # Verify delegation first
        delegation_check = await self.verify_delegation(subscription_id)
        if not delegation_check["is_delegated"]:
            raise LighthouseDelegationError(
                subscription_id, delegation_check.get("error", "Delegation not verified")
            )

        try:
            security_data = await resilient_api_call(
                func=self._get_security_assessments_sync,
                api_name="security",
                max_retries=3,
                subscription_id=subscription_id,
            )

            logger.info(
                f"Retrieved security data for {subscription_id}: score={security_data.get('percentage', 0):.1f}%"
            )
            return security_data

        except Exception as e:
            logger.error(f"Failed to get security assessments for {subscription_id}: {e}")
            raise

    def _get_security_assessments_sync(self, subscription_id: str) -> dict[str, Any]:
        """Synchronous helper to get security assessments.

        Args:
            subscription_id: The Azure subscription ID

        Returns:
            Dictionary with security assessment data
        """
        # Security Center requires a location parameter
        asc_location = "centralus"
        client = SecurityCenter(self.credential, subscription_id, asc_location)

        assessments = []
        secure_score = None
        max_score = None
        percentage = 0.0

        try:
            # Get secure scores
            scores = list(client.secure_scores.list())
            if scores:
                score = scores[0]
                secure_score = float(score.score.current) if score.score else 0.0
                max_score = float(score.max) if hasattr(score, "max") else 100.0
                percentage = (secure_score / max_score * 100) if max_score > 0 else 0.0

        except Exception as e:
            logger.warning(f"Could not retrieve secure score: {e}")

        try:
            # Get security assessments
            for assessment in client.assessments.list():
                assessments.append(
                    {
                        "id": assessment.id,
                        "name": assessment.name,
                        "display_name": assessment.display_name,
                        "resource_details": assessment.resource_details,
                        "status": assessment.status.code if assessment.status else None,
                        "severity": assessment.status.severity if assessment.status else None,
                    }
                )

        except Exception as e:
            logger.warning(f"Could not retrieve all assessments: {e}")

        return {
            "success": True,
            "subscription_id": subscription_id,
            "secure_score": secure_score,
            "max_score": max_score,
            "percentage": percentage,
            "assessments": assessments,
            "recommendations_count": len(assessments),
            "error": None,
        }

    async def validate_tenant_access(
        self,
        tenant_id: str,
        subscription_id: str,
    ) -> dict[str, Any]:
        """Comprehensive validation of tenant access via Lighthouse.

        Performs multiple checks to validate that:
        1. The subscription is accessible
        2. Cost data can be retrieved
        3. Security data can be retrieved
        4. Resources can be listed

        Args:
            tenant_id: The Azure tenant ID
            subscription_id: The Azure subscription ID

        Returns:
            Dictionary with validation results:
            {
                "is_valid": bool,
                "tenant_id": str,
                "subscription_id": str,
                "delegation_verified": bool,
                "cost_accessible": bool,
                "security_accessible": bool,
                "resources_accessible": bool,
                "details": dict,
                "errors": list[str]
            }

        Example:
            validation = await client.validate_tenant_access(
                tenant_id="tenant-123",
                subscription_id="sub-456"
            )
            if validation["is_valid"]:
                print("Tenant access validated successfully")
        """
        logger.info(f"Validating tenant access for {tenant_id}/{subscription_id}")

        result = {
            "is_valid": False,
            "tenant_id": tenant_id,
            "subscription_id": subscription_id,
            "delegation_verified": False,
            "cost_accessible": False,
            "security_accessible": False,
            "resources_accessible": False,
            "details": {},
            "errors": [],
        }

        # Step 1: Verify delegation
        try:
            delegation = await self.verify_delegation(subscription_id)
            result["delegation_verified"] = delegation["is_delegated"]
            result["details"]["subscription"] = delegation

            if not delegation["is_delegated"]:
                result["errors"].append(
                    f"Delegation verification failed: {delegation.get('error')}"
                )
                return result

        except Exception as e:
            result["errors"].append(f"Delegation check failed: {str(e)}")
            return result

        # Step 2: Test cost access
        try:
            cost_data = await self.get_cost_data(
                subscription_id=subscription_id,
                start_date=datetime.utcnow() - timedelta(days=7),
                end_date=datetime.utcnow(),
            )
            result["cost_accessible"] = True
            result["details"]["cost_sample"] = {
                "total_cost": cost_data.get("total_cost"),
                "currency": cost_data.get("currency"),
            }
        except Exception as e:
            result["errors"].append(f"Cost access failed: {str(e)}")
            logger.warning(f"Cost access test failed for {subscription_id}: {e}")

        # Step 3: Test security access
        try:
            security_data = await self.get_security_assessments(subscription_id)
            result["security_accessible"] = True
            result["details"]["security_sample"] = {
                "secure_score": security_data.get("secure_score"),
                "percentage": security_data.get("percentage"),
            }
        except Exception as e:
            result["errors"].append(f"Security access failed: {str(e)}")
            logger.warning(f"Security access test failed for {subscription_id}: {e}")

        # Step 4: Test resource listing (limited to first 10)
        try:
            resources = await self.list_resources(subscription_id)
            result["resources_accessible"] = True
            result["details"]["resource_count"] = len(resources)
        except Exception as e:
            result["errors"].append(f"Resource access failed: {str(e)}")
            logger.warning(f"Resource access test failed for {subscription_id}: {e}")

        # Determine overall validity
        # At minimum, delegation must be verified
        # For full validity, we want cost, security, and resources
        result["is_valid"] = (
            result["delegation_verified"]
            and result["cost_accessible"]
            and result["resources_accessible"]
        )

        if result["is_valid"]:
            logger.info(f"Tenant access validation succeeded for {tenant_id}/{subscription_id}")
        else:
            logger.warning(
                f"Tenant access validation failed for {tenant_id}/{subscription_id}: {result['errors']}"
            )

        return result

    async def get_delegated_subscriptions(self) -> list[dict[str, Any]]:
        """List all subscriptions accessible via Lighthouse delegation.

        Returns:
            List of subscription dictionaries with:
            - subscription_id: str
            - display_name: str
            - state: str
            - tenant_id: str
            - is_delegated: bool (True for all returned subscriptions)

        Example:
            subscriptions = await client.get_delegated_subscriptions()
            for sub in subscriptions:
                print(f"{sub['display_name']} ({sub['subscription_id']})")
        """
        logger.debug("Listing all delegated subscriptions")

        try:
            subscriptions = await resilient_api_call(
                func=self._list_subscriptions_sync,
                api_name="arm",
                max_retries=3,
            )

            logger.info(f"Found {len(subscriptions)} accessible subscriptions via Lighthouse")
            return subscriptions

        except Exception as e:
            logger.error(f"Failed to list delegated subscriptions: {e}")
            raise

    def _list_subscriptions_sync(self) -> list[dict[str, Any]]:
        """Synchronous helper to list all subscriptions.

        Returns:
            List of subscription dictionaries
        """
        client = SubscriptionClient(self.credential)
        subscriptions = []

        try:
            for sub in client.subscriptions.list():
                subscriptions.append(
                    {
                        "subscription_id": sub.subscription_id,
                        "display_name": sub.display_name,
                        "state": sub.state.value if hasattr(sub.state, "value") else str(sub.state),
                        "tenant_id": sub.tenant_id,
                        "is_delegated": True,  # All returned via DefaultAzureCredential are accessible
                    }
                )
        except Exception as e:
            logger.error(f"Error listing subscriptions: {e}")
            raise

        return subscriptions

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
