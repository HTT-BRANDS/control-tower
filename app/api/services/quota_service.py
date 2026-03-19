"""Quota utilization service — monitors Azure subscription quota usage (RM-007).

Fetches compute, network, and storage quota data from the Azure Resource Manager
Usage API using the existing LighthouseAzureClient credential infrastructure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Module-level lazy imports — None when SDK not installed.
# Defined at module scope so tests can patch them via
# app.api.services.quota_service.ComputeManagementClient.
try:
    from azure.mgmt.compute import ComputeManagementClient
except ImportError:
    ComputeManagementClient = None  # type: ignore[assignment,misc]

try:
    from azure.mgmt.network import NetworkManagementClient
except ImportError:
    NetworkManagementClient = None  # type: ignore[assignment,misc]

# Azure resource providers and their quota-bearing resource types
QUOTA_PROVIDERS = {
    "compute": "Microsoft.Compute",
    "network": "Microsoft.Network",
    "storage": "Microsoft.Storage",
}

# Utilization threshold percentages
THRESHOLD_WARNING = 75.0
THRESHOLD_CRITICAL = 90.0


@dataclass
class QuotaItem:
    """A single quota metric for a subscription."""

    name: str
    current_value: int
    limit: int
    unit: str = "Count"
    provider: str = ""
    location: str = ""

    @property
    def utilization_pct(self) -> float:
        """Percentage of quota consumed."""
        if self.limit == 0:
            return 0.0
        return round((self.current_value / self.limit) * 100, 1)

    @property
    def status(self) -> str:
        """Health status: ok | warning | critical."""
        pct = self.utilization_pct
        if pct >= THRESHOLD_CRITICAL:
            return "critical"
        if pct >= THRESHOLD_WARNING:
            return "warning"
        return "ok"

    @property
    def available(self) -> int:
        return max(0, self.limit - self.current_value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "current_value": self.current_value,
            "limit": self.limit,
            "available": self.available,
            "utilization_pct": self.utilization_pct,
            "unit": self.unit,
            "provider": self.provider,
            "location": self.location,
            "status": self.status,
        }


@dataclass
class QuotaSummary:
    """Aggregated quota health for a subscription."""

    subscription_id: str
    tenant_id: str
    location: str
    quotas: list[QuotaItem] = field(default_factory=list)
    error: str | None = None

    @property
    def critical_count(self) -> int:
        return sum(1 for q in self.quotas if q.status == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for q in self.quotas if q.status == "warning")

    @property
    def overall_status(self) -> str:
        if self.error:
            return "error"
        if self.critical_count > 0:
            return "critical"
        if self.warning_count > 0:
            return "warning"
        return "ok"

    def to_dict(self) -> dict[str, Any]:
        return {
            "subscription_id": self.subscription_id,
            "tenant_id": self.tenant_id,
            "location": self.location,
            "overall_status": self.overall_status,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "total_quotas": len(self.quotas),
            "quotas": [q.to_dict() for q in self.quotas],
            "error": self.error,
        }


class QuotaService:
    """Fetches and aggregates Azure quota utilization data.

    Uses the Azure Compute Usage API (via azure-mgmt-compute) to get
    per-subscription quota data. Falls back gracefully on permission errors.
    """

    def __init__(self, credential: Any) -> None:
        self.credential = credential

    def get_compute_quotas(
        self, subscription_id: str, tenant_id: str, location: str = "eastus"
    ) -> QuotaSummary:
        """Fetch compute quota utilization for a subscription.

        Calls Azure Compute Usage API:
        GET /subscriptions/{sub}/providers/Microsoft.Compute/locations/{loc}/usages
        """
        summary = QuotaSummary(
            subscription_id=subscription_id,
            tenant_id=tenant_id,
            location=location,
        )
        if ComputeManagementClient is None:
            summary.error = "azure-mgmt-compute not installed"
            logger.warning("azure-mgmt-compute not available for quota check")
            return summary
        try:
            client = ComputeManagementClient(self.credential, subscription_id)
            usages = client.usage.list(location)
            for usage in usages:
                if usage.current_value is not None and usage.limit is not None:
                    item = QuotaItem(
                        name=usage.name.localized_value or usage.name.value,
                        current_value=usage.current_value,
                        limit=usage.limit,
                        unit=usage.unit or "Count",
                        provider="compute",
                        location=location,
                    )
                    summary.quotas.append(item)
        except Exception as exc:
            summary.error = str(exc)
            logger.warning("Quota fetch failed for sub %s: %s", subscription_id, exc)
        return summary

    def get_network_quotas(
        self, subscription_id: str, tenant_id: str, location: str = "eastus"
    ) -> QuotaSummary:
        """Fetch network quota utilization for a subscription."""
        summary = QuotaSummary(
            subscription_id=subscription_id,
            tenant_id=tenant_id,
            location=location,
        )
        if NetworkManagementClient is None:
            summary.error = "azure-mgmt-network not installed"
            logger.warning("azure-mgmt-network not available for quota check")
            return summary
        try:
            client = NetworkManagementClient(self.credential, subscription_id)
            usages = client.usages.list(location)
            for usage in usages:
                if usage.current_value is not None and usage.limit is not None:
                    item = QuotaItem(
                        name=usage.name.localized_value or usage.name.value,
                        current_value=usage.current_value,
                        limit=usage.limit,
                        unit="Count",
                        provider="network",
                        location=location,
                    )
                    summary.quotas.append(item)
        except Exception as exc:
            summary.error = str(exc)
            logger.warning("Network quota fetch failed for sub %s: %s", subscription_id, exc)
        return summary

    def aggregate_quotas(self, summaries: list[QuotaSummary]) -> dict[str, Any]:
        """Merge multiple subscription quota summaries into a cross-tenant view."""
        all_quotas = []
        critical_subs = []
        warning_subs = []

        for summary in summaries:
            if summary.overall_status == "critical":
                critical_subs.append(summary.subscription_id)
            elif summary.overall_status == "warning":
                warning_subs.append(summary.subscription_id)
            all_quotas.extend(summary.quotas)

        # Sort by utilization descending to surface highest risk first
        all_quotas.sort(key=lambda q: q.utilization_pct, reverse=True)

        overall = "ok"
        if critical_subs:
            overall = "critical"
        elif warning_subs:
            overall = "warning"

        return {
            "overall_status": overall,
            "subscriptions_checked": len(summaries),
            "critical_subscriptions": critical_subs,
            "warning_subscriptions": warning_subs,
            "top_quotas_by_utilization": [q.to_dict() for q in all_quotas[:20]],
            "total_quota_metrics": len(all_quotas),
        }
