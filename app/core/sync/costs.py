"""Cost data synchronization module.

Uses the Azure Cost Management REST API directly (api-version 2023-11-01)
because the azure-mgmt-costmanagement SDK v4 (api 2022-10-01) returns empty
results for MCA (Microsoft Customer Agreement) billing accounts.
"""

import logging
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.exc import DataError, IntegrityError, ProgrammingError

from app.api.services.azure_client import azure_client_manager
from app.api.services.monitoring_service import MonitoringService
from app.core.circuit_breaker import COST_SYNC_BREAKER, circuit_breaker
from app.core.database import get_db_context
from app.core.retry import COST_SYNC_POLICY, retry_with_backoff
from app.models.cost import CostSnapshot
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

COST_API_VERSION = "2023-11-01"


@circuit_breaker(COST_SYNC_BREAKER)
@retry_with_backoff(COST_SYNC_POLICY)
async def sync_costs():
    """Sync cost data from all tenants.

    Fetches the last 30 days of cost data from Azure Cost Management API
    for all active tenants and their subscriptions, storing results in
    the CostSnapshot model grouped by resource group and service name.
    """
    logger.info(f"Starting cost sync at {datetime.now(UTC)}")

    # Define time period (last 30 days)
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=30)
    from_date = start_date.strftime("%Y-%m-%d")
    to_date = end_date.strftime("%Y-%m-%d")

    total_synced = 0
    total_errors = 0
    log_id = None

    try:
        # Start monitoring and get tenant list with a short-lived session
        with get_db_context() as db:
            monitoring = MonitoringService(db)
            log_entry = monitoring.start_sync_job(job_type="costs")
            log_id = log_entry.id
            tenants = db.query(Tenant).filter(Tenant.is_active).all()
            tenant_data = [(t.id, t.name, t.tenant_id) for t in tenants]

        logger.info(f"Found {len(tenant_data)} active tenants to sync")

        for tenant_id, tenant_name, azure_tenant_id in tenant_data:
            logger.info(f"Syncing costs for tenant: {tenant_name} ({azure_tenant_id})")

            try:
                with get_db_context() as tenant_db:
                    # Get subscriptions for this tenant
                    subscriptions = await azure_client_manager.list_subscriptions(azure_tenant_id)
                    logger.info(
                        f"Found {len(subscriptions)} subscriptions for tenant {tenant_name}"
                    )

                    for sub in subscriptions:
                        sub_id = sub["subscription_id"]
                        sub_name = sub["display_name"]

                        # Skip non-enabled subscriptions
                        if sub["state"] != "Enabled":
                            logger.info(f"Skipping subscription {sub_name} (state: {sub['state']})")
                            continue

                        try:
                            logger.info(
                                f"Querying costs for subscription: {sub_name} ({sub_id[:8]}...)"
                            )

                            rows = await _query_costs_rest(
                                azure_tenant_id,
                                sub_id,
                                from_date,
                                to_date,
                            )

                            if rows:
                                rows_processed = 0

                                # Column indices from Azure Cost Management API response:
                                # [0]=Cost, [1]=UsageDate, [2]=ResourceGroupName,
                                # [3]=ServiceName, [4]=Currency
                                # (matches grouping order in _query_costs_rest)
                                for row in rows:
                                    try:
                                        if len(row) < 3:
                                            continue

                                        # Extract values from row
                                        cost_value = float(row[0]) if row[0] else 0.0
                                        usage_date = datetime.strptime(str(row[1]), "%Y%m%d").date()
                                        resource_group = (
                                            str(row[2]) if len(row) > 2 and row[2] else None
                                        )
                                        service_name = (
                                            str(row[3]) if len(row) > 3 and row[3] else None
                                        )
                                        currency = str(row[4]) if len(row) > 4 and row[4] else "USD"

                                        # Skip zero-cost entries to save space
                                        if cost_value == 0.0:
                                            continue

                                        # Create or update cost snapshot
                                        snapshot = CostSnapshot(
                                            tenant_id=tenant_id,
                                            subscription_id=sub_id,
                                            date=usage_date,
                                            total_cost=cost_value,
                                            currency=currency,
                                            resource_group=resource_group,
                                            service_name=service_name,
                                            synced_at=datetime.now(UTC),
                                        )

                                        tenant_db.add(snapshot)
                                        rows_processed += 1

                                    except (ValueError, TypeError, IndexError) as e:
                                        logger.warning(f"Error processing cost row: {e}")
                                        continue

                                # Commit all snapshots for this subscription
                                tenant_db.commit()
                                total_synced += rows_processed
                                logger.info(
                                    f"Successfully synced {rows_processed} cost records "
                                    f"for subscription {sub_name}"
                                )
                            else:
                                logger.info(f"No cost data found for subscription {sub_name}")

                        except httpx.HTTPStatusError as e:
                            total_errors += 1
                            if e.response.status_code == 403:
                                logger.error(
                                    f"Access denied to cost data for subscription {sub_name}. "
                                    f"Missing Cost Management Reader role?"
                                )
                            else:
                                logger.error(
                                    f"HTTP error querying costs for subscription {sub_name}: "
                                    f"{e.response.status_code} - {e.response.text[:200]}"
                                )
                        except Exception as e:
                            total_errors += 1
                            logger.error(
                                f"Error syncing costs for subscription {sub_name}: {e}",
                                exc_info=True,
                            )

            except (IntegrityError, DataError, ProgrammingError) as e:
                total_errors += 1
                logger.error(f"Data error syncing costs for tenant {tenant_name}: {e}")
                continue
            except Exception as e:
                total_errors += 1
                logger.error(f"Error processing tenant {tenant_name}: {e}", exc_info=True)
                continue

        # Update monitoring with final status
        if log_id:
            with get_db_context() as db:
                monitoring = MonitoringService(db)
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
            f"Cost sync completed: {total_synced} records synced, {total_errors} errors encountered"
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


async def _query_costs_rest(
    tenant_id: str,
    subscription_id: str,
    from_date: str,
    to_date: str,
) -> list:
    """Query Cost Management REST API directly.

    The azure-mgmt-costmanagement SDK v4 (api 2022-10-01) returns empty
    results for MCA billing. The 2023-11-01 API works correctly, so we
    call it via httpx instead.

    Returns:
        List of cost rows, each row is [cost, date, currency, rg, service].
    """
    credential = azure_client_manager.get_credential(tenant_id)
    token = credential.get_token("https://management.azure.com/.default")

    url = (
        f"https://management.azure.com/subscriptions/{subscription_id}"
        f"/providers/Microsoft.CostManagement/query"
        f"?api-version={COST_API_VERSION}"
    )
    body = {
        "type": "ActualCost",
        "timeframe": "Custom",
        "timePeriod": {"from": from_date, "to": to_date},
        "dataset": {
            "granularity": "Daily",
            "aggregation": {
                "totalCost": {"name": "Cost", "function": "Sum"},
            },
            "grouping": [
                {"type": "Dimension", "name": "ResourceGroupName"},
                {"type": "Dimension", "name": "ServiceName"},
            ],
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            json=body,
            headers={"Authorization": f"Bearer {token.token}"},
        )
        resp.raise_for_status()

    data = resp.json()
    # API nests under "properties" in the REST response
    props = data.get("properties", data)
    return props.get("rows", [])
