#!/usr/bin/env python3
"""
Azure SQL Free Tier Evaluation Script for Staging Environment

Analyzes current staging database usage against Azure SQL Free Tier limits:
- Max size: 32 GB (2 GB data + 30 GB log)
- Compute: Basic (limited DTUs)
- 1 free database per subscription

Usage:
    python scripts/evaluate-sql-free-tier.py --resource-group rg-governance-staging \
        --server sql-governance-staging-xxx --database governance-db

Author: Code Puppy (Richard) 🐶
Issue: l5i
"""

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

# Azure SQL Free Tier Limits
FREE_TIER_LIMITS = {
    "max_size_gb": 32,
    "max_data_size_gb": 2,
    "max_log_size_gb": 30,
    "max_dtu": 5,  # Approximate, Free tier is basic compute
    "max_connections": 30,
    "sla": "None",  # No SLA on Free Tier
    "geo_replication": False,
    "auto_failover": False,
    "point_in_time_restore": "7 days",
}

# Estimated costs for comparison (monthly)
TIER_COSTS = {
    "Basic": 4.90,
    "Standard_S0": 15.00,
    "Standard_S1": 30.00,
    "Free": 0.00,
}


@dataclass
class DatabaseMetrics:
    """Database usage metrics"""
    current_size_gb: float
    data_size_gb: float
    log_size_gb: float
    max_size_gb: float
    avg_dtu_percent: float
    max_dtu_percent: float
    avg_cpu_percent: float
    max_cpu_percent: float
    avg_connections: float
    max_connections: int
    storage_percent: float
    deadlocks_per_hour: float


@dataclass
class EvaluationResult:
    """Free Tier compatibility evaluation"""
    timestamp: str
    resource_group: str
    server_name: str
    database_name: str
    current_tier: str
    current_sku: str
    metrics: DatabaseMetrics
    free_tier_compatible: bool
    compatibility_score: float  # 0-100
    risks: list[str]
    recommendations: list[str]
    estimated_savings_monthly: float
    estimated_savings_annual: float


