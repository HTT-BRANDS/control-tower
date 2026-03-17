"""Budget synchronization module for Azure Cost Management integration.

Provides scheduled and on-demand sync of budget data from Azure,
along with threshold monitoring and alert generation.
"""

import logging
from datetime import datetime

from app.api.services.budget_service import BudgetService, BudgetServiceError
from app.core.circuit_breaker import BUDGET_SYNC_BREAKER, circuit_breaker
from app.core.database import get_db_context
from app.core.retry import BUDGET_SYNC_POLICY, retry_with_backoff
from app.models.budget import Budget, BudgetAlert, BudgetSyncResult
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)


@circuit_breaker(BUDGET_SYNC_BREAKER)
@retry_with_backoff(BUDGET_SYNC_POLICY)
async def sync_budgets_for_tenant(
    tenant_id: str,
    subscription_ids: list[str] | None = None,
    sync_type: str = "incremental",
) -> BudgetSyncResult:
    """Sync budgets from Azure Cost Management for a specific tenant.

    Pulls budget definitions, current spending, and forecast data from
    Azure Cost Management API and updates local database records.

    Args:
        tenant_id: Azure tenant ID to sync
        subscription_ids: Optional list of specific subscriptions to sync
        sync_type: Sync type - "full", "incremental", or "alerts_only"

    Returns:
        BudgetSyncResult with sync statistics
    """
    logger.info(f"Starting budget sync for tenant {tenant_id} (type: {sync_type})")

    started_at = datetime.utcnow()

    with get_db_context() as db:
        service = BudgetService(db)

        # Create sync result record
        sync_result = BudgetSyncResult(
            tenant_id=tenant_id,
            sync_type=sync_type,
            status="running",
            started_at=started_at,
        )
        db.add(sync_result)
        db.commit()

        try:
            # Perform the sync
            result_response = await service.sync_budgets_from_azure(
                tenant_id=tenant_id,
                subscription_ids=subscription_ids,
            )

            # Update sync result with response data
            sync_result.status = result_response.status
            sync_result.budgets_synced = result_response.budgets_synced
            sync_result.budgets_created = result_response.budgets_created
            sync_result.budgets_updated = result_response.budgets_updated
            sync_result.budgets_deleted = result_response.budgets_deleted
            sync_result.alerts_triggered = result_response.alerts_triggered
            sync_result.errors_count = result_response.errors_count

            if result_response.error_message:
                sync_result.error_message = result_response.error_message

            sync_result.complete(sync_result.status)
            db.commit()

            logger.info(
                f"Budget sync completed for tenant {tenant_id}: "
                f"{sync_result.budgets_synced} budgets synced, "
                f"{sync_result.alerts_triggered} alerts triggered"
            )

            return sync_result

        except Exception as e:
            sync_result.status = "failed"
            sync_result.error_message = str(e)[:1000]
            sync_result.complete("failed")
            db.commit()

            logger.error(f"Budget sync failed for tenant {tenant_id}: {e}")
            raise BudgetSyncError(f"Failed to sync budgets for tenant {tenant_id}: {e}") from e


async def sync_budget_alerts(tenant_id: str | None = None) -> dict[str, int]:
    """Check budget thresholds and create alerts for breaches.

    Evaluates all budget thresholds and creates alert records when
    spending crosses configured thresholds.

    Args:
        tenant_id: Optional tenant ID to limit scope (None for all tenants)

    Returns:
        Dict with alert statistics by tenant
    """
    logger.info(f"Starting budget alert check (tenant: {tenant_id or 'all'})")

    alerts_triggered: dict[str, int] = {}

    with get_db_context() as db:
        # Get budgets to check
        query = db.query(Budget)
        if tenant_id:
            query = query.filter(Budget.tenant_id == tenant_id)

        budgets = query.all()

        for budget in budgets:
            tenant_alerts = 0

            for threshold in budget.thresholds:
                if not threshold.is_enabled:
                    continue

                threshold_amount = threshold.calculate_amount(budget.amount)

                # Check if threshold is breached
                if budget.current_spend >= threshold_amount:
                    # Check if alert already exists
                    existing_alert = (
                        db.query(BudgetAlert)
                        .filter(
                            BudgetAlert.budget_id == budget.id,
                            BudgetAlert.threshold_id == threshold.id,
                            BudgetAlert.status.in_(["pending", "acknowledged"]),
                        )
                        .first()
                    )

                    if not existing_alert:
                        # Determine alert type based on threshold percentage
                        if threshold.percentage >= 100:
                            alert_type = "exceeded"
                        elif threshold.percentage >= 80:
                            alert_type = "critical"
                        else:
                            alert_type = "warning"

                        # Create new alert
                        alert = BudgetAlert(
                            budget_id=budget.id,
                            threshold_id=threshold.id,
                            alert_type=alert_type,
                            status="pending",
                            threshold_percentage=threshold.percentage,
                            threshold_amount=threshold_amount,
                            current_spend=budget.current_spend,
                            forecasted_spend=budget.forecasted_spend,
                            utilization_percentage=budget.utilization_percentage,
                        )
                        db.add(alert)

                        # Update threshold stats
                        threshold.trigger_count += 1
                        threshold.last_triggered_at = datetime.utcnow()

                        tenant_alerts += 1

                        logger.info(
                            f"Budget alert triggered: {budget.name} at {threshold.percentage}% "
                            f"(${budget.current_spend:.2f} / ${budget.amount:.2f})"
                        )

            if tenant_alerts > 0:
                alerts_triggered[budget.tenant_id] = (
                    alerts_triggered.get(budget.tenant_id, 0) + tenant_alerts
                )

        db.commit()

    total_alerts = sum(alerts_triggered.values())
    logger.info(f"Budget alert check complete: {total_alerts} alerts triggered")

    return alerts_triggered


