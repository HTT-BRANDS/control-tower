"""LighthouseDelegationMixin implementation for LighthouseAzureClient."""

import logging
from typing import Any

from app.services.lighthouse_support import lighthouse_module

logger = logging.getLogger(__name__)


class LighthouseDelegationMixin:
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
            subscription = await lighthouse_module().resilient_api_call(
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
                raise lighthouse_module().LighthouseDelegationError(
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
        client = lighthouse_module().SubscriptionClient(self.credential)
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
