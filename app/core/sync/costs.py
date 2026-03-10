"""Cost data synchronization module."""

import logging
from datetime import datetime, timedelta

from azure.core.exceptions import HttpResponseError
from azure.mgmt.costmanagement.models import (
    QueryAggregation,
    QueryDataset,
    QueryDefinition,
    QueryGrouping,
    QueryTimePeriod,
)

from app.api.services.azure_client import azure_client_manager
from app.api.services.monitoring_service import MonitoringService
from app.core.circuit_breaker import COST_SYNC_BREAKER, circuit_breaker
from app.core.database import get_db_context
from app.core.retry import COST_SYNC_POLICY, retry_with_backoff
from app.models.cost import CostSnapshot
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)


@circuit_breaker(COST_SYNC_BREAKER)
@retry_with_backoff(COST_SYNC_POLICY)
async def sync_costs():
    """Sync cost data from all tenants.

    Fetches the last 30 days of cost data from Azure Cost Management API
    for all active tenants and their subscriptions, storing results in
    the CostSnapshot model grouped by resource group and service name.
    """
    logger.info(f"Starting cost sync at {datetime.utcnow()}")

    # Define time period (last 30 days)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    from_date = start_date.strftime("%Y-%m-%d")
    to_date = end_date.strftime("%Y-%m-%d")

    total_synced = 0
    total_errors = 0
    log_id = None

    try:
        with get_db_context() as db:
            # Start monitoring
            monitoring = MonitoringService(db)
            log_entry = monitoring.start_sync_job(job_type="costs")
            log_id = log_entry.id
            # Get all active tenants
            tenants = db.query(Tenant).filter(Tenant.is_active).all()
            logger.info(f"Found {len(tenants)} active tenants to sync")

            for tenant in tenants:
                logger.info(f"Syncing costs for tenant: {tenant.name} ({tenant.tenant_id})")

                try:
                    # Get subscriptions for this tenant
                    subscriptions = await azure_client_manager.list_subscriptions(tenant.tenant_id)
                    logger.info(f"Found {len(subscriptions)} subscriptions for tenant {tenant.name}")

                    for sub in subscriptions:
                        sub_id = sub["subscription_id"]
                        sub_name = sub["display_name"]

                        # Skip non-enabled subscriptions
                        if sub["state"] != "Enabled":
                            logger.info(f"Skipping subscription {sub_name} (state: {sub['state']})")
                            continue

                        try:
                            logger.info(f"Querying costs for subscription: {sub_name} ({sub_id[:8]}...)")

                            # Get cost client for this subscription
                            cost_client = azure_client_manager.get_cost_client(
                                tenant.tenant_id,
                                sub_id
                            )

                            # Build query definition with grouping by ResourceGroup and ServiceName
                            query = QueryDefinition(
                                type="ActualCost",
                                timeframe="Custom",
                                time_period=QueryTimePeriod(
                                    from_property=from_date,
                                    to=to_date,
                                ),
                                dataset=QueryDataset(
                                    granularity="Daily",
                                    aggregation={
                                        "totalCost": QueryAggregation(name="Cost", function="Sum")
                                    },
                                    grouping=[
                                        QueryGrouping(type="Dimension", name="ResourceGroupName"),
                                        QueryGrouping(type="Dimension", name="ServiceName"),
                                    ],
                                ),
                            )

                            # Execute query
                            result = cost_client.query.usage(
                                scope=f"/subscriptions/{sub_id}",
                                parameters=query,
                            )

                            # Process results — SDK v4+ puts rows/columns
                            # directly on QueryResult (not under .properties)
                            rows = getattr(result, 'rows', None)
                            if rows is None and hasattr(result, 'properties'):
                                rows = getattr(result.properties, 'rows', None)

                            if rows:
                                rows_processed = 0

                                # Column indices (based on query grouping and aggregation)
                                # Typical order: Cost, UsageDate, Currency, ResourceGroupName, ServiceName
                                for row in rows:
                                    try:
                                        if len(row) < 3:
                                            continue

                                        # Extract values from row
                                        cost_value = float(row[0]) if row[0] else 0.0
                                        usage_date = datetime.strptime(str(row[1]), "%Y%m%d").date()
                                        currency = str(row[2]) if len(row) > 2 and row[2] else "USD"
                                        resource_group = str(row[3]) if len(row) > 3 and row[3] else None
                                        service_name = str(row[4]) if len(row) > 4 and row[4] else None

                                        # Skip zero-cost entries to save space
                                        if cost_value == 0.0:
                                            continue

                                        # Create or update cost snapshot
                                        snapshot = CostSnapshot(
                                            tenant_id=tenant.id,
                                            subscription_id=sub_id,
                                            date=usage_date,
                                            total_cost=cost_value,
                                            currency=currency,
                                            resource_group=resource_group,
                                            service_name=service_name,
                                            synced_at=datetime.utcnow(),
                                        )

                                        db.add(snapshot)
                                        rows_processed += 1

                                    except (ValueError, TypeError, IndexError) as e:
                                        logger.warning(f"Error processing cost row: {e}")
                                        continue

                                # Commit all snapshots for this subscription
                                db.commit()
                                total_synced += rows_processed
                                logger.info(
                                    f"Successfully synced {rows_processed} cost records "
                                    f"for subscription {sub_name}"
                                )
                            else:
                                logger.info(f"No cost data found for subscription {sub_name}")

                        except HttpResponseError as e:
                            total_errors += 1
                            if e.status_code == 403:
                                logger.error(
                                    f"Access denied to cost data for subscription {sub_name}. "
                                    f"Missing Cost Management Reader role?"
                                )
                            else:
                                logger.error(
                                    f"HTTP error querying costs for subscription {sub_name}: "
                                    f"{e.status_code} - {e.message}"
                                )
                        except Exception as e:
                            total_errors += 1
                            logger.error(
                                f"Error syncing costs for subscription {sub_name}: {e}",
                                exc_info=True
                            )

                except Exception as e:
                    total_errors += 1
                    logger.error(
                        f"Error processing tenant {tenant.name}: {e}",
                        exc_info=True
                    )

        # Update monitoring with final status
        if log_id:
            monitoring.complete_sync_job(
                log_id=log_id,
                status="completed" if total_errors == 0 else "failed",
                final_records={
                    "records_processed": total_synced,
                    "records_created": total_synced,
                    "records_updated": 0,
                    "errors_count": total_errors,
                },
            )

        logger.info(
            f"Cost sync completed: {total_synced} records synced, "
            f"{total_errors} errors encountered"
        )

    except Exception as e:
        logger.error(f"Fatal error during cost sync: {e}", exc_info=True)
        # Update monitoring with failure status
        if log_id:
            with get_db_context() as db:
                monitoring = MonitoringService(db)
                monitoring.complete_sync_job(
                    log_id=log_id,
                    status="failed",
                    error_message=str(e)[:1000],
                    final_records={
                        "records_processed": total_synced,
                        "records_created": total_synced,
                        "records_updated": 0,
                        "errors_count": total_errors + 1,
                    },
                )
        raise
