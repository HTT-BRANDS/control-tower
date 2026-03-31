#!/usr/bin/env python3
"""Benchmark database query performance before/after adding indexes.

This script measures query execution time for common query patterns
to validate the performance improvement from adding indexes.

Usage:
    python scripts/benchmark_indexes.py --iterations 100
    python scripts/benchmark_indexes.py --output results.json

"""

import argparse
import json
import logging
import statistics
import sys
import time
from datetime import UTC, datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Benchmark database query performance")
    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="Number of iterations per query (default: 100)",
    )
    parser.add_argument(
        "--output",
        help="Output results to JSON file",
    )
    parser.add_argument(
        "--tenant-id",
        help="Specific tenant ID to query (uses random if not specified)",
    )
    return parser.parse_args()


def benchmark_query(db, query_func, iterations: int = 100) -> dict:
    """Benchmark a query function and return statistics."""
    times = []

    for _ in range(iterations):
        start = time.perf_counter()
        query_func(db)
        end = time.perf_counter()
        times.append((end - start) * 1000)  # Convert to milliseconds

    return {
        "min_ms": round(min(times), 2),
        "max_ms": round(max(times), 2),
        "mean_ms": round(statistics.mean(times), 2),
        "median_ms": round(statistics.median(times), 2),
        "stdev_ms": round(statistics.stdev(times), 2) if len(times) > 1 else 0,
        "iterations": iterations,
    }


def benchmark_sync_jobs_by_tenant(db, tenant_id: str | None = None):
    """Benchmark: Query sync jobs by tenant_id."""
    from sqlalchemy import text

    sql = text("""
        SELECT id, job_type, status, started_at, completed_at
        FROM sync_jobs
        WHERE tenant_id = :tenant_id
        ORDER BY started_at DESC
        LIMIT 100
    """)
    result = db.execute(sql, {"tenant_id": tenant_id or "test-tenant-id"})
    list(result)  # Consume results


def benchmark_sync_jobs_recent(db):
    """Benchmark: Query recent sync jobs."""
    from sqlalchemy import text

    since = datetime.now(UTC) - timedelta(days=7)
    sql = text("""
        SELECT id, job_type, status, started_at
        FROM sync_jobs
        WHERE started_at > :since
        ORDER BY started_at DESC
        LIMIT 50
    """)
    result = db.execute(sql, {"since": since})
    list(result)


def benchmark_recommendations_by_tenant(db, tenant_id: str | None = None):
    """Benchmark: Query recommendations by tenant."""
    from sqlalchemy import text

    sql = text("""
        SELECT id, title, impact, status, created_at
        FROM recommendations
        WHERE tenant_id = :tenant_id
        ORDER BY created_at DESC
        LIMIT 50
    """)
    result = db.execute(sql, {"tenant_id": tenant_id or "test-tenant-id"})
    list(result)


def benchmark_monitoring_alerts_active(db, tenant_id: str | None = None):
    """Benchmark: Query active monitoring alerts."""
    from sqlalchemy import text

    sql = text("""
        SELECT id, severity, message, status, created_at
        FROM monitoring_alerts
        WHERE tenant_id = :tenant_id
        AND status = 'active'
        ORDER BY created_at DESC
        LIMIT 50
    """)
    result = db.execute(sql, {"tenant_id": tenant_id or "test-tenant-id"})
    list(result)


def benchmark_budgets_by_tenant(db, tenant_id: str | None = None):
    """Benchmark: Query budgets by tenant."""
    from sqlalchemy import text

    sql = text("""
        SELECT id, name, amount, current_spend, alert_threshold
        FROM budgets
        WHERE tenant_id = :tenant_id
        ORDER BY created_at DESC
        LIMIT 20
    """)
    result = db.execute(sql, {"tenant_id": tenant_id or "test-tenant-id"})
    list(result)


