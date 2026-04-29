"""LighthouseResourceMixin implementation for LighthouseAzureClient."""

import logging
from typing import Any

from app.services.lighthouse_support import lighthouse_module

logger = logging.getLogger(__name__)


class LighthouseResourceMixin:
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
            raise lighthouse_module().LighthouseDelegationError(
                subscription_id, delegation_check.get("error", "Delegation not verified")
            )

        try:
            resources = await lighthouse_module().resilient_api_call(
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
        client = lighthouse_module().ResourceManagementClient(self.credential, subscription_id)
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