def run_az_command(args: list[str]) -> tuple[bool, str]:
    """Execute Azure CLI command and return (success, output)"""
    try:
        result = subprocess.run(
            ["az"] + args,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return True, result.stdout
        return False, result.stderr
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except FileNotFoundError:
        return False, "Azure CLI not found. Install: https://aka.ms/azure-cli"


def get_database_info(resource_group: str, server_name: str, database_name: str) -> dict:
    """Get current database configuration"""
    success, output = run_az_command([
        "sql", "db", "show",
        "--resource-group", resource_group,
        "--server", server_name,
        "--name", database_name,
        "--output", "json"
    ])
    if success:
        return json.loads(output)
    return {}


def get_database_size(resource_group: str, server_name: str, database_name: str) -> dict:
    """Get database size information using space-used metric"""
    end_time = datetime.utcnow().isoformat() + "Z"
    start_time = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"

    success, output = run_az_command([
        "monitor", "metrics", "list",
        "--resource", f"/subscriptions/{get_subscription_id()}/resourceGroups/{resource_group}/providers/Microsoft.Sql/servers/{server_name}/databases/{database_name}",
        "--metric", "storage",
        "--start-time", start_time,
        "--end-time", end_time,
        "--interval", "PT1H",
        "--aggregation", "Average",
        "--output", "json"
    ])

    if success:
        data = json.loads(output)
        if data.get("value") and data["value"][0].get("timeseries"):
            avg = data["value"][0]["timeseries"][0].get("data", [{}])[0].get("average", 0)
            return {"avg_bytes": avg}

    # Fallback: use az sql db list-usages
    success, output = run_az_command([
        "sql", "db", "list-usages",
        "--resource-group", resource_group,
        "--server", server_name,
        "--name", database_name,
        "--output", "json"
    ])
    if success:
        usages = json.loads(output)
        for usage in usages:
            if usage.get("name") == "database_size":
                return {"current_bytes": usage.get("currentValue", 0), "limit_bytes": usage.get("limit", 0)}

    return {}


def get_metrics(
    resource_group: str,
    server_name: str,
    database_name: str,
    metric_name: str,
    aggregation: str = "Average",
    hours: int = 168  # 7 days
) -> list[float]:
    """Get Azure Monitor metrics for the database"""
    end_time = datetime.utcnow().isoformat() + "Z"
    start_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"

    success, output = run_az_command([
        "monitor", "metrics", "list",
        "--resource", f"/subscriptions/{get_subscription_id()}/resourceGroups/{resource_group}/providers/Microsoft.Sql/servers/{server_name}/databases/{database_name}",
        "--metric", metric_name,
        "--start-time", start_time,
        "--end-time", end_time,
        "--interval", "PT1H",
        "--aggregation", aggregation,
        "--output", "json"
    ])

    values = []
    if success:
        data = json.loads(output)
        for metric in data.get("value", []):
            for series in metric.get("timeseries", []):
                for point in series.get("data", []):
                    val = point.get(aggregation.lower(), 0)
                    if val is not None:
                        values.append(float(val))
    return values


def get_subscription_id() -> str:
    """Get current Azure subscription ID"""
    success, output = run_az_command(["account", "show", "--query", "id", "-o", "tsv"])
    return output.strip() if success else ""


def calculate_metrics(
    resource_group: str,
    server_name: str,
    database_name: str
) -> DatabaseMetrics:
    """Calculate all database metrics"""
    # Get size metrics
    size_info = get_database_size(resource_group, server_name, database_name)
    current_bytes = size_info.get("current_bytes", size_info.get("avg_bytes", 0))
    limit_bytes = size_info.get("limit_bytes", 268435456000)  # Default 250GB

    current_size_gb = current_bytes / (1024**3)
    max_size_gb = limit_bytes / (1024**3)

    # Estimate data vs log (typical ratio ~85% data, 15% log)
    data_size_gb = current_size_gb * 0.85
    log_size_gb = current_size_gb * 0.15

    # Get DTU metrics (7 days)
    dtu_values = get_metrics(resource_group, server_name, database_name, "dtu_consumption_percent", "Average", 168)
    avg_dtu = sum(dtu_values) / len(dtu_values) if dtu_values else 0
    max_dtu = max(dtu_values) if dtu_values else 0

    # Get CPU metrics
    cpu_values = get_metrics(resource_group, server_name, database_name, "cpu_percent", "Average", 168)
    avg_cpu = sum(cpu_values) / len(cpu_values) if cpu_values else 0
    max_cpu = max(cpu_values) if cpu_values else 0

    # Get connection metrics
    conn_values = get_metrics(resource_group, server_name, database_name, "connection_failed", "Total", 168)
    # Get active connections instead
    active_conn = get_metrics(resource_group, server_name, database_name, "sessions_count", "Maximum", 168)
    avg_connections = sum(active_conn) / len(active_conn) if active_conn else 0
    max_connections = int(max(active_conn)) if active_conn else 0

    # Storage percent
    storage_pct = (current_size_gb / max_size_gb * 100) if max_size_gb > 0 else 0

    # Get deadlock count (7 days)
    deadlock_values = get_metrics(resource_group, server_name, database_name, "deadlock", "Total", 168)
    deadlocks_per_hour = sum(deadlock_values) / 168 if deadlock_values else 0

    return DatabaseMetrics(
        current_size_gb=round(current_size_gb, 2),
        data_size_gb=round(data_size_gb, 2),
        log_size_gb=round(log_size_gb, 2),
        max_size_gb=round(max_size_gb, 2),
        avg_dtu_percent=round(avg_dtu, 2),
        max_dtu_percent=round(max_dtu, 2),
        avg_cpu_percent=round(avg_cpu, 2),
        max_cpu_percent=round(max_cpu, 2),
        avg_connections=round(avg_connections, 1),
        max_connections=max_connections,
        storage_percent=round(storage_pct, 2),
        deadlocks_per_hour=round(deadlocks_per_hour, 2),
    )


def evaluate_compatibility(
    db_info: dict,
    metrics: DatabaseMetrics,
    current_tier: str
) -> tuple[bool, float, list[str], list[str]]:
    """
    Evaluate Free Tier compatibility
    Returns: (is_compatible, score, risks, recommendations)
    """
    risks = []
    recommendations = []
    score = 100.0

    # Check size limit (32 GB total)
    if metrics.current_size_gb > FREE_TIER_LIMITS["max_size_gb"]:
        risks.append(f"Database size ({metrics.current_size_gb:.2f} GB) exceeds Free Tier limit ({FREE_TIER_LIMITS['max_size_gb']} GB)")
        score -= 50
    elif metrics.current_size_gb > 25:  # Warning at 25GB
        recommendations.append(f"Database size ({metrics.current_size_gb:.2f} GB) is approaching Free Tier limit - monitor growth")
        score -= 10
    else:
        recommendations.append(f"✓ Database size ({metrics.current_size_gb:.2f} GB) fits within Free Tier ({FREE_TIER_LIMITS['max_size_gb']} GB)")

    # Check data size (2 GB)
    if metrics.data_size_gb > FREE_TIER_LIMITS["max_data_size_gb"]:
        risks.append(f"Data size ({metrics.data_size_gb:.2f} GB) exceeds Free Tier data limit ({FREE_TIER_LIMITS['max_data_size_gb']} GB)")
        score -= 40

    # Check connection limit (30)
    if metrics.max_connections > FREE_TIER_LIMITS["max_connections"]:
        risks.append(f"Peak connections ({metrics.max_connections}) exceeds Free Tier limit ({FREE_TIER_LIMITS['max_connections']})")
        score -= 20
    else:
        recommendations.append(f"✓ Connection count ({metrics.max_connections}) within Free Tier limits")

    # Check DTU usage
    if metrics.max_dtu_percent > 80:
        recommendations.append(f"⚠ Peak DTU usage ({metrics.max_dtu_percent}%) may hit Free Tier compute limits")
        score -= 10

    # Check deadlocks
    if metrics.deadlocks_per_hour > 1:
        risks.append(f"High deadlock rate ({metrics.deadlocks_per_hour:.2f}/hour) may indicate concurrency issues")
        score -= 5

    # SLA consideration
    if current_tier in ["Standard_S1", "Standard_S2", "Premium"]:
        recommendations.append("⚠ Free Tier has no SLA - acceptable for staging only")
        score -= 5

    # Staging-specific recommendations
    recommendations.append("✓ Free Tier suitable for non-production staging environment")
    recommendations.append("✓ No geo-redundancy required for staging")

    is_compatible = len([r for r in risks if "exceeds" in r.lower()]) == 0

    return is_compatible, max(0, score), risks, recommendations


def generate_report(
    resource_group: str,
    server_name: str,
    database_name: str,
    output_path: str | None = None
) -> EvaluationResult:
    """Generate full evaluation report"""
    print("🔍 Azure SQL Free Tier Evaluation")
    print("=" * 50)
    print(f"Database: {server_name}/{database_name}")
    print(f"Resource Group: {resource_group}")
    print("-" * 50)

    # Get database info
    print("📊 Fetching database configuration...")
    db_info = get_database_info(resource_group, server_name, database_name)

    current_sku = db_info.get("sku", {}).get("name", "Unknown")
    current_tier = db_info.get("sku", {}).get("tier", "Unknown")

    print(f"Current SKU: {current_sku} ({current_tier})")

    # Get metrics
    print("📈 Analyzing 7-day metrics...")
    metrics = calculate_metrics(resource_group, server_name, database_name)

    # Evaluate
    compatible, score, risks, recommendations = evaluate_compatibility(
        db_info, metrics, current_tier
    )

    # Calculate savings
    current_cost = TIER_COSTS.get(current_sku, TIER_COSTS.get(current_tier, 15.0))
    savings_monthly = current_cost
    savings_annual = savings_monthly * 12

    result = EvaluationResult(
        timestamp=datetime.utcnow().isoformat() + "Z",
        resource_group=resource_group,
        server_name=server_name,
        database_name=database_name,
        current_tier=current_tier,
        current_sku=current_sku,
        metrics=metrics,
        free_tier_compatible=compatible,
        compatibility_score=score,
        risks=risks,
        recommendations=recommendations,
        estimated_savings_monthly=round(savings_monthly, 2),
        estimated_savings_annual=round(savings_annual, 2),
    )

    # Print summary
    print("\n📋 Evaluation Results")
    print("=" * 50)
    print(f"Free Tier Compatible: {'✅ YES' if compatible else '❌ NO'}")
    print(f"Compatibility Score: {score:.1f}/100")
    print("\n💰 Cost Impact:")
    print(f"  Current estimated cost: ${current_cost:.2f}/month")
    print("  Free Tier cost: $0.00/month")
    print(f"  Monthly savings: ${savings_monthly:.2f}")
    print(f"  Annual savings: ${savings_annual:.2f}")

    print("\n📊 Current Metrics:")
    print(f"  Database Size: {metrics.current_size_gb:.2f} GB / {metrics.max_size_gb:.2f} GB ({metrics.storage_percent:.1f}%)")
    print(f"  Avg DTU: {metrics.avg_dtu_percent:.1f}% | Peak DTU: {metrics.max_dtu_percent:.1f}%")
    print(f"  Avg Connections: {metrics.avg_connections:.1f} | Peak Connections: {metrics.max_connections}")
    print(f"  Deadlocks/hour: {metrics.deadlocks_per_hour:.2f}")

    print(f"\n⚠️  Risks ({len(risks)}):")
    for risk in risks:
        print(f"  • {risk}")
    if not risks:
        print("  • None identified")

    print(f"\n💡 Recommendations ({len(recommendations)}):")
    for rec in recommendations:
        print(f"  • {rec}")

    # Save to file
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        report_data = {
            "evaluation": asdict(result),
            "free_tier_limits": FREE_TIER_LIMITS,
            "tier_costs": TIER_COSTS,
        }

        with open(output_file, "w") as f:
            json.dump(report_data, f, indent=2)
        print(f"\n💾 Report saved to: {output_file}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate Azure SQL Free Tier compatibility for staging"
    )
    parser.add_argument(
        "--resource-group", "-g",
        default="rg-governance-staging",
        help="Resource group name (default: rg-governance-staging)"
    )
    parser.add_argument(
        "--server", "-s",
        required=True,
        help="SQL Server name"
    )
    parser.add_argument(
        "--database", "-d",
        default="governance-db",
        help="Database name (default: governance-db)"
    )
    parser.add_argument(
        "--output", "-o",
        default="docs/analysis/sql-free-tier-report.json",
        help="Output JSON file path"
    )
    parser.add_argument(
        "--subscription",
        help="Azure subscription ID (optional)"
    )

    args = parser.parse_args()

    # Verify Azure login
    success, _ = run_az_command(["account", "show"])
    if not success:
        print("❌ Not logged into Azure. Run: az login")
        sys.exit(1)

    if args.subscription:
        run_az_command(["account", "set", "--subscription", args.subscription])

    # Generate report
    result = generate_report(
        args.resource_group,
        args.server,
        args.database,
        args.output
    )

    # Exit code based on compatibility
    sys.exit(0 if result.free_tier_compatible else 1)


if __name__ == "__main__":
    main()
