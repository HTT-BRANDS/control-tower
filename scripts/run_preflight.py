#!/usr/bin/env python3
"""Standalone CLI script for running preflight checks.

This script can be used for CI/CD integration, manual testing, or
automated health checks. It supports multiple output formats and
exit codes for integration with automation systems.

Usage:
    python scripts/run_preflight.py [options]

Options:
    --json           Output results in JSON format
    --markdown       Output results in Markdown format
    --fail-fast      Stop on first failure
    --category CATEGORY   Run only specific category (can be repeated)
    --tenant TENANT_ID    Run only for specific tenant
    --timeout SECONDS     Timeout for each check (default: 30)
    --no-cache       Don't cache results between runs
    --quiet          Suppress non-JSON output
    --help           Show this help message

Exit Codes:
    0   All checks passed
    1   One or more checks failed
    2   Invalid arguments or internal error
    3   Checks are already running

Examples:
    # Run all checks and output JSON
    python scripts/run_preflight.py --json

    # Run with fail-fast and markdown output
    python scripts/run_preflight.py --fail-fast --markdown

    # Run only Azure-related checks
    python scripts/run_preflight.py --category azure_auth --category azure_subscriptions

    # Check specific tenant
    python scripts/run_preflight.py --tenant 00000000-0000-0000-0000-000000000000
"""

import argparse
import asyncio
import json
import logging
import sys

# Add the parent directory to the path for imports
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])

from app.preflight.models import (
    CheckCategory,
    PreflightCheckRequest,
)
from app.preflight.reports import ReportGenerator
from app.preflight.runner import PreflightRunner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_categories(category_args: list[str]) -> list[CheckCategory] | None:
    """Parse category arguments into CheckCategory enums."""
    if not category_args:
        return None

    categories = []
    for cat_str in category_args:
        try:
            # Handle case-insensitive matching
            cat_str.upper()
            category = CheckCategory(_cat_lower := cat_str.lower())
            categories.append(category)
        except ValueError:
            valid_categories = [c.value for c in CheckCategory]
            print(
                f"Error: Invalid category '{cat_str}'. Valid categories: {valid_categories}",
                file=sys.stderr,
            )
            sys.exit(2)

    return categories


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run preflight checks for Azure Governance Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format",
    )

    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Output results in Markdown format",
    )

    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first failure",
    )

    parser.add_argument(
        "--category",
        action="append",
        dest="categories",
        help="Run only specific category (can be repeated)",
    )

    parser.add_argument(
        "--tenant",
        action="append",
        dest="tenants",
        help="Run only for specific tenant",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Timeout for each check in seconds (default: 30)",
    )

    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Don't cache results between runs",
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress non-JSON output",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


async def run_preflight(args: argparse.Namespace) -> PreflightRunner:
    """Run preflight checks with the given arguments."""
    categories = parse_categories(args.categories) if args.categories else None

    # Create request
    request = PreflightCheckRequest(
        categories=categories,
        tenant_ids=args.tenants,
        fail_fast=args.fail_fast,
        timeout_seconds=args.timeout,
    )

    # Create runner
    runner = PreflightRunner(
        categories=request.categories,
        tenant_ids=request.tenant_ids,
        fail_fast=request.fail_fast,
        timeout_seconds=request.timeout_seconds,
    )

    if args.no_cache:
        runner.clear_all_caches()

    logger.info(
        f"Running preflight checks: categories={categories}, "
        f"tenants={args.tenants}, fail_fast={args.fail_fast}"
    )

    # Run checks
    await runner.run_checks(
        categories=categories,
        tenant_ids=args.tenants,
    )

    return runner


def print_results(
    runner: PreflightRunner,
    args: argparse.Namespace,
) -> int:
    """Print results and return exit code."""
    report = runner.current_report

    if args.json:
        generator = ReportGenerator(report)
        print(generator.to_json())
    elif args.markdown:
        generator = ReportGenerator(report)
        print(generator.to_markdown())
    else:
        # Human-readable output
        summary = report.get_summary()

        if not args.quiet:
            print("\n" + "=" * 60)
            print("PREFLIGHT CHECK RESULTS")
            print("=" * 60)
            print(f"Report ID: {summary['id']}")
            print(f"Started: {summary['started_at']}")
            print(f"Completed: {summary['completed_at']}")
            print(f"Duration: {summary['duration_ms']:.2f}ms")
            print()
            print(f"✅ Passed: {summary['passed']}")
            print(f"⚠️  Warnings: {summary['warnings']}")
            print(f"❌ Failed: {summary['failed']}")
            print(f"⏭️  Skipped: {summary['skipped']}")
            print(f"📊 Total: {summary['total']}")
            print()

            if summary["is_success"]:
                print("✅ All checks passed!")
            else:
                print("❌ Some checks failed!")
                print("\nFailed checks:")

                for result in report.get_failed_checks():
                    print(f"  - {result.name}: {result.message}")
                    if result.recommendations:
                        print("    Recommendations:")
                        for rec in result.recommendations:
                            print(f"      - {rec}")

        # Print JSON summary if not quiet
        if not args.quiet:
            print("\n" + "-" * 60)
            print("JSON Summary:")
            print(json.dumps(summary, indent=2))

    # Return exit code
    if report.is_success:
        return 0
    else:
        return 1


async def async_main() -> int:
    """Async main entry point."""
    args = parse_arguments()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        runner = await run_preflight(args)
        return print_results(runner, args)

    except KeyboardInterrupt:
        print("\nPreflight checks interrupted by user", file=sys.stderr)
        return 2

    except Exception as e:
        print(f"Error running preflight checks: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 2


def main() -> int:
    """Main entry point."""
    return asyncio.run(async_main())


if __name__ == "__main__":
    sys.exit(main())
