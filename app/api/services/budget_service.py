"""Budget management service with Azure Cost Management API integration.

Provides CRUD operations for budgets, threshold management, alert handling,
and synchronization with Azure Cost Management Budget API.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.api.services.azure_client import azure_client_manager
from app.core.cache import cached, invalidate_on_sync_completion
from app.core.circuit_breaker import BUDGET_SYNC_BREAKER, circuit_breaker
from app.core.retry import BUDGET_SYNC_POLICY, retry_with_backoff
from app.models.budget import (
    AlertStatus,
    AlertType,
    Budget,
    BudgetAlert,
    BudgetNotification,
    BudgetStatus,
    BudgetSyncResult,
    BudgetThreshold,
)
from app.models.tenant import Tenant
from app.schemas.budget import (
    BudgetAlertBulkResponse,
    BudgetAlertResponse,
    BudgetCreate,
    BudgetListItem,
    BudgetResponse,
    BudgetSummary,
    BudgetSyncResultResponse,
    BudgetThresholdResponse,
    BudgetUpdate,
)

logger = logging.getLogger(__name__)

BUDGET_API_VERSION = "2023-11-01"


class BudgetServiceError(Exception):
    """Raised when budget operations fail."""

    pass


class BudgetService:
    """Service for budget management operations with Azure integration."""

    def __init__(self, db: Session):
        self.db = db

    # =========================================================================
    # Budget CRUD Operations
    # =========================================================================

    async def get_budgets(
        self,
        tenant_ids: list[str] | None = None,
        subscription_ids: list[str] | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[BudgetListItem]:
        """Get list of budgets with optional filtering.

        Args:
            tenant_ids: Filter by tenant IDs
            subscription_ids: Filter by subscription IDs
            status: Filter by budget status
            limit: Maximum results to return
            offset: Pagination offset

        Returns:
            List of budget list items
        """
        query = self.db.query(Budget)

        if tenant_ids:
            query = query.filter(Budget.tenant_id.in_(tenant_ids))
        if subscription_ids:
            query = query.filter(Budget.subscription_id.in_(subscription_ids))
        if status:
            query = query.filter(Budget.status == status)

        query.count()
        budgets = query.order_by(Budget.created_at.desc()).offset(offset).limit(limit).all()

        # Build response with alert counts
        result = []
        for budget in budgets:
            pending_alerts = (
                budget.alerts.filter(BudgetAlert.status == AlertStatus.PENDING).count()
                if hasattr(budget.alerts, "filter")
                else sum(1 for a in budget.alerts if a.status == AlertStatus.PENDING)
            )

            result.append(
                BudgetListItem(
                    id=budget.id,
                    name=budget.name,
                    amount=budget.amount,
                    current_spend=budget.current_spend,
                    utilization_percentage=budget.utilization_percentage,
                    status=budget.status,
                    time_grain=budget.time_grain,
                    currency=budget.currency,
                    start_date=budget.start_date,
                    end_date=budget.end_date,
                    subscription_id=budget.subscription_id,
                    resource_group=budget.resource_group,
                    alert_count=pending_alerts,
                    last_synced_at=budget.last_synced_at,
                )
            )

        return result

    @cached("budget_detail")
    async def get_budget(self, budget_id: str) -> BudgetResponse | None:
        """Get detailed budget information by ID.

        Args:
            budget_id: Budget UUID

        Returns:
            Budget response or None if not found
        """
        budget = self.db.query(Budget).filter(Budget.id == budget_id).first()
        if not budget:
            return None

        return self._to_budget_response(budget)

    async def create_budget(self, data: BudgetCreate) -> BudgetResponse:
        """Create a new budget locally and in Azure.

        Args:
            data: Budget creation data

        Returns:
            Created budget response

        Raises:
            BudgetServiceError: If creation fails
        """
        # Generate UUID for new budget
        budget_id = str(uuid.uuid4())

        # Create local budget record
        budget = Budget(
            id=budget_id,
            tenant_id=data.tenant_id,
            subscription_id=data.subscription_id,
            resource_group=data.resource_group,
            name=data.name,
            amount=data.amount,
            time_grain=data.time_grain,
            category=data.category,
            start_date=data.start_date,
            end_date=data.end_date,
            currency=data.currency,
            current_spend=0.0,
            status=BudgetStatus.ACTIVE,
            utilization_percentage=0.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db.add(budget)

        # Create thresholds if provided
        for threshold_config in data.thresholds:
            threshold = BudgetThreshold(
                budget_id=budget_id,
                percentage=threshold_config.percentage,
                alert_type=threshold_config.alert_type,
                contact_emails=json.dumps(threshold_config.contact_emails)
                if threshold_config.contact_emails
                else None,
                contact_roles=json.dumps(threshold_config.contact_roles)
                if threshold_config.contact_roles
                else None,
                contact_groups=json.dumps(threshold_config.contact_groups)
                if threshold_config.contact_groups
                else None,
                is_enabled=threshold_config.is_enabled,
                amount=budget.amount * (threshold_config.percentage / 100.0),
            )
            self.db.add(threshold)

        # Create notifications if provided
        for notification_config in data.notifications:
            notification = BudgetNotification(
                budget_id=budget_id,
                notification_type=notification_config.notification_type,
                config=json.dumps(notification_config.config)
                if notification_config.config else None,
                is_enabled=notification_config.is_enabled,
            )
            self.db.add(notification)

        try:
            self.db.commit()
            self.db.refresh(budget)

            # Try to create in Azure (best effort - don't fail if Azure creation fails)
            try:
                await self._create_budget_in_azure(budget)
            except Exception as e:
                logger.warning(
                    f"Failed to create budget in Azure: {e}. Budget created locally only."
                )

            return self._to_budget_response(budget)

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create budget: {e}")
            raise BudgetServiceError(f"Failed to create budget: {e}") from e

    async def update_budget(self, budget_id: str, data: BudgetUpdate) -> BudgetResponse | None:
        """Update an existing budget.

        Args:
            budget_id: Budget UUID
            data: Update data

        Returns:
            Updated budget response or None if not found
        """
        budget = self.db.query(Budget).filter(Budget.id == budget_id).first()
        if not budget:
            return None

        # Update fields
        update_fields = data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            if hasattr(budget, field):
                setattr(budget, field, value)

        budget.updated_at = datetime.utcnow()

        # Recalculate utilization if amount changed
        if "amount" in update_fields and budget.amount > 0:
            budget.utilization_percentage = (budget.current_spend / budget.amount) * 100
            budget.update_status()

        try:
            self.db.commit()
            self.db.refresh(budget)

            # Try to update in Azure
            try:
                await self._update_budget_in_azure(budget)
            except Exception as e:
                logger.warning(f"Failed to update budget in Azure: {e}")

            # Invalidate cache
            await invalidate_on_sync_completion(budget.tenant_id)

            return self._to_budget_response(budget)

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update budget: {e}")
            raise BudgetServiceError(f"Failed to update budget: {e}") from e

    async def delete_budget(self, budget_id: str) -> bool:
        """Delete a budget.

        Args:
            budget_id: Budget UUID

        Returns:
            True if deleted, False if not found
        """
        budget = self.db.query(Budget).filter(Budget.id == budget_id).first()
        if not budget:
            return False

        tenant_id = budget.tenant_id

        try:
            # Try to delete from Azure first
            try:
                await self._delete_budget_from_azure(budget)
            except Exception as e:
                logger.warning(f"Failed to delete budget from Azure: {e}")

            self.db.delete(budget)
            self.db.commit()

            # Invalidate cache
            await invalidate_on_sync_completion(tenant_id)

            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete budget: {e}")
            raise BudgetServiceError(f"Failed to delete budget: {e}") from e

    # =========================================================================
    # Budget Alerts
    # =========================================================================

    async def get_budget_alerts(
        self,
        budget_id: str | None = None,
        tenant_ids: list[str] | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BudgetAlertResponse]:
        """Get budget alerts with optional filtering.

        Args:
            budget_id: Filter by specific budget
            tenant_ids: Filter by tenant IDs
            status: Filter by alert status
            limit: Maximum results to return
            offset: Pagination offset

        Returns:
            List of budget alerts
        """
        query = self.db.query(BudgetAlert)

        if budget_id:
            query = query.filter(BudgetAlert.budget_id == budget_id)
        if tenant_ids:
            # Join with budget to filter by tenant
            query = query.join(Budget).filter(Budget.tenant_id.in_(tenant_ids))
        if status:
            query = query.filter(BudgetAlert.status == status)

        alerts = query.order_by(BudgetAlert.triggered_at.desc()).offset(offset).limit(limit).all()

        return [self._to_alert_response(alert) for alert in alerts]

    async def acknowledge_alert(
        self, alert_id: int, user_id: str, note: str | None = None
    ) -> bool:
        """Acknowledge a budget alert.

        Args:
            alert_id: Alert ID
            user_id: User acknowledging the alert
            note: Optional resolution note

        Returns:
            True if acknowledged, False if not found
        """
        alert = self.db.query(BudgetAlert).filter(BudgetAlert.id == alert_id).first()
        if not alert:
            return False

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = user_id
        alert.acknowledged_at = datetime.utcnow()
        if note:
            alert.resolution_note = note

        try:
            self.db.commit()

            # Invalidate cache
            await invalidate_on_sync_completion(alert.budget.tenant_id)

            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to acknowledge alert: {e}")
            return False

    async def bulk_acknowledge_alerts(
        self, alert_ids: list[int], user_id: str, note: str | None = None
    ) -> BudgetAlertBulkResponse:
        """Acknowledge multiple budget alerts at once.

        Args:
            alert_ids: List of alert IDs
            user_id: User acknowledging
            note: Optional resolution note

        Returns:
            Bulk acknowledge response
        """
        acknowledged_count = 0
        failed_ids = []

        for alert_id in alert_ids:
            success = await self.acknowledge_alert(alert_id, user_id, note)
            if success:
                acknowledged_count += 1
            else:
                failed_ids.append(alert_id)

        return BudgetAlertBulkResponse(
            success=len(failed_ids) == 0,
            acknowledged_count=acknowledged_count,
            failed_ids=failed_ids,
            acknowledged_at=datetime.utcnow(),
        )

    # =========================================================================
    # Budget Summary
    # =========================================================================

    @cached("budget_summary")
    async def get_budget_summary(self, tenant_ids: list[str] | None = None) -> BudgetSummary:
        """Get aggregated budget summary.

        Args:
            tenant_ids: Filter by tenant IDs

        Returns:
            Budget summary
        """
        query = self.db.query(Budget)
        if tenant_ids:
            query = query.filter(Budget.tenant_id.in_(tenant_ids))

        budgets = query.all()

        total_amount = sum(b.amount for b in budgets)
        total_spend = sum(b.current_spend for b in budgets)
        overall_utilization = (total_spend / total_amount * 100) if total_amount > 0 else 0

        # Count by status
        status_counts = {"active": 0, "warning": 0, "critical": 0, "exceeded": 0}
        for budget in budgets:
            status_counts[budget.status] = status_counts.get(budget.status, 0) + 1

        # Count alerts
        alert_query = self.db.query(BudgetAlert).join(Budget)
        if tenant_ids:
            alert_query = alert_query.filter(Budget.tenant_id.in_(tenant_ids))

        pending_alerts = alert_query.filter(BudgetAlert.status == AlertStatus.PENDING).count()
        acknowledged_alerts = alert_query.filter(
            BudgetAlert.status == AlertStatus.ACKNOWLEDGED
        ).count()

        # Per-tenant breakdown
        by_tenant = []
        tenant_ids_found = {b.tenant_id for b in budgets}
        tenants = self.db.query(Tenant).filter(Tenant.id.in_(tenant_ids_found)).all()
        tenant_names = {t.id: t.name for t in tenants}

        for tenant_id in tenant_ids_found:
            tenant_budgets = [b for b in budgets if b.tenant_id == tenant_id]
            tenant_amount = sum(b.amount for b in tenant_budgets)
            tenant_spend = sum(b.current_spend for b in tenant_budgets)
            tenant_utilization = (tenant_spend / tenant_amount * 100) if tenant_amount > 0 else 0

            by_tenant.append(
                {
                    "tenant_id": tenant_id,
                    "tenant_name": tenant_names.get(tenant_id, "Unknown"),
                    "budget_count": len(tenant_budgets),
                    "total_amount": tenant_amount,
                    "total_spend": tenant_spend,
                    "utilization_percentage": tenant_utilization,
                }
            )

        return BudgetSummary(
            total_budgets=len(budgets),
            total_budget_amount=total_amount,
            total_current_spend=total_spend,
            overall_utilization=overall_utilization,
            active_count=status_counts.get("active", 0),
            warning_count=status_counts.get("warning", 0),
            critical_count=status_counts.get("critical", 0),
            exceeded_count=status_counts.get("exceeded", 0),
            pending_alerts=pending_alerts,
            acknowledged_alerts=acknowledged_alerts,
            by_tenant=by_tenant,
        )

    # =========================================================================
    # Azure Sync Operations
    # =========================================================================

    @circuit_breaker(BUDGET_SYNC_BREAKER)
    @retry_with_backoff(BUDGET_SYNC_POLICY)
    async def sync_budgets_from_azure(
        self, tenant_id: str, subscription_ids: list[str] | None = None
    ) -> BudgetSyncResultResponse:
        """Sync budgets from Azure Cost Management API.

        Args:
            tenant_id: Tenant ID to sync
            subscription_ids: Specific subscriptions (None for all)

        Returns:
            Sync result
        """
        sync_result = BudgetSyncResult(
            tenant_id=tenant_id,
            sync_type="incremental",
            status="running",
            started_at=datetime.utcnow(),
        )
        self.db.add(sync_result)
        self.db.commit()

        try:
            # Get subscriptions to sync
            if subscription_ids:
                subscriptions = [
                    {"subscription_id": sub_id} for sub_id in subscription_ids
                ]
            else:
                subscriptions = await azure_client_manager.list_subscriptions(tenant_id)

            total_synced = 0
            total_created = 0
            total_updated = 0
            total_errors = 0

            for sub in subscriptions:
                sub_id = sub["subscription_id"]

                try:
                    azure_budgets = await self._fetch_budgets_from_azure(tenant_id, sub_id)

                    for azure_budget in azure_budgets:
                        try:
                            result = await self._sync_single_budget(
                                tenant_id, sub_id, azure_budget
                            )
                            if result == "created":
                                total_created += 1
                            elif result == "updated":
                                total_updated += 1
                            total_synced += 1
                        except Exception as e:
                            logger.error(f"Failed to sync budget: {e}")
                            total_errors += 1

                except Exception as e:
                    logger.error(f"Failed to fetch budgets for subscription {sub_id}: {e}")
                    total_errors += 1

            # Update sync result
            sync_result.status = "completed" if total_errors == 0 else "partial"
            sync_result.budgets_synced = total_synced
            sync_result.budgets_created = total_created
            sync_result.budgets_updated = total_updated
            sync_result.errors_count = total_errors
            sync_result.complete(sync_result.status)

            self.db.commit()

            # Check for threshold breaches
            await self._check_budget_thresholds(tenant_id)

            # Invalidate cache
            await invalidate_on_sync_completion(tenant_id)

            return self._to_sync_result_response(sync_result)

        except Exception as e:
            sync_result.status = "failed"
            sync_result.error_message = str(e)[:1000]
            sync_result.complete("failed")
            self.db.commit()
            logger.error(f"Budget sync failed for tenant {tenant_id}: {e}")
            raise BudgetServiceError(f"Sync failed: {e}") from e

    async def _fetch_budgets_from_azure(
        self, tenant_id: str, subscription_id: str
    ) -> list[dict[str, Any]]:
        """Fetch budgets from Azure Cost Management API.

        Args:
            tenant_id: Azure tenant ID
            subscription_id: Azure subscription ID

        Returns:
            List of budget dictionaries from Azure
        """
        credential = azure_client_manager.get_credential(tenant_id)
        token = credential.get_token("https://management.azure.com/.default")

        url = (
            f"https://management.azure.com/subscriptions/{subscription_id}"
            f"/providers/Microsoft.Consumption/budgets"
            f"?api-version={BUDGET_API_VERSION}"
        )

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {token.token}"},
            )
            resp.raise_for_status()

        data = resp.json()
        return data.get("value", [])

    async def _sync_single_budget(
        self, tenant_id: str, subscription_id: str, azure_budget: dict[str, Any]
    ) -> str:
        """Sync a single budget from Azure.

        Args:
            tenant_id: Tenant ID
            subscription_id: Subscription ID
            azure_budget: Budget data from Azure API

        Returns:
            "created", "updated", or "unchanged"
        """
        properties = azure_budget.get("properties", {})
        azure_id = azure_budget.get("id", "")
        name = azure_budget.get("name", "")
        etag = azure_budget.get("etag", "")

        # Check if budget exists locally
        existing = (
            self.db.query(Budget)
            .filter(Budget.azure_budget_id == azure_id)
            .first()
        )

        # Extract budget details
        amount = properties.get("amount", 0)
        time_grain = properties.get("timeGrain", "Monthly")
        category = properties.get("category", "Cost")

        time_period = properties.get("timePeriod", {})
        start_date = datetime.strptime(
            time_period.get("startDate", "2024-01-01"), "%Y-%m-%d"
        ).date()
        end_date_str = time_period.get("endDate")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else None

        # Current spend
        current_spend = properties.get("currentSpend", {}).get("amount", 0)
        forecasted_spend = properties.get("forecast", {}).get("amount")
        currency = properties.get("currentSpend", {}).get("unit", "USD")

        # Calculate utilization
        utilization = (float(current_spend) / float(amount) * 100) if amount > 0 else 0

        if existing:
            # Update existing
            existing.name = name
            existing.amount = float(amount)
            existing.time_grain = time_grain
            existing.category = category
            existing.start_date = start_date
            existing.end_date = end_date
            existing.current_spend = float(current_spend)
            existing.forecasted_spend = float(forecasted_spend) if forecasted_spend else None
            existing.currency = currency
            existing.utilization_percentage = utilization
            existing.etag = etag
            existing.last_synced_at = datetime.utcnow()
            existing.update_status()

            result = "updated"
        else:
            # Create new
            budget = Budget(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                name=name,
                amount=float(amount),
                time_grain=time_grain,
                category=category,
                start_date=start_date,
                end_date=end_date,
                current_spend=float(current_spend),
                forecasted_spend=float(forecasted_spend) if forecasted_spend else None,
                currency=currency,
                utilization_percentage=utilization,
                azure_budget_id=azure_id,
                etag=etag,
                last_synced_at=datetime.utcnow(),
            )
            budget.update_status()
            self.db.add(budget)

            # Sync notification thresholds
            notifications = properties.get("notifications", {})
            for _notif_name, notif_config in notifications.items():
                threshold = BudgetThreshold(
                    budget_id=budget.id,
                    percentage=float(notif_config.get("threshold", 100)),
                    alert_type=notif_config.get("operator", "GreaterThan"),
                    contact_emails=json.dumps(notif_config.get("contactEmails", [])),
                    contact_roles=json.dumps(notif_config.get("contactRoles", [])),
                    contact_groups=json.dumps(notif_config.get("contactGroups", [])),
                    is_enabled=notif_config.get("enabled", True),
                )
                self.db.add(threshold)

            result = "created"

        self.db.commit()
        return result

    async def _check_budget_thresholds(self, tenant_id: str) -> int:
        """Check all budget thresholds and create alerts for breaches.

        Args:
            tenant_id: Tenant to check

        Returns:
            Number of alerts triggered
        """
        budgets = self.db.query(Budget).filter(Budget.tenant_id == tenant_id).all()
        alerts_triggered = 0

        for budget in budgets:
            for threshold in budget.thresholds:
                if not threshold.is_enabled:
                    continue

                threshold_amount = threshold.calculate_amount(budget.amount)

                # Check if threshold is breached
                if budget.current_spend >= threshold_amount:
                    # Check if alert already exists for this threshold
                    existing_alert = (
                        self.db.query(BudgetAlert)
                        .filter(
                            BudgetAlert.budget_id == budget.id,
                            BudgetAlert.threshold_id == threshold.id,
                            BudgetAlert.status.in_([AlertStatus.PENDING, AlertStatus.ACKNOWLEDGED]),
                        )
                        .first()
                    )

                    if not existing_alert:
                        # Create new alert
                        alert = BudgetAlert(
                            budget_id=budget.id,
                            threshold_id=threshold.id,
                            alert_type=self._map_alert_type(threshold.alert_type),
                            threshold_percentage=threshold.percentage,
                            threshold_amount=threshold_amount,
                            current_spend=budget.current_spend,
                            forecasted_spend=budget.forecasted_spend,
                            utilization_percentage=budget.utilization_percentage,
                        )
                        self.db.add(alert)
                        alerts_triggered += 1

                        # Update threshold trigger count
                        threshold.trigger_count += 1
                        threshold.last_triggered_at = datetime.utcnow()

        self.db.commit()
        return alerts_triggered

    def _map_alert_type(self, azure_operator: str) -> str:
        """Map Azure alert operator to our alert type."""
        operator_map = {
            "GreaterThan": AlertType.WARNING,
            "GreaterThanOrEqualTo": AlertType.WARNING,
            "LessThan": AlertType.FORECASTED,
        }
        return operator_map.get(azure_operator, AlertType.WARNING)

    # =========================================================================
    # Azure CRUD Operations (Best Effort)
    # =========================================================================

    async def _create_budget_in_azure(self, budget: Budget) -> None:
        """Create budget in Azure Cost Management.

        Args:
            budget: Local budget to create in Azure
        """
        # Get thresholds
        thresholds = (
            self.db.query(BudgetThreshold).filter(BudgetThreshold.budget_id == budget.id).all()
        )

        # Build notifications
        notifications = {}
        for i, threshold in enumerate(thresholds):
            notif_name = f"Notification{i + 1}"
            notifications[notif_name] = {
                "enabled": threshold.is_enabled,
                "operator": "GreaterThan",
                "threshold": threshold.percentage,
                "contactEmails": json.loads(threshold.contact_emails or "[]"),
                "contactRoles": json.loads(threshold.contact_roles or "[]"),
                "contactGroups": json.loads(threshold.contact_groups or "[]"),
            }

        body = {
            "properties": {
                "category": budget.category,
                "amount": budget.amount,
                "timeGrain": budget.time_grain,
                "timePeriod": {
                    "startDate": budget.start_date.isoformat(),
                    "endDate": budget.end_date.isoformat() if budget.end_date else None,
                },
                "notifications": notifications,
            }
        }

        # Remove None values
        if not body["properties"]["timePeriod"]["endDate"]:
            del body["properties"]["timePeriod"]["endDate"]

        credential = azure_client_manager.get_credential(budget.tenant_id)
        token = credential.get_token("https://management.azure.com/.default")

        url = (
            f"https://management.azure.com/subscriptions/{budget.subscription_id}"
            f"/providers/Microsoft.Consumption/budgets/{budget.name}"
            f"?api-version={BUDGET_API_VERSION}"
        )

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.put(
                url,
                json=body,
                headers={"Authorization": f"Bearer {token.token}"},
            )
            resp.raise_for_status()

            # Update local budget with Azure ID
            data = resp.json()
            budget.azure_budget_id = data.get("id")
            budget.etag = data.get("etag")
            self.db.commit()

    async def _update_budget_in_azure(self, budget: Budget) -> None:
        """Update budget in Azure Cost Management."""
        if not budget.azure_budget_id:
            # Create instead
            await self._create_budget_in_azure(budget)
            return

        # Similar to create but with PATCH semantics
        body = {
            "properties": {
                "amount": budget.amount,
                "timePeriod": {
                    "startDate": budget.start_date.isoformat(),
                    "endDate": budget.end_date.isoformat() if budget.end_date else None,
                },
            }
        }

        if not body["properties"]["timePeriod"].get("endDate"):
            del body["properties"]["timePeriod"]["endDate"]

        credential = azure_client_manager.get_credential(budget.tenant_id)
        token = credential.get_token("https://management.azure.com/.default")

        url = (
            f"https://management.azure.com{budget.azure_budget_id}"
            f"?api-version={BUDGET_API_VERSION}"
        )

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(
                url,
                json=body,
                headers={
                    "Authorization": f"Bearer {token.token}",
                    "If-Match": budget.etag or "*",
                },
            )
            resp.raise_for_status()

            # Update ETag
            data = resp.json()
            budget.etag = data.get("etag")
            self.db.commit()

    async def _delete_budget_from_azure(self, budget: Budget) -> None:
        """Delete budget from Azure Cost Management."""
        if not budget.azure_budget_id:
            return

        credential = azure_client_manager.get_credential(budget.tenant_id)
        token = credential.get_token("https://management.azure.com/.default")

        url = (
            f"https://management.azure.com{budget.azure_budget_id}"
            f"?api-version={BUDGET_API_VERSION}"
        )

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(
                url,
                headers={"Authorization": f"Bearer {token.token}"},
            )
            resp.raise_for_status()

    # =========================================================================
    # Conversion Helpers
    # =========================================================================

    def _to_budget_response(self, budget: Budget) -> BudgetResponse:
        """Convert Budget model to BudgetResponse schema."""
        # Get thresholds (handle lazy loading)
        try:
            thresholds = [
                BudgetThresholdResponse(
                    id=t.id,
                    budget_id=t.budget_id,
                    percentage=t.percentage,
                    amount=t.amount,
                    alert_type=t.alert_type,
                    contact_emails=t.contact_emails,
                    contact_roles=t.contact_roles,
                    contact_groups=t.contact_groups,
                    is_enabled=t.is_enabled,
                    trigger_count=t.trigger_count,
                    last_triggered_at=t.last_triggered_at,
                    created_at=t.created_at,
                    updated_at=t.updated_at,
                )
                for t in budget.thresholds
            ]
        except Exception:
            thresholds = []

        # Get recent alerts (handle lazy loading)
        try:
            if hasattr(budget.alerts, 'order_by'):
                recent_alerts = [
                    self._to_alert_response(a)
                    for a in budget.alerts.order_by(BudgetAlert.triggered_at.desc()).limit(10).all()
                ]
            else:
                # Fallback for detached instances - query directly
                from sqlalchemy.orm import joinedload
                alerts = (
                    self.db.query(BudgetAlert)
                    .options(joinedload(BudgetAlert.budget))
                    .filter(BudgetAlert.budget_id == budget.id)
                    .order_by(BudgetAlert.triggered_at.desc())
                    .limit(10)
                    .all()
                )
                recent_alerts = [self._to_alert_response(a) for a in alerts]
        except Exception:
            recent_alerts = []

        return BudgetResponse(
            id=budget.id,
            tenant_id=budget.tenant_id,
            subscription_id=budget.subscription_id,
            name=budget.name,
            amount=budget.amount,
            time_grain=budget.time_grain,
            category=budget.category,
            start_date=budget.start_date,
            end_date=budget.end_date,
            resource_group=budget.resource_group,
            currency=budget.currency,
            current_spend=budget.current_spend,
            forecasted_spend=budget.forecasted_spend,
            utilization_percentage=budget.utilization_percentage,
            status=budget.status,
            azure_budget_id=budget.azure_budget_id,
            etag=budget.etag,
            created_at=budget.created_at,
            updated_at=budget.updated_at,
            last_synced_at=budget.last_synced_at,
            thresholds=thresholds,
            recent_alerts=recent_alerts,
            remaining_amount=budget.remaining_amount,
            is_exceeded=budget.is_exceeded,
            days_remaining=budget.days_remaining,
        )

    def _to_alert_response(self, alert: BudgetAlert) -> BudgetAlertResponse:
        """Convert BudgetAlert model to BudgetAlertResponse schema."""
        budget = alert.budget

        return BudgetAlertResponse(
            id=alert.id,
            budget_id=alert.budget_id,
            budget_name=budget.name if budget else None,
            tenant_id=budget.tenant_id if budget else None,
            subscription_id=budget.subscription_id if budget else None,
            threshold_id=alert.threshold_id,
            alert_type=alert.alert_type,
            status=alert.status,
            threshold_percentage=alert.threshold_percentage,
            threshold_amount=alert.threshold_amount,
            current_spend=alert.current_spend,
            forecasted_spend=alert.forecasted_spend,
            utilization_percentage=alert.utilization_percentage,
            triggered_at=alert.triggered_at,
            acknowledged_at=alert.acknowledged_at,
            acknowledged_by=alert.acknowledged_by,
            resolved_at=alert.resolved_at,
            resolution_note=alert.resolution_note,
            notification_sent=alert.notification_sent,
            notification_sent_at=alert.notification_sent_at,
        )

    def _to_sync_result_response(self, result: BudgetSyncResult) -> BudgetSyncResultResponse:
        """Convert BudgetSyncResult model to response schema."""
        return BudgetSyncResultResponse(
            id=result.id,
            tenant_id=result.tenant_id,
            sync_type=result.sync_type,
            status=result.status,
            budgets_synced=result.budgets_synced,
            budgets_created=result.budgets_created,
            budgets_updated=result.budgets_updated,
            budgets_deleted=result.budgets_deleted,
            alerts_triggered=result.alerts_triggered,
            errors_count=result.errors_count,
            error_message=result.error_message,
            error_details=result.error_details,
            started_at=result.started_at,
            completed_at=result.completed_at,
            duration_seconds=result.duration_seconds,
        )
