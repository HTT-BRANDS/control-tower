"""LighthouseCostMixin implementation for LighthouseAzureClient."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.services.lighthouse_support import lighthouse_module

logger = logging.getLogger(__name__)


class LighthouseCostMixin:
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
            raise lighthouse_module().LighthouseDelegationError(
                subscription_id, delegation_check.get("error", "Delegation not verified")
            )

        # Set default date range if not provided
        if not end_date:
            end_date = datetime.now(UTC)
        if not start_date:
            start_date = end_date - timedelta(days=30)

        try:
            cost_data = await lighthouse_module().resilient_api_call(
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
        client = lighthouse_module().CostManagementClient(self.credential, subscription_id)
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

        query = lighthouse_module().QueryDefinition(
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
