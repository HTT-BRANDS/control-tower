"""LighthouseAccessMixin implementation for LighthouseAzureClient."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.services.lighthouse_support import lighthouse_module

logger = logging.getLogger(__name__)


class LighthouseAccessMixin:
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
                start_date=datetime.now(UTC) - timedelta(days=7),
                end_date=datetime.now(UTC),
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
            subscriptions = await lighthouse_module().resilient_api_call(
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
        client = lighthouse_module().SubscriptionClient(self.credential)
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
