#!/usr/bin/env python3
"""Azure SQL Elastic Pool Evaluation Script.

Analyzes database usage patterns to determine if elastic pool
would be cost-effective for a multi-tenant setup.

Calculates:
- Per-database DTU usage patterns
- Peak vs average utilization
- Cost comparison (single DB vs elastic pool)
- Recommended pool configuration

Usage:
    python scripts/evaluate-elastic-pools.py --analyze
    python scripts/evaluate-elastic-pools.py --cost-comparison --databases 10 --dtu-tier S2
    python scripts/evaluate-elastic-pools.py --recommend --output recommendation.json

Environment:
    Requires DATABASE_URL environment variable set to Azure SQL connection string.
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Azure SQL Pricing (approximate, as of 2024)
# These are rough estimates - actual pricing varies by region
SINGLE_DB_PRICING = {
    "S0": {"dtus": 10, "monthly_cost": 15.00},
    "S1": {"dtus": 20, "monthly_cost": 30.00},
    "S2": {"dtus": 50, "monthly_cost": 75.00},
    "S3": {"dtus": 100, "monthly_cost": 150.00},
    "P1": {"dtus": 125, "monthly_cost": 465.00},
    "P2": {"dtus": 250, "monthly_cost": 930.00},
}

ELASTIC_POOL_PRICING = {
    "Standard_100": {"dtus": 100, "monthly_cost": 148.00, "max_databases": 200},
    "Standard_200": {"dtus": 200, "monthly_cost": 296.00, "max_databases": 500},
    "Standard_300": {"dtus": 300, "monthly_cost": 444.00, "max_databases": 500},
    "Standard_400": {"dtus": 400, "monthly_cost": 595.00, "max_databases": 500},
    "Standard_800": {"dtus": 800, "monthly_cost": 1190.00, "max_databases": 500},
    "Standard_1200": {"dtus": 1200, "monthly_cost": 1785.00, "max_databases": 500},
    "Standard_1600": {"dtus": 1600, "monthly_cost": 2380.00, "max_databases": 500},
    "Standard_3000": {"dtus": 3000, "monthly_cost": 4460.00, "max_databases": 500},
    "Premium_125": {"dtus": 125, "monthly_cost": 465.00, "max_databases": 50},
    "Premium_250": {"dtus": 250, "monthly_cost": 930.00, "max_databases": 100},
    "Premium_500": {"dtus": 500, "monthly_cost": 1860.00, "max_databases": 100},
    "Premium_1000": {"dtus": 1000, "monthly_cost": 3720.00, "max_databases": 100},
    "Premium_1500": {"dtus": 1500, "monthly_cost": 5580.00, "max_databases": 100},
}


@dataclass
class DatabaseMetrics:
    """Metrics for a single database."""

    database_name: str
    avg_cpu_percent: float
    max_cpu_percent: float
    avg_data_io_percent: float
    max_data_io_percent: float
    avg_log_write_percent: float
    max_log_write_percent: float
    dtu_limit: int
    storage_mb: float
    sample_count: int


@dataclass
class ElasticPoolRecommendation:
    """Elastic pool recommendation result."""

    recommended: bool
    reason: str
    current_setup_cost: float
    elastic_pool_cost: float
    annual_savings: float
    savings_percent: float
    recommended_pool: str
    pool_dtu_utilization: float
    estimated_databases_supported: int
    risk_level: str


class ElasticPoolEvaluator:
    """Evaluates whether elastic pool makes sense for the workload."""

    def __init__(self, db: Session):
        self.db = db
        self._is_azure_sql: bool | None = None

    def is_azure_sql(self) -> bool:
        """Check if connected to Azure SQL."""
        if self._is_azure_sql is not None:
            return self._is_azure_sql

        settings = get_settings()
        self._is_azure_sql = (
            "database.windows.net" in settings.database_url or "mssql" in settings.database_url
        ) and not settings.database_url.startswith("sqlite")
        return self._is_azure_sql

    def get_database_metrics(
        self,
        hours: int = 168,  # 1 week
    ) -> list[DatabaseMetrics]:
        """Get resource utilization metrics for all databases.

        Returns:
            List of DatabaseMetrics for each database
        """
        if not self.is_azure_sql():
            return []

        try:
            # Query resource stats from Query Store or DMVs
            query = text("""
                SELECT 
                    DB_NAME() as database_name,
                    AVG(avg_cpu_percent) as avg_cpu,
                    MAX(avg_cpu_percent) as max_cpu,
                    AVG(avg_data_io_percent) as avg_data_io,
                    MAX(avg_data_io_percent) as max_data_io,
                    AVG(avg_log_write_percent) as avg_log_write,
                    MAX(avg_log_write_percent) as max_log_write,
                    MAX(dtu_limit) as dtu_limit,
                    MAX(storage_in_megabytes) as storage_mb,
                    COUNT(*) as sample_count
                FROM sys.dm_db_resource_stats
                WHERE end_time >= DATEADD(HOUR, -:hours, GETUTCDATE())
                GROUP BY database_id
            """)

            result = self.db.execute(query, {"hours": hours}).fetchone()

            if not result:
                return []

            # For single database, return metrics for current DB
            return [
                DatabaseMetrics(
                    database_name=result.database_name,
                    avg_cpu_percent=float(result.avg_cpu),
                    max_cpu_percent=float(result.max_cpu),
                    avg_data_io_percent=float(result.avg_data_io),
                    max_data_io_percent=float(result.max_data_io),
                    avg_log_write_percent=float(result.avg_log_write),
                    max_log_write_percent=float(result.max_log_write),
                    dtu_limit=int(result.dtu_limit) if result.dtu_limit else 10,
                    storage_mb=float(result.storage_mb) if result.storage_mb else 0,
                    sample_count=int(result.sample_count),
                )
            ]

        except Exception as e:
            logger.error(f"Failed to get database metrics: {e}")
            return []

    def estimate_multi_tenant_metrics(
        self,
        database_count: int,
        peak_concurrent_ratio: float = 0.3,
        base_metrics: DatabaseMetrics | None = None,
    ) -> list[DatabaseMetrics]:
        """Estimate metrics for multiple tenant databases.

        This is used when we only have access to one database but want to
        simulate a multi-tenant scenario.

        Args:
            database_count: Number of tenant databases to simulate
            peak_concurrent_ratio: Ratio of databases at peak (0.0-1.0)
            base_metrics: Base metrics to use for simulation

        Returns:
            List of simulated DatabaseMetrics
        """
        if base_metrics is None:
            # Create default metrics for simulation
            base = DatabaseMetrics(
                database_name="tenant_template",
                avg_cpu_percent=5.0,
                max_cpu_percent=40.0,
                avg_data_io_percent=3.0,
                max_data_io_percent=25.0,
                avg_log_write_percent=2.0,
                max_log_write_percent=20.0,
                dtu_limit=20,
                storage_mb=100.0,
                sample_count=100,
            )
        else:
            base = base_metrics

        # Simulate variation across tenants
        databases = []
        peak_count = max(1, int(database_count * peak_concurrent_ratio))

        for i in range(database_count):
            # Vary the metrics slightly for each simulated tenant
            variation = 0.8 + (i % 5) * 0.1  # 0.8 to 1.2 variation

            # First 'peak_count' databases have higher utilization
            is_peak = i < peak_count
            load_factor = 1.5 if is_peak else 0.6

            databases.append(
                DatabaseMetrics(
                    database_name=f"tenant_{i+1:03d}",
                    avg_cpu_percent=min(100, base.avg_cpu_percent * variation * load_factor),
                    max_cpu_percent=min(100, base.max_cpu_percent * variation * load_factor),
                    avg_data_io_percent=min(
                        100, base.avg_data_io_percent * variation * load_factor
                    ),
                    max_data_io_percent=min(
                        100, base.max_data_io_percent * variation * load_factor
                    ),
                    avg_log_write_percent=min(
                        100, base.avg_log_write_percent * variation * load_factor
                    ),
                    max_log_write_percent=min(
                        100, base.max_log_write_percent * variation * load_factor
                    ),
                    dtu_limit=base.dtu_limit,
                    storage_mb=base.storage_mb * variation,
                    sample_count=base.sample_count,
                )
            )

        return databases

    def calculate_elastic_pool_benefit(
        self,
        databases: list[DatabaseMetrics],
    ) -> dict[str, Any]:
        """Calculate whether elastic pool would be beneficial.

        Key metrics:
        - Average utilization per database
        - Peak utilization across all databases
        - Sum of peaks vs peak of sums

        Returns:
            Analysis results
        """
        if not databases:
            return {"error": "No database metrics available"}

        # Calculate current single DB costs
        total_dtu_limit = sum(db.dtu_limit for db in databases)
        total_databases = len(databases)

        # Find matching single DB tier
        current_tier = self._find_best_single_db_tier(max(db.dtu_limit for db in databases))
        current_cost = (
            SINGLE_DB_PRICING.get(current_tier, {}).get("monthly_cost", 0) * total_databases
        )

        # Calculate aggregate metrics
        avg_cpu = sum(db.avg_cpu_percent for db in databases) / len(databases)
        max_cpu = max(db.max_cpu_percent for db in databases)

        # For elastic pool, the key insight is that peaks don't align perfectly
        # Peak of sums is typically less than sum of peaks
        peak_simultaneous = self._estimate_simultaneous_peak(databases)

        # Storage calculation
        total_storage_mb = sum(db.storage_mb for db in databases)

        # Find best elastic pool
        recommended_pool = self._find_best_elastic_pool(databases, peak_simultaneous)

        pool_config = ELASTIC_POOL_PRICING.get(recommended_pool, {})
        pool_cost = pool_config.get("monthly_cost", 0)
        pool_dtus = pool_config.get("dtus", 0)
        pool_max_dbs = pool_config.get("max_databases", 0)

        # Calculate utilization
        if pool_dtus > 0:
            # Estimate utilization based on average load
            avg_total_load = sum(db.avg_cpu_percent * db.dtu_limit / 100 for db in databases)
            pool_utilization = (avg_total_load / pool_dtus) * 100
        else:
            pool_utilization = 0

        # Savings calculation
        monthly_savings = current_cost - pool_cost
        annual_savings = monthly_savings * 12
        savings_percent = (monthly_savings / current_cost * 100) if current_cost > 0 else 0

        # Risk assessment
        risk_level = self._assess_risk(databases, pool_dtus, pool_max_dbs, pool_utilization)

        return {
            "current_setup": {
                "database_count": total_databases,
                "total_dtu_limit": total_dtu_limit,
                "single_db_tier": current_tier,
                "monthly_cost": current_cost,
            },
            "workload_analysis": {
                "average_cpu_percent": round(avg_cpu, 2),
                "peak_cpu_percent": round(max_cpu, 2),
                "estimated_simultaneous_peak": round(peak_simultaneous, 2),
                "total_storage_mb": round(total_storage_mb, 2),
                "burstiness_factor": round(
                    sum(db.max_cpu_percent for db in databases) / peak_simultaneous, 2
                ),
            },
            "elastic_pool_recommendation": {
                "pool_tier": recommended_pool,
                "pool_dtus": pool_dtus,
                "max_databases": pool_max_dbs,
                "estimated_utilization_percent": round(pool_utilization, 2),
                "monthly_cost": pool_cost,
            },
            "cost_analysis": {
                "monthly_savings": round(monthly_savings, 2),
                "annual_savings": round(annual_savings, 2),
                "savings_percent": round(savings_percent, 2),
                "breakeven_months": round(pool_cost / monthly_savings, 1)
                if monthly_savings > 0
                else None,
            },
            "risk_assessment": {
                "level": risk_level,
                "recommendation": self._recommendation_text(
                    savings_percent, risk_level, monthly_savings
                ),
            },
        }

    def _find_best_single_db_tier(self, required_dtus: int) -> str:
        """Find the best single DB tier for given DTU requirement."""
        for tier, config in sorted(SINGLE_DB_PRICING.items(), key=lambda x: x[1]["dtus"]):
            if config["dtus"] >= required_dtus:
                return tier
        return "P2"  # Highest tier as fallback

    def _estimate_simultaneous_peak(
        self,
        databases: list[DatabaseMetrics],
        correlation_factor: float = 0.6,
    ) -> float:
        """Estimate simultaneous peak across all databases.

        Uses statistical approach: peak of sums = sum of averages +
        correlation-adjusted standard deviation of peaks.
        """
        # Sum of average loads
        avg_load = sum(db.avg_cpu_percent * db.dtu_limit / 100 for db in databases)

        # Peak loads
        peak_loads = [db.max_cpu_percent * db.dtu_limit / 100 for db in databases]

        # Statistical approach: peaks don't perfectly align
        # Use correlation factor to estimate simultaneous peak
        sum_of_peaks = sum(peak_loads)
        simultaneous_peak = avg_load + (sum_of_peaks - avg_load) * correlation_factor

        return simultaneous_peak

    def _find_best_elastic_pool(
        self,
        databases: list[DatabaseMetrics],
        required_dtus: float,
    ) -> str:
        """Find the best elastic pool tier for the workload."""
        database_count = len(databases)

        # Add 30% headroom for growth and burst
        required_with_headroom = required_dtus * 1.3

        for pool_name, config in ELASTIC_POOL_PRICING.items():
            if (
                config["dtus"] >= required_with_headroom
                and config["max_databases"] >= database_count
            ):
                return pool_name

        # Return largest if nothing fits
        return "Standard_3000"

    def _assess_risk(
        self,
        databases: list[DatabaseMetrics],
        pool_dtus: int,
        pool_max_dbs: int,
        pool_utilization: float,
    ) -> str:
        """Assess risk level of elastic pool recommendation."""
        risks = []

        # Check database count
        if len(databases) > pool_max_dbs:
            risks.append("Database count exceeds pool maximum")

        # Check peak utilization
        max_peak = max(db.max_cpu_percent * db.dtu_limit / 100 for db in databases)
        if max_peak > pool_dtus:
            risks.append("Single database peak exceeds pool DTUs")

        # Check average utilization
        if pool_utilization > 80:
            risks.append("High average utilization")
        elif pool_utilization > 60:
            risks.append("Moderate utilization")

        # Check burstiness
        burstiness = sum(db.max_cpu_percent for db in databases) / (
            sum(db.avg_cpu_percent for db in databases) or 1
        )
        if burstiness > 5:
            risks.append("Very bursty workload")
        elif burstiness > 3:
            risks.append("Bursty workload")

        if "Single database peak exceeds pool DTUs" in risks or len(databases) > pool_max_dbs:
            return "HIGH"
        elif risks:
            return "MEDIUM"
        else:
            return "LOW"

    def _recommendation_text(
        self,
        savings_percent: float,
        risk_level: str,
        monthly_savings: float,
    ) -> str:
        """Generate recommendation text."""
        if risk_level == "HIGH":
            return (
                "NOT RECOMMENDED: Risk factors present. "
                "Consider Premium tier or stay with single databases."
            )
        elif savings_percent < 10:
            return (
                "NOT RECOMMENDED: Savings insufficient (< 10%). "
                "Stay with single databases for simplicity."
            )
        elif risk_level == "MEDIUM":
            return (
                "CONDITIONALLY RECOMMENDED: Acceptable savings with moderate risk. "
                "Monitor closely if implemented."
            )
        elif savings_percent >= 20 and monthly_savings > 100:
            return (
                "STRONGLY RECOMMENDED: Significant savings with low risk. "
                "Elastic pool is a good fit for this workload."
            )
        else:
            return (
                "RECOMMENDED: Modest savings with low risk. "
                "Consider elastic pool for operational simplicity."
            )

    def print_analysis(self, analysis: dict[str, Any]) -> None:
        """Print formatted analysis results."""
        print("\n" + "=" * 80)
        print("AZURE SQL ELASTIC POOL EVALUATION")
        print("=" * 80)

        if "error" in analysis:
            print(f"\n❌ Error: {analysis['error']}")
            return

        # Current setup
        current = analysis["current_setup"]
        print("\n📊 Current Setup:")
        print(f"   Database Count: {current['database_count']}")
        print(f"   Single DB Tier: {current['single_db_tier']}")
        print(f"   Total DTU Limit: {current['total_dtu_limit']}")
        print(f"   Monthly Cost: ${current['monthly_cost']:.2f}")

        # Workload analysis
        workload = analysis["workload_analysis"]
        print("\n📈 Workload Analysis:")
        print(f"   Average CPU: {workload['average_cpu_percent']:.1f}%")
        print(f"   Peak CPU: {workload['peak_cpu_percent']:.1f}%")
        print(f"   Simultaneous Peak: {workload['estimated_simultaneous_peak']:.1f} DTUs")
        print(f"   Total Storage: {workload['total_storage_mb']:.1f} MB")
        print(f"   Burstiness Factor: {workload['burstiness_factor']:.2f}x")

        # Elastic pool recommendation
        pool = analysis["elastic_pool_recommendation"]
        print("\n💧 Recommended Elastic Pool:")
        print(f"   Tier: {pool['pool_tier']}")
        print(f"   DTUs: {pool['pool_dtus']}")
        print(f"   Max Databases: {pool['max_databases']}")
        print(f"   Estimated Utilization: {pool['estimated_utilization_percent']:.1f}%")
        print(f"   Monthly Cost: ${pool['monthly_cost']:.2f}")

        # Cost analysis
        cost = analysis["cost_analysis"]
        print("\n💰 Cost Analysis:")
        print(f"   Monthly Savings: ${cost['monthly_savings']:.2f}")
        print(f"   Annual Savings: ${cost['annual_savings']:.2f}")
        print(f"   Savings Percent: {cost['savings_percent']:.1f}%")
        if cost["breakeven_months"]:
            print(f"   Breakeven: {cost['breakeven_months']} months")

        # Risk assessment
        risk = analysis["risk_assessment"]
        risk_icon = "🔴" if risk["level"] == "HIGH" else "🟡" if risk["level"] == "MEDIUM" else "🟢"
        print(f"\n{risk_icon} Risk Assessment ({risk['level']}):")
        print(f"   {risk['recommendation']}")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate Azure SQL Elastic Pool suitability",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze current database
  %(prog)s --analyze

  # Cost comparison for 20 databases at S2 tier
  %(prog)s --cost-comparison --databases 20 --dtu-tier S2

  # Full recommendation with output
  %(prog)s --recommend --databases 50 --output recommendation.json

  # Custom simulation parameters
  %(prog)s --simulate --databases 30 --peak-ratio 0.25 --base-tier S1
        """,
    )

    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Analyze current database metrics",
    )
    parser.add_argument(
        "--cost-comparison",
        action="store_true",
        help="Run cost comparison analysis",
    )
    parser.add_argument(
        "--recommend",
        action="store_true",
        help="Generate full recommendation",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Use simulation mode (for multi-tenant planning)",
    )

    # Simulation parameters
    parser.add_argument(
        "--databases",
        type=int,
        default=10,
        help="Number of databases to simulate (default: 10)",
    )
    parser.add_argument(
        "--dtu-tier",
        type=str,
        default="S2",
        choices=list(SINGLE_DB_PRICING.keys()),
        help="Single DB tier for comparison (default: S2)",
    )
    parser.add_argument(
        "--peak-ratio",
        type=float,
        default=0.3,
        help="Ratio of databases at peak (0.0-1.0, default: 0.3)",
    )
    parser.add_argument(
        "--base-tier",
        type=str,
        default="S1",
        choices=list(SINGLE_DB_PRICING.keys()),
        help="Base tier for simulation (default: S1)",
    )

    # Output
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for JSON results",
    )

    args = parser.parse_args()

    # If no action specified, show help
    if not any([args.analyze, args.cost_comparison, args.recommend]):
        parser.print_help()
        sys.exit(0)

    # Initialize
    print("\n🔌 Initializing...")
    db = SessionLocal()

    try:
        evaluator = ElasticPoolEvaluator(db)

        if not evaluator.is_azure_sql():
            print("\n⚠️  Not connected to Azure SQL. Using simulation mode.\n")
            args.simulate = True

        # Get metrics
        if args.simulate or not evaluator.is_azure_sql():
            # Use simulation
            base_dtu = SINGLE_DB_PRICING[args.base_tier]["dtus"]
            base_metrics = DatabaseMetrics(
                database_name="simulated",
                avg_cpu_percent=15.0,
                max_cpu_percent=60.0,
                avg_data_io_percent=10.0,
                max_data_io_percent=40.0,
                avg_log_write_percent=5.0,
                max_log_write_percent=25.0,
                dtu_limit=base_dtu,
                storage_mb=500.0,
                sample_count=168,
            )
            databases = evaluator.estimate_multi_tenant_metrics(
                database_count=args.databases,
                peak_concurrent_ratio=args.peak_ratio,
                base_metrics=base_metrics,
            )
        else:
            # Use actual metrics
            databases = evaluator.get_database_metrics(hours=168)
            if not databases:
                print("\n⚠️  Could not retrieve database metrics. Using simulation.")
                databases = evaluator.estimate_multi_tenant_metrics(
                    database_count=args.databases,
                    peak_concurrent_ratio=args.peak_ratio,
                )

        # Override DTU tier if specified
        if args.dtu_tier:
            target_dtu = SINGLE_DB_PRICING[args.dtu_tier]["dtus"]
            for db_metrics in databases:
                db_metrics.dtu_limit = target_dtu

        # Run analysis
        analysis = evaluator.calculate_elastic_pool_benefit(databases)

        # Print results
        evaluator.print_analysis(analysis)

        # Save output if requested
        if args.output:
            with open(args.output, "w") as f:
                json.dump(analysis, f, indent=2, default=str)
            print(f"\n💾 Results saved to: {args.output}")

        # Additional simulation details if applicable
        if args.simulate:
            print("\n📝 Simulation Details:")
            print(f"   Databases: {args.databases}")
            print(f"   Peak Concurrent Ratio: {args.peak_ratio}")
            print(f"   Base Tier: {args.base_tier}")
            print("\n   Note: Simulation uses estimated metrics. For accurate analysis,")
            print("   run against an actual Azure SQL database with representative load.")

        print("\n" + "=" * 80)
        print("Evaluation complete! 🎉")
        print("=" * 80 + "\n")

    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
