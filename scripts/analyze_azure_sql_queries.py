#!/usr/bin/env python3
"""Azure SQL Query Store analysis script.

Analyzes Query Store data to identify:
- Slow queries needing optimization
- Missing indexes based on Query Store recommendations
- N+1 query patterns
- Query optimization opportunities

Usage:
    python scripts/analyze_azure_sql_queries.py --help
    python scripts/analyze_azure_sql_queries.py --slow-threshold 500
    python scripts/analyze_azure_sql_queries.py --recommend-indexes
    python scripts/analyze_azure_sql_queries.py --analyze-n1

Environment:
    Requires DATABASE_URL environment variable set to Azure SQL connection string.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.azure_sql_monitoring import AzureSQLMonitor
from app.core.config import get_settings
from app.core.database import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def analyze_slow_queries(
    monitor: AzureSQLMonitor,
    threshold_ms: float,
    top_n: int,
) -> None:
    """Analyze and report slow queries from Query Store."""
    print("\n" + "=" * 80)
    print(f"SLOW QUERY ANALYSIS (threshold: {threshold_ms}ms)")
    print("=" * 80)

    slow_queries = monitor.get_slow_queries(
        threshold_ms=threshold_ms,
        time_window_hours=24,
    )

    if not slow_queries:
        print("\n✅ No slow queries detected above threshold!")
        return

    print(f"\n⚠️  Found {len(slow_queries)} slow queries:\n")

    for i, query in enumerate(slow_queries[:top_n], 1):
        print(f"  {i}. Query ID: {query.query_id} | Plan ID: {query.plan_id}")
        print(f"     Avg Duration: {query.avg_duration_ms:.2f}ms")
        print(f"     Total Duration: {query.total_duration_ms:.2f}ms")
        print(f"     Execution Count: {query.execution_count:,}")
        print(f"     Avg CPU: {query.avg_cpu_time_ms:.2f}ms")
        print(
            f"     IO Reads: {query.avg_logical_io_reads:,} | Writes: {query.avg_logical_io_writes:,}"
        )
        print(f"     Last Executed: {query.last_execution_time}")
        print(f"     Query Preview: {query.query_text[:150]}...")
        print()


def recommend_indexes(monitor: AzureSQLMonitor, min_improvement: float) -> None:
    """Recommend indexes based on Query Store and missing index DMVs."""
    print("\n" + "=" * 80)
    print("INDEX RECOMMENDATIONS")
    print("=" * 80)

    missing_indexes = monitor.get_missing_indexes()

    if not missing_indexes:
        print("\n✅ No missing indexes detected!")
        return

    # Filter by improvement measure
    significant = [idx for idx in missing_indexes if idx["improvement_measure"] >= min_improvement]

    if not significant:
        print(f"\nℹ️  No indexes with improvement measure >= {min_improvement}")
        print(
            f"   (Best available: {max(idx['improvement_measure'] for idx in missing_indexes):.2f})"
        )
        return

    print(f"\n📊 Found {len(significant)} significant index recommendations:\n")

    for i, idx in enumerate(significant[:20], 1):
        print(f"  {i}. Table: {idx['table']}")
        print(
            f"     Improvement: {idx['improvement_measure']:.2f} (impact: {idx['improvement_percent']:.1f}%)"
        )
        print(f"     User Seeks: {idx['user_seeks']:,} | Scans: {idx['user_scans']:,}")

        if idx["equality_columns"]:
            print(f"     Equality Columns: {idx['equality_columns']}")
        if idx["inequality_columns"]:
            print(f"     Inequality Columns: {idx['inequality_columns']}")
        if idx["included_columns"]:
            print(f"     Included Columns: {idx['included_columns']}")

        # Generate CREATE INDEX statement
        index_name = f"IX_{idx['table']}_{'_'.join(idx['equality_columns'].split(', ')[:2]) if idx['equality_columns'] else 'RECOMMENDED'}"
        print("     📝 Suggested SQL:")
        print(f"        CREATE INDEX [{index_name}] ON [{idx['table']}]")
        print(f"        ({idx['equality_columns'] or idx['inequality_columns']})")
        if idx["included_columns"]:
            print(f"        INCLUDE ({idx['included_columns']});")
        else:
            print("        ;")
        print()


def analyze_n1_patterns(monitor: AzureSQLMonitor) -> None:
    """Analyze and report potential N+1 query patterns."""
    print("\n" + "=" * 80)
    print("N+1 QUERY PATTERN ANALYSIS")
    print("=" * 80)

    candidates = monitor.get_n1_query_candidates()

    if not candidates:
        print("\n✅ No N+1 query patterns detected!")
        return

    print(f"\n🔄 Found {len(candidates)} potential N+1 patterns:\n")

    for i, candidate in enumerate(candidates, 1):
        print(f"  {i}. Query ID: {candidate['query_id']}")
        print(f"     Pattern: {candidate['suspected_pattern']}")
        print(f"     Execution Count: {candidate['execution_count']:,}")
        print(f"     Avg Duration: {candidate['avg_duration_ms']:.2f}ms")
        print(f"     Plan Variations: {candidate['plan_count']}")
        print(f"     Query Preview: {candidate['query_preview']}")
        print()

    print("💡 Recommendations:")
    print("   - Use joinedload() for eagerly loading relationships")
    print("   - Use selectinload() for many-to-one relationships")
    print("   - Consider bulk operations instead of loops")
    print("   - Review ORM usage patterns in application code")
    print()


def generate_full_report(monitor: AzureSQLMonitor, output_file: str | None) -> None:
    """Generate and save comprehensive report."""
    print("\n" + "=" * 80)
    print("GENERATING FULL AZURE SQL REPORT")
    print("=" * 80)

    report = monitor.get_full_report()

    # Print summary
    print("\n📈 Report Summary:")
    print(f"   Query Store Enabled: {report['query_store_enabled']}")
    print(f"   Generation Time: {report['generation_time_ms']:.2f}ms")

    if report["dtu_metrics"]:
        dtu = report["dtu_metrics"]
        print("\n   DTU Metrics:")
        print(f"      CPU: {dtu.avg_cpu_percent:.1f}%")
        print(f"      Data IO: {dtu.avg_data_io_percent:.1f}%")
        print(f"      Log Write: {dtu.avg_log_write_percent:.1f}%")
        print(f"      Memory: {dtu.avg_memory_usage_percent:.1f}%")

    if report["pool_metrics"]:
        pool = report["pool_metrics"]
        print("\n   Pool Metrics:")
        print(f"      Utilization: {pool.utilization_percent:.1f}%")
        print(f"      Checked Out: {pool.checked_out}")
        print(f"      Pool Size: {pool.pool_size}")

    if report["recommendations"]:
        print(f"\n⚠️  Recommendations ({len(report['recommendations'])}):")
        for rec in report["recommendations"]:
            print(f"      - {rec}")
    else:
        print("\n✅ No immediate recommendations")

    # Save to file if requested
    if output_file:
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\n💾 Report saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Azure SQL Query Store and provide optimization recommendations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --slow-queries --threshold 1000 --top 20
  %(prog)s --recommend-indexes --min-improvement 1000
  %(prog)s --analyze-n1
  %(prog)s --full-report --output report.json
  %(prog)s --all  # Run all analyses
        """,
    )

    parser.add_argument(
        "--slow-queries",
        action="store_true",
        help="Analyze slow queries from Query Store",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=500,
        help="Slow query threshold in milliseconds (default: 500)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of top queries to show (default: 10)",
    )
    parser.add_argument(
        "--recommend-indexes",
        action="store_true",
        help="Recommend indexes based on Query Store",
    )
    parser.add_argument(
        "--min-improvement",
        type=float,
        default=1000,
        help="Minimum improvement measure for index recommendations (default: 1000)",
    )
    parser.add_argument(
        "--analyze-n1",
        action="store_true",
        help="Analyze N+1 query patterns",
    )
    parser.add_argument(
        "--full-report",
        action="store_true",
        help="Generate comprehensive report",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for JSON report",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all analyses",
    )

    args = parser.parse_args()

    # If no specific analysis requested, show help
    if not any(
        [
            args.slow_queries,
            args.recommend_indexes,
            args.analyze_n1,
            args.full_report,
            args.all,
        ]
    ):
        parser.print_help()
        sys.exit(0)

    # Check environment
    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        print("\n⚠️  Warning: SQLite detected. Query Store features only available on Azure SQL.")
        print("   Only connection pool metrics will be available.")

    # Initialize database session
    print("\n🔌 Connecting to database...")
    db = SessionLocal()

    try:
        monitor = AzureSQLMonitor(db)

        # Check Query Store
        if not monitor.is_query_store_enabled() and not settings.database_url.startswith("sqlite"):
            print("\n⚠️  Query Store is not enabled for this database!")
            print("   Enable it with:")
            print("   ALTER DATABASE CURRENT SET QUERY_STORE = ON;")
            print("   ALTER DATABASE CURRENT SET QUERY_STORE (OPERATION_MODE = READ_WRITE);")
            print()

        # Run requested analyses
        if args.all:
            args.slow_queries = True
            args.recommend_indexes = True
            args.analyze_n1 = True
            args.full_report = True

        if args.slow_queries:
            analyze_slow_queries(monitor, args.threshold, args.top)

        if args.recommend_indexes:
            recommend_indexes(monitor, args.min_improvement)

        if args.analyze_n1:
            analyze_n1_patterns(monitor)

        if args.full_report:
            generate_full_report(monitor, args.output)

        print("\n" + "=" * 80)
        print("Analysis complete! 🎉")
        print("=" * 80 + "\n")

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
