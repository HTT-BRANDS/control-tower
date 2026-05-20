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
from app.core.sync.utils import determine_sync_outcome, get_sync_eligible_tenants
from app.models.cost import CostSnapshot
from app.models.monitoring import SyncJobLog
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

COST_API_VERSION = "2023-11-01"
COST_TENANT_FRESHNESS_JOB_TYPE = "costs_tenant"


def _record_tenant_cost_freshness(
    tenant_id: str,
    started_at: datetime,
    records_processed: int,
    errors_count: int,
    subscriptions_seen: int,
    error_messages: list[str],
) -> None:
    """Record per-tenant cost sync freshness, even when Azure returns $0 rows.

    CostSnapshot rows intentionally skip zero-cost entries. Without this marker,
    a tenant whose Cost Management query succeeds but returns no non-zero usage
    looks stale forever in /healthz/data. That is observability goblin nonsense:
    "freshly checked and zero" is different from "we never checked".
    """
    ended_at = datetime.now(UTC)
    status = "completed" if errors_count == 0 else "failed"
    with get_db_context() as db:
        db.add(
            SyncJobLog(
                job_type=COST_TENANT_FRESHNESS_JOB_TYPE,
                tenant_id=tenant_id,
                status=status,
                started_at=started_at,
                ended_at=ended_at,
                duration_ms=int((ended_at - started_at).total_seconds() * 1000),
                records_processed=records_processed,
                records_created=records_processed,
                records_updated=0,
                errors_count=errors_count,
                error_message="; ".join(error_messages)[:5000] if error_messages else None,
                details_json=(
                    f'{{"subscriptions_seen": {subscriptions_seen}, '
                    f'"zero_cost_success": {str(records_processed == 0 and errors_count == 0).lower()}}}'
                ),
            )
        )