def benchmark_cost_data_by_date_range(db, tenant_id: str | None = None):
    """Benchmark: Query cost data by date range."""
    from sqlalchemy import text

    start_date = datetime.now(UTC) - timedelta(days=30)
    end_date = datetime.now(UTC)

    sql = text("""
        SELECT id, service_name, cost, usage_date
        FROM cost_data
        WHERE tenant_id = :tenant_id
        AND usage_date BETWEEN :start_date AND :end_date
        ORDER BY usage_date DESC
        LIMIT 100
    """)
    result = db.execute(
        sql,
        {
            "tenant_id": tenant_id or "test-tenant-id",
            "start_date": start_date,
            "end_date": end_date,
        },
    )
    list(result)


def benchmark_resources_by_tenant(db, tenant_id: str | None = None):
    """Benchmark: Query resources by tenant."""
    from sqlalchemy import text

    sql = text("""
        SELECT id, name, type, status, resource_group
        FROM resources
        WHERE tenant_id = :tenant_id
        ORDER BY name
        LIMIT 100
    """)
    result = db.execute(sql, {"tenant_id": tenant_id or "test-tenant-id"})
    list(result)


def get_existing_indexes(db) -> dict:
    """Get list of existing indexes for relevant tables."""
    from sqlalchemy import inspect

    insp = inspect(db.bind)
    tables = [
        "sync_jobs",
        "recommendations",
        "monitoring_alerts",
        "budgets",
        "cost_data",
        "resources",
        "compliance_scores",
        "subscriptions",
        "backfill_jobs",
    ]

    indexes = {}
    for table in tables:
        try:
            table_indexes = insp.get_indexes(table)
            indexes[table] = [idx["name"] for idx in table_indexes]
        except Exception:
            indexes[table] = []

    return indexes


def main() -> int:
    """Main entry point."""
    args = parse_args()

    try:
        from app.core.database import SessionLocal
    except ImportError:
        logger.error("Could not import SessionLocal. Make sure you're in the project root.")
        return 1

    results = {
        "timestamp": datetime.now(UTC).isoformat(),
        "iterations": args.iterations,
        "queries": {},
    }

    logger.info(f"Starting benchmark with {args.iterations} iterations per query")

    try:
        db = SessionLocal()

        # Get existing indexes
        results["existing_indexes"] = get_existing_indexes(db)

        # Define benchmark queries
        benchmarks = {
            "sync_jobs_by_tenant": lambda db: benchmark_sync_jobs_by_tenant(db, args.tenant_id),
            "sync_jobs_recent": benchmark_sync_jobs_recent,
            "recommendations_by_tenant": lambda db: benchmark_recommendations_by_tenant(
                db, args.tenant_id
            ),
            "monitoring_alerts_active": lambda db: benchmark_monitoring_alerts_active(
                db, args.tenant_id
            ),
            "budgets_by_tenant": lambda db: benchmark_budgets_by_tenant(db, args.tenant_id),
            "cost_data_by_date_range": lambda db: benchmark_cost_data_by_date_range(
                db, args.tenant_id
            ),
            "resources_by_tenant": lambda db: benchmark_resources_by_tenant(db, args.tenant_id),
        }

        # Run benchmarks
        for name, query_func in benchmarks.items():
            logger.info(f"Benchmarking: {name}...")
            try:
                stats = benchmark_query(db, query_func, args.iterations)
                results["queries"][name] = stats
                logger.info(
                    f"  Mean: {stats['mean_ms']:.2f}ms, "
                    f"Median: {stats['median_ms']:.2f}ms, "
                    f"Min: {stats['min_ms']:.2f}ms, "
                    f"Max: {stats['max_ms']:.2f}ms"
                )
            except Exception as e:
                logger.error(f"  Failed: {e}")
                results["queries"][name] = {"error": str(e)}

        db.close()

        # Output results
        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            logger.info(f"Results saved to {args.output}")
        else:
            print(json.dumps(results, indent=2))

        return 0

    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
