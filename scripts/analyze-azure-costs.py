#!/usr/bin/env python3
"""Analyze Azure costs with tenant tracking and optimization recommendations.

This script provides comprehensive cost analysis:
- Resource costs tracked by tenant/resource group
- Idle resource identification (unused VMs, disks, IPs)
- Cost trend analysis and forecasting
- Automated cost alerts based on thresholds
- Cost allocation reports for finance teams
- CSV export for external analysis

Usage:
    # Analyze costs for current month
    python scripts/analyze-azure-costs.py --subscription $AZURE_SUBSCRIPTION_ID

    # Analyze with tenant breakdown
    python scripts/analyze-azure-costs.py --subscription $SUB_ID --by-tenant

    # Find idle resources
    python scripts/analyze-azure-costs.py --subscription $SUB_ID --find-idle

    # Generate cost alerts
    python scripts/analyze-azure-costs.py --subscription $SUB_ID --alert-threshold 1000

    # Export to CSV
    python scripts/analyze-azure-costs.py --subscription $SUB_ID --export-csv costs.csv

    # Historical analysis (last 90 days)
    python scripts/analyze-azure-costs.py --subscription $SUB_ID --days 90

Environment Variables:
    AZURE_SUBSCRIPTION_ID: Azure subscription ID
    AZURE_TENANT_ID: Azure AD tenant ID
    TEAMS_WEBHOOK_URL: Teams webhook for alerts
    SLACK_WEBHOOK_URL: Slack webhook for alerts
"""

import argparse
import csv
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class CostBreakdown:
    """Cost breakdown by category."""

    service_name: str
    resource_group: str
    resource_id: str | None = None
    cost_usd: Decimal = Decimal("0")
    usage_quantity: Decimal = Decimal("0")
    usage_unit: str = ""
    tags: dict[str, str] = field(default_factory=dict)
    tenant_id: str | None = None

    @property
    def tenant_name(self) -> str:
        """Get tenant name from tags or resource group."""
        return self.tags.get("tenant", self.tags.get("Tenant", self.resource_group))


@dataclass
class IdleResource:
    """Information about an idle resource."""

    resource_type: str
    resource_name: str
    resource_id: str
    resource_group: str
    last_used_days: int
    monthly_cost: Decimal
    reason: str
    recommendation: str
    tags: dict[str, str] = field(default_factory=dict)

    @property
    def potential_savings_annual(self) -> Decimal:
        """Calculate potential annual savings."""
        return self.monthly_cost * 12


@dataclass
class CostAlert:
    """Cost alert information."""

    alert_type: str  # "threshold", "anomaly", "idle_resource"
    severity: str  # "info", "warning", "critical"
    message: str
    current_cost: Decimal
    threshold: Decimal | None = None
    resource_id: str | None = None
    recommendation: str = ""