async def _sync_subscription_costs(
    sub_db,
    tenant_id: int,
    azure_tenant_id: str,
    sub_id: str,
    sub_name: str,
    from_date: str,
    to_date: str,
) -> int:
    """Sync cost data for a single subscription using an isolated session.

    Each subscription gets its own DB session so that a flush/commit failure
    on one subscription does not poison the session for others (avoiding
    PendingRollbackError cascades).

    Returns:
        Number of cost records synced for this subscription.
    """
    logger.info(f"Querying costs for subscription: {sub_name} ({sub_id[:8]}...)")

    rows = await _query_costs_rest(
        azure_tenant_id,
        sub_id,
        from_date,
        to_date,
    )

    if not rows:
        logger.info(f"No cost data found for subscription {sub_name}")
        return 0

    rows_processed = 0

    # Column indices from Azure Cost Management API response:
    # [0]=Cost, [1]=UsageDate, [2]=ResourceGroupName,
    # [3]=ServiceName, [4]=Currency
    # (matches grouping order in _query_costs_rest)
    for row in rows:
        try:
            if len(row) < 3:
                continue

            cost_value = float(row[0]) if row[0] else 0.0
            usage_date = datetime.strptime(str(row[1]), "%Y%m%d").date()
            resource_group = str(row[2]) if len(row) > 2 and row[2] else None
            service_name = str(row[3]) if len(row) > 3 and row[3] else None
            currency = str(row[4]) if len(row) > 4 and row[4] else "USD"

            # Skip zero-cost entries to save space
            if cost_value == 0.0:
                continue

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

            sub_db.add(snapshot)
            rows_processed += 1

        except (ValueError, TypeError, IndexError) as e:
            logger.warning(f"Error processing cost row: {e}")
            continue

    sub_db.commit()
    logger.info(f"Successfully synced {rows_processed} cost records for subscription {sub_name}")
    return rows_processed


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
    total_subscriptions_seen = 0
    eligible_tenant_count = 0
    log_id = None

    try:
        # Start monitoring and get tenant list with a short-lived session
        with get_db_context() as db:
            monitoring = MonitoringService(db)
            log_entry = monitoring.start_sync_job(job_type="costs")
            log_id = log_entry.id
            tenants = db.query(Tenant).filter(Tenant.is_active).all()
            eligible_tenants = get_sync_eligible_tenants(tenants)
            tenant_data = [(t.id, t.name, t.tenant_id) for t in eligible_tenants]
            eligible_tenant_count = len(tenant_data)

        logger.info(f"Found {len(tenant_data)} sync-eligible tenants to sync")

        for tenant_id, tenant_name, azure_tenant_id in tenant_data:
            logger.info(f"Syncing costs for tenant: {tenant_name} ({azure_tenant_id})")
            tenant_started_at = datetime.now(UTC)
            tenant_synced = 0
            tenant_errors = 0
            tenant_subscriptions_seen = 0
            tenant_error_messages: list[str] = []

            try:
                # Get subscription list (Azure API call, no DB session needed)
                subscriptions = await azure_client_manager.list_subscriptions(azure_tenant_id)

                total_subscriptions_seen += len(subscriptions)
                tenant_subscriptions_seen = len(subscriptions)
                logger.info(f"Found {len(subscriptions)} subscriptions for tenant {tenant_name}")

                # Process each subscription in its own session to prevent
                # PendingRollbackError cascade when one subscription fails
                for sub in subscriptions:
                    sub_id = sub["subscription_id"]
                    sub_name = sub["display_name"]

                    # Skip non-enabled subscriptions
                    if sub["state"] != "Enabled":
                        logger.info(f"Skipping subscription {sub_name} (state: {sub['state']})")
                        continue

                    try:
                        with get_db_context() as sub_db:
                            synced = await _sync_subscription_costs(
                                sub_db=sub_db,
                                tenant_id=tenant_id,
                                azure_tenant_id=azure_tenant_id,
                                sub_id=sub_id,
                                sub_name=sub_name,
                                from_date=from_date,
                                to_date=to_date,
                            )
                            total_synced += synced
                            tenant_synced += synced
                    except (IntegrityError, DataError, ProgrammingError) as e:
                        total_errors += 1
                        tenant_errors += 1
                        message = f"Data error for subscription {sub_name}: {e}"
                        tenant_error_messages.append(message)
                        logger.error(message)
                    except httpx.HTTPStatusError as e:
                        total_errors += 1
                        tenant_errors += 1
                        if e.response.status_code == 403:
                            message = (
                                f"Access denied to cost data for subscription {sub_name}. "
                                f"Missing Cost Management Reader role?"
                            )
                            tenant_error_messages.append(message)
                            logger.error(message)
                        else:
                            message = (
                                f"HTTP error querying costs for subscription {sub_name}: "
                                f"{e.response.status_code} - {e.response.text[:200]}"
                            )
                            tenant_error_messages.append(message)
                            logger.error(message)
                    except Exception as e:
                        total_errors += 1
                        tenant_errors += 1
                        message = f"Unexpected error for subscription {sub_name}: {e}"
                        tenant_error_messages.append(message)
                        logger.error(message, exc_info=True)

            except Exception as e:
                total_errors += 1
                tenant_errors += 1
                message = f"Error processing tenant {tenant_name}: {e}"
                tenant_error_messages.append(message)
                logger.error(message, exc_info=True)
            finally:
                _record_tenant_cost_freshness(
                    tenant_id=tenant_id,
                    started_at=tenant_started_at,
                    records_processed=tenant_synced,
                    errors_count=tenant_errors,
                    subscriptions_seen=tenant_subscriptions_seen,
                    error_messages=tenant_error_messages,
                )

        # Determine final status and error summary
        final_status, error_summary, _outcome_details = determine_sync_outcome(
            job_type="costs",
            records_processed=total_synced,
            errors_count=total_errors,
            eligible_tenants=eligible_tenant_count,
            subscriptions_seen=total_subscriptions_seen,
        )

        # Update monitoring with final status
        if log_id:
            with get_db_context() as db:
                monitoring = MonitoringService(db)
                monitoring.complete_sync_job(
                    log_id=log_id,
                    status=final_status,
                    error_message=error_summary,
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
                    error_message=str(e)[:5000],
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