async def sync_all_tenant_budgets(
    sync_type: str = "incremental",
    include_alerts: bool = True,
) -> list[BudgetSyncResult]:
    """Sync budgets for all active tenants.

    Iterates through all active tenants and performs budget sync
    for each one.

    Args:
        sync_type: Sync type - "full", "incremental", or "alerts_only"
        include_alerts: Whether to also check thresholds and create alerts

    Returns:
        List of BudgetSyncResult for each tenant
    """
    logger.info(f"Starting budget sync for all tenants (type: {sync_type})")

    results: list[BudgetSyncResult] = []

    with get_db_context() as db:
        tenants = db.query(Tenant).filter(Tenant.is_active).all()

    for tenant in tenants:
        try:
            result = await sync_budgets_for_tenant(
                tenant_id=tenant.id,
                sync_type=sync_type,
            )
            results.append(result)
        except BudgetSyncError as e:
            logger.error(f"Failed to sync budgets for tenant {tenant.id}: {e}")
            # Continue with other tenants

    if include_alerts:
        try:
            await sync_budget_alerts()
        except Exception as e:
            logger.error(f"Failed to sync budget alerts: {e}")

    logger.info(f"Completed budget sync for {len(results)} tenants")
    return results


class BudgetSyncError(Exception):
    """Raised when budget synchronization fails."""

    pass


def get_last_sync_status(tenant_id: str) -> dict | None:
    """Get the last sync status for a tenant.

    Args:
        tenant_id: Tenant ID to check

    Returns:
        Dict with sync status or None if no sync found
    """
    with get_db_context() as db:
        last_sync = (
            db.query(BudgetSyncResult)
            .filter(BudgetSyncResult.tenant_id == tenant_id)
            .order_by(BudgetSyncResult.started_at.desc())
            .first()
        )

        if not last_sync:
            return None

        return {
            "id": last_sync.id,
            "status": last_sync.status,
            "sync_type": last_sync.sync_type,
            "started_at": last_sync.started_at.isoformat() if last_sync.started_at else None,
            "completed_at": last_sync.completed_at.isoformat() if last_sync.completed_at else None,
            "duration_seconds": last_sync.duration_seconds,
            "budgets_synced": last_sync.budgets_synced,
            "budgets_created": last_sync.budgets_created,
            "budgets_updated": last_sync.budgets_updated,
            "alerts_triggered": last_sync.alerts_triggered,
            "errors_count": last_sync.errors_count,
            "error_message": last_sync.error_message,
        }


def get_pending_alerts_count(tenant_id: str | None = None) -> int:
    """Get count of pending budget alerts.

    Args:
        tenant_id: Optional tenant to filter by

    Returns:
        Number of pending alerts
    """
    with get_db_context() as db:
        query = db.query(BudgetAlert).filter(BudgetAlert.status == "pending")

        if tenant_id:
            from app.models.budget import Budget

            query = query.join(Budget).filter(Budget.tenant_id == tenant_id)

        return query.count()


# Background task wrapper for scheduler integration
async def run_scheduled_budget_sync():
    """Entry point for scheduled budget synchronization.

    Can be registered with the task scheduler to run periodically.
    """
    logger.info("Starting scheduled budget sync")

    try:
        results = await sync_all_tenant_budgets(
            sync_type="incremental",
            include_alerts=True,
        )

        total_synced = sum(r.budgets_synced for r in results)
        total_alerts = sum(r.alerts_triggered for r in results)
        total_errors = sum(r.errors_count for r in results)

        logger.info(
            f"Scheduled budget sync complete: "
            f"{len(results)} tenants, {total_synced} budgets, "
            f"{total_alerts} alerts, {total_errors} errors"
        )

    except Exception as e:
        logger.error(f"Scheduled budget sync failed: {e}")
        raise