class AzureCostAnalyzer:
    """Azure cost analysis and optimization tool."""

    # Resource types that commonly become idle
    IDLE_PRONE_RESOURCES = [
        "Microsoft.Compute/virtualMachines",
        "Microsoft.Compute/disks",
        "Microsoft.Network/publicIPAddresses",
        "Microsoft.Sql/servers/databases",
        "Microsoft.Storage/storageAccounts",
        "Microsoft.Network/loadBalancers",
        "Microsoft.Network/networkInterfaces",
    ]

    def __init__(self, subscription_id: str | None = None):
        self.subscription_id = subscription_id or os.environ.get("AZURE_SUBSCRIPTION_ID")
        self._cost_mgmt_client: Any = None
        self._resource_client: Any = None
        self._monitor_client: Any = None
        self._alerts: list[CostAlert] = []

    def _get_cost_mgmt_client(self) -> Any:
        """Get Azure Cost Management client."""
        if self._cost_mgmt_client is None:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.mgmt.costmanagement import CostManagementClient

                credential = DefaultAzureCredential()
                self._cost_mgmt_client = CostManagementClient(credential)
                logger.info("Connected to Azure Cost Management")
            except ImportError:
                logger.error(
                    "Azure SDK not installed. Run: pip install azure-mgmt-costmanagement azure-identity"
                )
                raise
        return self._cost_mgmt_client

    def _get_resource_client(self) -> Any:
        """Get Azure Resource Management client."""
        if self._resource_client is None:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.mgmt.resource import ResourceManagementClient

                credential = DefaultAzureCredential()
                subscription = self.subscription_id or os.environ.get("AZURE_SUBSCRIPTION_ID")
                self._resource_client = ResourceManagementClient(credential, subscription)
            except ImportError:
                logger.error("Azure SDK not installed")
                raise
        return self._resource_client

    def _get_monitor_client(self) -> Any:
        """Get Azure Monitor client for metrics."""
        if self._monitor_client is None:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.mgmt.monitor import MonitorManagementClient

                credential = DefaultAzureCredential()
                subscription = self.subscription_id or os.environ.get("AZURE_SUBSCRIPTION_ID")
                self._monitor_client = MonitorManagementClient(credential, subscription)
            except ImportError:
                logger.error("Azure SDK not installed")
                raise
        return self._monitor_client

    def get_costs_by_resource_group(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CostBreakdown]:
        """Get cost breakdown by resource group."""
        try:
            from azure.mgmt.costmanagement.models import (
                QueryAggregation,
                QueryDataset,
                QueryDefinition,
                QueryGrouping,
            )

            client = self._get_cost_mgmt_client()
            scope = f"/subscriptions/{self.subscription_id}"

            # Build query for resource group costs
            query = QueryDefinition(
                type="ActualCost",
                timeframe="Custom",
                time_period={
                    "from": start_date.strftime("%Y-%m-%dT00:00:00Z"),
                    "to": end_date.strftime("%Y-%m-%dT23:59:59Z"),
                },
                dataset=QueryDataset(
                    granularity="None",
                    aggregation={"totalCost": QueryAggregation(name="PreTaxCost", function="Sum")},
                    grouping=[
                        QueryGrouping(name="ResourceGroup", type="Dimension"),
                        QueryGrouping(name="ServiceName", type="Dimension"),
                    ],
                ),
            )

            result = client.query.usage(scope, query)

            breakdowns = []
            for row in result.rows:
                breakdowns.append(
                    CostBreakdown(
                        service_name=row[1] if len(row) > 1 else "Unknown",
                        resource_group=row[2] if len(row) > 2 else "Unknown",
                        cost_usd=Decimal(str(row[0])),
                    )
                )

            return breakdowns

        except Exception as e:
            logger.error(f"Failed to get costs: {e}")
            # Return empty list - will show helpful error in UI
            return []

    def get_detailed_costs(
        self, start_date: datetime, end_date: datetime, group_by_tenant: bool = False
    ) -> list[CostBreakdown]:
        """Get detailed cost breakdown with optional tenant grouping."""
        try:
            # Try SDK approach first
            return self._get_detailed_costs_sdk(start_date, end_date, group_by_tenant)
        except Exception as e:
            logger.warning(f"SDK approach failed: {e}, falling back to CLI")
            return self._get_detailed_costs_cli(start_date, end_date, group_by_tenant)

    def _get_detailed_costs_sdk(
        self, start_date: datetime, end_date: datetime, group_by_tenant: bool
    ) -> list[CostBreakdown]:
        """Get costs using Azure SDK."""
        from azure.mgmt.costmanagement.models import (
            QueryAggregation,
            QueryDataset,
            QueryDefinition,
            QueryGrouping,
        )

        client = self._get_cost_mgmt_client()
        scope = f"/subscriptions/{self.subscription_id}"

        groupings = [
            QueryGrouping(name="ResourceGroup", type="Dimension"),
            QueryGrouping(name="ServiceName", type="Dimension"),
        ]

        if group_by_tenant:
            groupings.append(QueryGrouping(name="TagKey", type="TagKey"))

        query = QueryDefinition(
            type="ActualCost",
            timeframe="Custom",
            time_period={
                "from": start_date.strftime("%Y-%m-%dT00:00:00Z"),
                "to": end_date.strftime("%Y-%m-%dT23:59:59Z"),
            },
            dataset=QueryDataset(
                granularity="None",
                aggregation={
                    "totalCost": QueryAggregation(name="PreTaxCost", function="Sum"),
                    "usageQuantity": QueryAggregation(name="UsageQuantity", function="Sum"),
                },
                grouping=groupings,
            ),
        )

        result = client.query.usage(scope, query)

        breakdowns = []
        for row in result.rows:
            cost_idx = 0
            quantity_idx = 1 if len(row) > 1 else None
            service_idx = -2 if len(row) > 2 else 0
            rg_idx = -1

            tags = {}
            if group_by_tenant and len(row) > 4:
                # Extract tenant tag if present
                tag_key = row[-3] if len(row) > 3 else None
                if tag_key:
                    tags["tenant"] = tag_key

            breakdowns.append(
                CostBreakdown(
                    cost_usd=Decimal(str(row[cost_idx])),
                    usage_quantity=Decimal(str(row[quantity_idx]))
                    if quantity_idx
                    else Decimal("0"),
                    service_name=str(row[service_idx]) if service_idx < len(row) else "Unknown",
                    resource_group=str(row[rg_idx]) if rg_idx < len(row) else "Unknown",
                    tags=tags,
                )
            )

        return breakdowns

    def _get_detailed_costs_cli(
        self, start_date: datetime, end_date: datetime, group_by_tenant: bool
    ) -> list[CostBreakdown]:
        """Fallback: Get costs using Azure CLI."""
        import subprocess

        cmd = [
            "az",
            "costmanagement",
            "query",
            "--scope",
            f"/subscriptions/{self.subscription_id}",
            "--timeframe",
            "Custom",
            "--time-period",
            f"from={start_date.strftime('%Y-%m-%d')}",
            "--time-period",
            f"to={end_date.strftime('%Y-%m-%d')}",
            "--dataset-aggregation",
            "totalCost=PreTaxCost",
            "--dataset-grouping",
            "ResourceGroup",
            "--dataset-grouping",
            "ServiceName",
            "--output",
            "json",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)

            breakdowns = []
            for row in data.get("rows", []):
                breakdowns.append(
                    CostBreakdown(
                        cost_usd=Decimal(str(row[0])),
                        service_name=row[1] if len(row) > 1 else "Unknown",
                        resource_group=row[2] if len(row) > 2 else "Unknown",
                    )
                )

            return breakdowns
        except Exception as e:
            logger.error(f"CLI fallback also failed: {e}")
            return []

    def find_idle_resources(self, days_threshold: int = 7) -> list[IdleResource]:
        """Find idle resources that may be candidates for deletion."""
        idle_resources = []

        try:
            resource_client = self._get_resource_client()
            monitor_client = self._get_monitor_client()

            # Check each resource type
            for resource_type in self.IDLE_PRONE_RESOURCES:
                resources = resource_client.resources.list(
                    filter=f"resourceType eq '{resource_type}'"
                )

                for resource in resources:
                    idle_info = self._check_resource_idle(resource, monitor_client, days_threshold)
                    if idle_info:
                        idle_resources.append(idle_info)

        except Exception as e:
            logger.error(f"Failed to find idle resources: {e}")

        return idle_resources

    def _check_resource_idle(
        self, resource: Any, monitor_client: Any, days_threshold: int
    ) -> IdleResource | None:
        """Check if a specific resource is idle."""
        resource_type = resource.type
        resource_id = resource.id
        resource_name = resource.name
        resource_group = resource.id.split("/")[4] if resource.id else "Unknown"

        try:
            # Different metrics for different resource types
            metric_name = (
                "Percentage CPU"
                if resource_type == "Microsoft.Compute/virtualMachines"
                else "Transactions"
            )

            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days_threshold)

            metrics = monitor_client.metrics.list(
                resource_id,
                timespan=f"{start_time.isoformat()}/{end_time.isoformat()}",
                interval="PT1H",
                metricnames=metric_name,
                aggregation="Average",
            )

            # Check if there are any significant metrics
            total_usage = 0
            data_points = 0

            for metric in metrics.value:
                for time_series in metric.timeseries:
                    for point in time_series.data:
                        if point.average:
                            total_usage += point.average
                            data_points += 1

            avg_usage = total_usage / data_points if data_points > 0 else 0

            # Determine if idle based on usage
            is_idle = False
            reason = ""
            recommendation = ""

            if resource_type == "Microsoft.Compute/virtualMachines":
                if avg_usage < 5:  # Less than 5% CPU average
                    is_idle = True
                    reason = (
                        f"Very low CPU usage: {avg_usage:.1f}% average over {days_threshold} days"
                    )
                    recommendation = "Consider stopping VM or using Start/Stop VMs solution"

            elif resource_type == "Microsoft.Compute/disks":
                # Check if disk is unattached
                if getattr(resource.properties, "disk_state", None) == "Unattached":
                    is_idle = True
                    reason = "Disk is unattached"
                    recommendation = "Delete unattached disk or attach to VM"

            if is_idle:
                # Estimate monthly cost (simplified)
                monthly_cost = self._estimate_resource_cost(resource_type, resource)

                return IdleResource(
                    resource_type=resource_type,
                    resource_name=resource_name,
                    resource_id=resource_id,
                    resource_group=resource_group,
                    last_used_days=days_threshold,
                    monthly_cost=monthly_cost,
                    reason=reason,
                    recommendation=recommendation,
                    tags=resource.tags or {},
                )

        except Exception as e:
            logger.debug(f"Could not check resource {resource_name}: {e}")

        return None

    def _estimate_resource_cost(self, resource_type: str, resource: Any) -> Decimal:
        """Estimate monthly cost of a resource."""
        # Simplified cost estimates - in production, use actual billing data
        estimates = {
            "Microsoft.Compute/virtualMachines": Decimal("50"),  # Average VM
            "Microsoft.Compute/disks": Decimal("5"),  # Average disk
            "Microsoft.Network/publicIPAddresses": Decimal("3"),
            "Microsoft.Sql/servers/databases": Decimal("15"),
        }
        return estimates.get(resource_type, Decimal("10"))

    def check_cost_thresholds(
        self, threshold_monthly: Decimal, threshold_daily: Decimal | None = None
    ) -> list[CostAlert]:
        """Check if costs exceed thresholds and generate alerts."""
        alerts = []

        # Get current month costs
        today = datetime.utcnow()
        first_day = today.replace(day=1)

        costs = self.get_detailed_costs(first_day, today)
        total_cost = sum(c.cost_usd for c in costs)

        # Check monthly threshold
        if total_cost > threshold_monthly:
            alerts.append(
                CostAlert(
                    alert_type="threshold",
                    severity="critical" if total_cost > threshold_monthly * 2 else "warning",
                    message=f"Monthly cost (${total_cost}) exceeds threshold (${threshold_monthly})",
                    current_cost=total_cost,
                    threshold=threshold_monthly,
                    recommendation="Review cost breakdown and consider optimization measures",
                )
            )

        # Check daily threshold (average)
        days_in_month = today.day
        daily_average = total_cost / days_in_month if days_in_month > 0 else Decimal("0")

        if threshold_daily and daily_average > threshold_daily:
            alerts.append(
                CostAlert(
                    alert_type="threshold",
                    severity="warning",
                    message=f"Daily cost average (${daily_average:.2f}) exceeds threshold (${threshold_daily})",
                    current_cost=daily_average,
                    threshold=threshold_daily,
                    recommendation="Monitor for cost spikes and investigate unexpected usage",
                )
            )

        self._alerts.extend(alerts)
        return alerts

    def generate_cost_report(
        self, days: int = 30, group_by_tenant: bool = False, include_idle_resources: bool = False
    ) -> dict[str, Any]:
        """Generate comprehensive cost report."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        logger.info(f"Generating cost report for {days} days...")

        # Get cost breakdown
        costs = self.get_detailed_costs(start_date, end_date, group_by_tenant)

        # Calculate totals
        total_cost = sum(c.cost_usd for c in costs)

        # Group by service
        by_service: dict[str, Decimal] = {}
        for c in costs:
            by_service[c.service_name] = by_service.get(c.service_name, Decimal("0")) + c.cost_usd

        # Group by resource group
        by_resource_group: dict[str, Decimal] = {}
        for c in costs:
            by_resource_group[c.resource_group] = (
                by_resource_group.get(c.resource_group, Decimal("0")) + c.cost_usd
            )

        # Group by tenant if requested
        by_tenant: dict[str, Decimal] = {}
        if group_by_tenant:
            for c in costs:
                tenant = c.tenant_name
                by_tenant[tenant] = by_tenant.get(tenant, Decimal("0")) + c.cost_usd

        # Find idle resources
        idle_resources = []
        if include_idle_resources:
            logger.info("Scanning for idle resources...")
            idle_resources = self.find_idle_resources()

        # Calculate potential savings
        potential_savings = sum(r.potential_savings_annual for r in idle_resources)

        return {
            "report_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days,
            },
            "summary": {
                "total_cost_usd": float(total_cost),
                "daily_average": float(total_cost / days) if days > 0 else 0,
                "projected_monthly": float(total_cost / days * 30) if days > 0 else 0,
                "service_count": len(by_service),
                "resource_group_count": len(by_resource_group),
                "idle_resource_count": len(idle_resources),
                "potential_annual_savings": float(potential_savings),
            },
            "by_service": {
                k: float(v) for k, v in sorted(by_service.items(), key=lambda x: x[1], reverse=True)
            },
            "by_resource_group": {
                k: float(v)
                for k, v in sorted(by_resource_group.items(), key=lambda x: x[1], reverse=True)
            },
            "by_tenant": {
                k: float(v) for k, v in sorted(by_tenant.items(), key=lambda x: x[1], reverse=True)
            }
            if by_tenant
            else {},
            "idle_resources": [asdict(r) for r in idle_resources],
            "alerts": [asdict(a) for a in self._alerts],
            "generated_at": datetime.utcnow().isoformat(),
        }

    def export_to_csv(self, report: dict[str, Any], output_path: str) -> None:
        """Export cost report to CSV for finance team."""
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)

            # Header
            writer.writerow(
                ["Report Period", "Service", "Resource Group", "Cost (USD)", "Percentage"]
            )

            # Summary row
            total = report["summary"]["total_cost_usd"]
            writer.writerow(
                [
                    f"{report['report_period']['start'][:10]} to {report['report_period']['end'][:10]}",
                    "TOTAL",
                    "ALL",
                    f"{total:.2f}",
                    "100.00%",
                ]
            )

            # Service breakdown
            for service, cost in report["by_service"].items():
                percentage = (cost / total * 100) if total > 0 else 0
                writer.writerow(["", service, "", f"{cost:.2f}", f"{percentage:.2f}%"])

            # Blank row
            writer.writerow([])

            # Idle resources section
            if report["idle_resources"]:
                writer.writerow(["IDLE RESOURCES", "", "", "", ""])
                writer.writerow(
                    ["Resource Name", "Type", "Resource Group", "Monthly Cost", "Recommendation"]
                )

                for resource in report["idle_resources"]:
                    writer.writerow(
                        [
                            resource["resource_name"],
                            resource["resource_type"].split("/")[-1],
                            resource["resource_group"],
                            f"${resource['monthly_cost']:.2f}",
                            resource["recommendation"],
                        ]
                    )

        logger.info(f"Cost report exported to: {output_path}")

    def send_alert_notifications(self, webhook_url: str | None = None) -> bool:
        """Send cost alerts to Teams/Slack webhook."""
        if not self._alerts:
            return True

        webhook = (
            webhook_url
            or os.environ.get("TEAMS_WEBHOOK_URL")
            or os.environ.get("SLACK_WEBHOOK_URL")
        )

        if not webhook:
            logger.warning("No webhook configured for alerts")
            return False

        try:
            import requests

            # Build message
            message = f"## Azure Cost Alert\n\n{len(self._alerts)} cost alert(s) triggered:\n\n"
            for alert in self._alerts:
                message += f"**{alert.severity.upper()}**: {alert.message}\n"
                if alert.recommendation:
                    message += f"💡 {alert.recommendation}\n\n"

            # Determine if Teams or Slack
            if "office.com" in webhook or "teams" in webhook:
                # Teams webhook format
                payload = {
                    "@type": "MessageCard",
                    "@context": "https://schema.org/extensions",
                    "themeColor": "ff0000"
                    if any(a.severity == "critical" for a in self._alerts)
                    else "ff9900",
                    "title": "Azure Cost Alert",
                    "text": message,
                }
            else:
                # Slack webhook format
                payload = {
                    "text": message,
                    "username": "Azure Cost Bot",
                    "icon_emoji": ":money_with_wings:",
                }

            response = requests.post(webhook, json=payload, timeout=30)
            response.raise_for_status()

            logger.info("Alert notifications sent successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to send alert notifications: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Azure Costs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic cost analysis
  %(prog)s --subscription $AZURE_SUBSCRIPTION_ID
  
  # With tenant breakdown
  %(prog)s --subscription $SUB_ID --by-tenant
  
  # Find idle resources
  %(prog)s --subscription $SUB_ID --find-idle
  
  # Cost alerts
  %(prog)s --subscription $SUB_ID --alert-threshold 1000
  
  # Export to CSV
  %(prog)s --subscription $SUB_ID --export-csv costs.csv
        """,
    )

    parser.add_argument("--subscription", "-s", help="Azure subscription ID")
    parser.add_argument("--days", "-d", type=int, default=30, help="Analysis period in days")
    parser.add_argument("--by-tenant", "-t", action="store_true", help="Group by tenant")
    parser.add_argument("--find-idle", "-i", action="store_true", help="Find idle resources")
    parser.add_argument("--idle-days", type=int, default=7, help="Days to consider resource idle")
    parser.add_argument("--alert-threshold", type=float, help="Monthly cost alert threshold (USD)")
    parser.add_argument("--export-csv", "-o", help="Export report to CSV file")
    parser.add_argument("--export-json", "-j", help="Export report to JSON file")
    parser.add_argument("--webhook", "-w", help="Webhook URL for alerts")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize analyzer
    analyzer = AzureCostAnalyzer(args.subscription)

    # Check for alerts if threshold specified
    if args.alert_threshold:
        logger.info(f"Checking cost threshold: ${args.alert_threshold}/month")
        alerts = analyzer.check_cost_thresholds(Decimal(str(args.alert_threshold)))

        if alerts:
            print(f"\n{'='*60}")
            print("COST ALERTS")
            print(f"{'='*60}")
            for alert in alerts:
                emoji = "🔴" if alert.severity == "critical" else "🟡"
                print(f"{emoji} {alert.message}")
                print(f"   Recommendation: {alert.recommendation}\n")
            print(f"{'='*60}\n")

            # Send notifications
            analyzer.send_alert_notifications(args.webhook)
        else:
            print("✅ No cost alerts - spending within threshold")

    # Generate full report
    report = analyzer.generate_cost_report(
        days=args.days, group_by_tenant=args.by_tenant, include_idle_resources=args.find_idle
    )

    # Display summary
    print(f"\n{'='*60}")
    print(f"AZURE COST REPORT: {report['report_period']['days']} Days")
    print(f"{'='*60}")
    print(f"Total Cost:        ${report['summary']['total_cost_usd']:.2f}")
    print(f"Daily Average:     ${report['summary']['daily_average']:.2f}")
    print(f"Projected Monthly: ${report['summary']['projected_monthly']:.2f}")
    print("\nTop Services by Cost:")
    for service, cost in list(report["by_service"].items())[:5]:
        percentage = cost / report["summary"]["total_cost_usd"] * 100
        print(f"  - {service}: ${cost:.2f} ({percentage:.1f}%)")

    if report["idle_resources"]:
        print(f"\n⚠️  Idle Resources Found: {len(report['idle_resources'])}")
        print(f"💰 Potential Annual Savings: ${report['summary']['potential_annual_savings']:.2f}")

    print(f"{'='*60}\n")

    # Export if requested
    if args.export_csv:
        analyzer.export_to_csv(report, args.export_csv)

    if args.export_json:
        with open(args.export_json, "w") as f:
            json.dump(report, f, indent=2)
        logger.info(f"Report exported to JSON: {args.export_json}")

    # Exit with error code if critical alerts
    critical_alerts = [a for a in analyzer._alerts if a.severity == "critical"]
    sys.exit(1 if critical_alerts else 0)


if __name__ == "__main__":
    main()
