"""Cost management service with caching support."""

import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.cache import cached, invalidate_on_sync_completion
from app.models.cost import CostAnomaly, CostSnapshot
from app.models.tenant import Tenant
from app.schemas.cost import (
    AnomaliesByService,
    AnomalyTrend,
    BulkAcknowledgeResponse,
    CostByTenant,
    CostForecast,
    CostSummary,
    CostTrend,
    ServiceCost,
    TopAnomaly,
)

if TYPE_CHECKING:
    from app.schemas import cost as cost_schemas

logger = logging.getLogger(__name__)


class CostService:
    """Service for cost management operations."""

    def __init__(self, db: Session):
        self.db = db

    @cached("cost_summary")
    async def get_cost_summary(
        self,
        period_days: int = 30,
        tenant_ids: list[str] | None = None,
    ) -> CostSummary:
        """Get aggregated cost summary across all tenants."""
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)
        prev_start = start_date - timedelta(days=period_days)

        # Current period costs
        query = self.db.query(CostSnapshot).filter(
            CostSnapshot.date >= start_date, CostSnapshot.date <= end_date
        )
        if tenant_ids:
            query = query.filter(CostSnapshot.tenant_id.in_(tenant_ids))
        current_costs = query.all()

        # Previous period costs for comparison
        prev_query = self.db.query(CostSnapshot).filter(
            CostSnapshot.date >= prev_start, CostSnapshot.date < start_date
        )
        if tenant_ids:
            prev_query = prev_query.filter(CostSnapshot.tenant_id.in_(tenant_ids))
        prev_costs = prev_query.all()

        current_total = sum(c.total_cost for c in current_costs)
        prev_total = sum(c.total_cost for c in prev_costs)

        # Calculate change percentage
        change_percent = None
        if prev_total > 0:
            change_percent = ((current_total - prev_total) / prev_total) * 100

        # Get unique counts
        tenant_ids = {c.tenant_id for c in current_costs}
        sub_ids = {c.subscription_id for c in current_costs}

        # Top services by cost
        service_costs = {}
        for cost in current_costs:
            if cost.service_name:
                service_costs[cost.service_name] = (
                    service_costs.get(cost.service_name, 0) + cost.total_cost
                )

        top_services = [
            ServiceCost(
                service_name=name,
                cost=cost,
                percentage_of_total=(cost / current_total * 100) if current_total > 0 else 0,
            )
            for name, cost in sorted(
                service_costs.items(), key=lambda x: x[1], reverse=True
            )[:10]
        ]

        return CostSummary(
            total_cost=current_total,
            currency="USD",
            period_start=start_date,
            period_end=end_date,
            tenant_count=len(tenant_ids),
            subscription_count=len(sub_ids),
            cost_change_percent=change_percent,
            top_services=top_services,
        )

    @cached("cost_by_tenant")
    async def get_costs_by_tenant(self, period_days: int = 30) -> list[CostByTenant]:
        """Get cost breakdown by tenant."""
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)

        tenants = self.db.query(Tenant).filter(Tenant.is_active).all()
        result = []

        for tenant in tenants:
            costs = (
                self.db.query(CostSnapshot)
                .filter(CostSnapshot.tenant_id == tenant.id)
                .filter(CostSnapshot.date >= start_date)
                .filter(CostSnapshot.date <= end_date)
                .all()
            )

            total = sum(c.total_cost for c in costs)

            result.append(
                CostByTenant(
                    tenant_id=tenant.id,
                    tenant_name=tenant.name,
                    total_cost=total,
                    currency="USD",
                )
            )

        return sorted(result, key=lambda x: x.total_cost, reverse=True)

    @cached("cost_trends")
    async def get_cost_trends(
        self, days: int = 30, tenant_ids: list[str] | None = None
    ) -> list[CostTrend]:
        """Get daily cost trends."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Aggregate costs by date
        daily_costs = {}
        query = self.db.query(CostSnapshot).filter(
            CostSnapshot.date >= start_date, CostSnapshot.date <= end_date
        )
        if tenant_ids:
            query = query.filter(CostSnapshot.tenant_id.in_(tenant_ids))
        costs = query.all()

        for cost in costs:
            daily_costs[cost.date] = daily_costs.get(cost.date, 0) + cost.total_cost

        return [
            CostTrend(date=d, cost=c)
            for d, c in sorted(daily_costs.items())
        ]

    def get_anomalies(
        self, acknowledged: bool | None = None
    ) -> list[CostAnomaly]:
        """Get cost anomalies (not cached - real-time data)."""
        query = self.db.query(CostAnomaly)

        if acknowledged is not None:
            query = query.filter(CostAnomaly.is_acknowledged == acknowledged)

        return query.order_by(CostAnomaly.detected_at.desc()).limit(50).all()

    async def acknowledge_anomaly(self, anomaly_id: int, user: str) -> bool:
        """Acknowledge a cost anomaly."""
        from datetime import datetime

        anomaly = self.db.query(CostAnomaly).filter(CostAnomaly.id == anomaly_id).first()
        if not anomaly:
            return False

        anomaly.is_acknowledged = True
        anomaly.acknowledged_by = user
        anomaly.acknowledged_at = datetime.utcnow()
        self.db.commit()

        # Invalidate cache after state change
        await invalidate_on_sync_completion(anomaly.tenant_id)
        return True

    async def bulk_acknowledge_anomalies(
        self, anomaly_ids: list[int], user: str
    ) -> BulkAcknowledgeResponse:
        """Acknowledge multiple cost anomalies."""
        acknowledged_count = 0
        failed_ids = []

        for anomaly_id in anomaly_ids:
            success = await self.acknowledge_anomaly(anomaly_id, user)
            if success:
                acknowledged_count += 1
            else:
                failed_ids.append(anomaly_id)

        return BulkAcknowledgeResponse(
            success=len(failed_ids) == 0,
            acknowledged_count=acknowledged_count,
            failed_ids=failed_ids,
            acknowledged_at=datetime.utcnow(),
        )

    @cached("cost_anomaly_trends")
    async def get_anomaly_trends(
        self, months: int = 6, tenant_ids: list[str] | None = None
    ) -> list[AnomalyTrend]:
        """Get anomaly trends over time grouped by month."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30 * months)

        query = self.db.query(CostAnomaly).filter(
            CostAnomaly.detected_at >= start_date, CostAnomaly.detected_at <= end_date
        )
        if tenant_ids:
            query = query.filter(CostAnomaly.tenant_id.in_(tenant_ids))
        anomalies = query.all()

        # Group by month
        by_month: dict[str, dict[str, Any]] = {}
        for anomaly in anomalies:
            month_key = anomaly.detected_at.strftime("%Y-%m")
            if month_key not in by_month:
                by_month[month_key] = {
                    "count": 0,
                    "impact": 0.0,
                    "acknowledged": 0,
                    "unacknowledged": 0,
                }

            by_month[month_key]["count"] += 1
            impact = abs((anomaly.actual_cost or 0) - (anomaly.expected_cost or 0))
            by_month[month_key]["impact"] += impact

            if anomaly.is_acknowledged:
                by_month[month_key]["acknowledged"] += 1
            else:
                by_month[month_key]["unacknowledged"] += 1

        return [
            AnomalyTrend(
                period=month,
                anomaly_count=data["count"],
                total_impact=data["impact"],
                acknowledged_count=data["acknowledged"],
                unacknowledged_count=data["unacknowledged"],
            )
            for month, data in sorted(by_month.items())
        ]

    @cached("cost_anomalies_by_service")
    async def get_anomalies_by_service(
        self, limit: int = 20, tenant_ids: list[str] | None = None
    ) -> list[AnomaliesByService]:
        """Get anomalies grouped by service."""
        query = self.db.query(CostAnomaly)
        if tenant_ids:
            query = query.filter(CostAnomaly.tenant_id.in_(tenant_ids))
        anomalies = query.all()

        # Group by service
        by_service: dict[str, dict[str, Any]] = {}
        for anomaly in anomalies:
            service_name = anomaly.service_name or "Unknown"
            if service_name not in by_service:
                by_service[service_name] = {
                    "count": 0,
                    "total_impact": 0.0,
                    "percentage_changes": [],
                    "latest_at": anomaly.detected_at,
                }

            by_service[service_name]["count"] += 1
            impact = abs((anomaly.actual_cost or 0) - (anomaly.expected_cost or 0))
            by_service[service_name]["total_impact"] += impact
            by_service[service_name]["percentage_changes"].append(
                anomaly.percentage_change or 0
            )

            if anomaly.detected_at > by_service[service_name]["latest_at"]:
                by_service[service_name]["latest_at"] = anomaly.detected_at

        # Calculate averages and create result
        result = []
        for service_name, data in by_service.items():
            avg_change = (
                sum(data["percentage_changes"]) / len(data["percentage_changes"])
                if data["percentage_changes"]
                else 0
            )
            result.append(
                AnomaliesByService(
                    service_name=service_name,
                    anomaly_count=data["count"],
                    total_impact=data["total_impact"],
                    avg_percentage_change=avg_change,
                    latest_anomaly_at=data["latest_at"],
                )
            )

        # Sort by total impact and limit
        return sorted(result, key=lambda x: x.total_impact, reverse=True)[:limit]

    def get_top_anomalies(
        self, n: int = 10, acknowledged: bool | None = None
    ) -> list[TopAnomaly]:
        """Get top N anomalies by impact (not cached - real-time)."""
        query = self.db.query(CostAnomaly)

        if acknowledged is not None:
            query = query.filter(CostAnomaly.is_acknowledged == acknowledged)

        anomalies = query.order_by(CostAnomaly.detected_at.desc()).limit(100).all()

        # Get tenant names for display
        tenant_names = {t.id: t.name for t in self.db.query(Tenant).all()}

        # Calculate impact score and sort
        scored_anomalies = []
        for anomaly in anomalies:
            impact = abs((anomaly.actual_cost or 0) - (anomaly.expected_cost or 0))
            percentage_factor = abs(anomaly.percentage_change or 0) / 100
            impact_score = impact * (1 + percentage_factor)

            scored_anomalies.append(
                (
                    anomaly,
                    impact_score,
                )
            )

        # Sort by impact score and take top N
        scored_anomalies.sort(key=lambda x: x[1], reverse=True)
        top_n = scored_anomalies[:n]

        return [
            TopAnomaly(
                anomaly=self._to_anomaly_schema(anomaly, tenant_names),
                impact_score=score,
            )
            for anomaly, score in top_n
        ]

    def _to_anomaly_schema(
        self, anomaly: CostAnomaly, tenant_names: dict[str, str]
    ) -> "cost_schemas.CostAnomaly":
        """Convert database anomaly to schema."""
        from app.schemas import cost as schemas

        return schemas.CostAnomaly(
            id=anomaly.id,
            tenant_id=anomaly.tenant_id,
            tenant_name=tenant_names.get(anomaly.tenant_id, "Unknown"),
            subscription_id=anomaly.subscription_id,
            detected_at=anomaly.detected_at,
            anomaly_type=anomaly.anomaly_type,
            description=anomaly.description,
            expected_cost=anomaly.expected_cost or 0,
            actual_cost=anomaly.actual_cost or 0,
            percentage_change=anomaly.percentage_change or 0,
            service_name=anomaly.service_name,
            is_acknowledged=bool(anomaly.is_acknowledged),
            acknowledged_by=anomaly.acknowledged_by,
            acknowledged_at=anomaly.acknowledged_at,
        )

    @cached("cost_forecast")
    async def get_cost_forecast(
        self, days: int = 30, tenant_ids: list[str] | None = None
    ) -> list[CostForecast]:
        """Generate cost forecast using simple linear projection."""
        # Get last 90 days of historical data for trend calculation
        end_date = date.today()
        start_date = end_date - timedelta(days=90)

        query = (
            self.db.query(CostSnapshot.date, func.sum(CostSnapshot.total_cost).label("daily_cost"))
            .filter(CostSnapshot.date >= start_date, CostSnapshot.date <= end_date)
        )
        if tenant_ids:
            query = query.filter(CostSnapshot.tenant_id.in_(tenant_ids))
        historical_costs = query.group_by(CostSnapshot.date).order_by(CostSnapshot.date).all()

        if len(historical_costs) < 7:
            # Not enough data, return empty
            return []

        # Calculate simple linear trend
        costs = [c.daily_cost for c in historical_costs]
        n = len(costs)
        x_mean = (n - 1) / 2
        y_mean = sum(costs) / n

        # Calculate slope (m) using least squares
        numerator = sum((i - x_mean) * (costs[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator != 0 else 0

        # Calculate standard deviation for confidence intervals
        variance = sum((c - y_mean) ** 2 for c in costs) / n
        std_dev = variance ** 0.5

        # Generate forecast
        last_value = costs[-1]
        forecasts = []

        for i in range(1, days + 1):
            forecast_date = end_date + timedelta(days=i)
            forecasted_cost = last_value + (slope * i)

            # Simple confidence interval (±1 standard deviation)
            confidence_lower = max(0, forecasted_cost - std_dev)
            confidence_upper = forecasted_cost + std_dev

            forecasts.append(
                CostForecast(
                    date=forecast_date,
                    forecasted_cost=round(forecasted_cost, 2),
                    confidence_lower=round(confidence_lower, 2),
                    confidence_upper=round(confidence_upper, 2),
                )
            )

        return forecasts
