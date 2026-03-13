#!/usr/bin/env python3
"""CLI for backfill operations.

Commands:
- run: Start a new backfill
- resume: Resume a paused/failed backfill
- list: List all backfill jobs
- status: Show job status
- cancel: Cancel a running job

Usage:
    python scripts/run_backfill.py run --tenant tenant-id --type costs --months 6
    python scripts/run_backfill.py resume --job-id abc-123
    python scripts/run_backfill.py list --tenant tenant-id
    python scripts/run_backfill.py status --job-id abc-123
    python scripts/run_backfill.py cancel --job-id abc-123
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import get_db_context
from app.models.backfill_job import BackfillStatus
from app.services.backfill_service import ResumableBackfillService

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ANSI color codes for terminal output
COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "magenta": "\033[95m",
    "cyan": "\033[96m",
}


def colorize(text: str, color: str) -> str:
    """Add color to text if terminal supports it."""
    if sys.stdout.isatty():
        return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"
    return text


def status_color(status: str) -> str:
    """Get color for status."""
    colors = {
        BackfillStatus.PENDING.value: "yellow",
        BackfillStatus.RUNNING.value: "blue",
        BackfillStatus.PAUSED.value: "cyan",
        BackfillStatus.COMPLETED.value: "green",
        BackfillStatus.FAILED.value: "red",
        BackfillStatus.CANCELLED.value: "magenta",
    }
    return colors.get(status, "reset")


def print_progress_bar(progress: float, width: int = 50) -> str:
    """Create a progress bar string."""
    filled = int(width * progress / 100)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {progress:.1f}%"


def format_duration(seconds: float | None) -> str:
    """Format duration in human readable form."""
    if seconds is None:
        return "N/A"

    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    else:
        return f"{seconds / 3600:.1f}h"


def format_datetime(dt: datetime | None) -> str:
    """Format datetime for display."""
    if dt is None:
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def cmd_run(args: argparse.Namespace) -> int:
    """Handle run command."""
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30 * args.months)

    logger.info(f"Starting backfill for {args.type}")
    logger.info(f"Date range: {start_date.date()} to {end_date.date()}")
    logger.info(f"Tenant: {args.tenant or 'All tenants'}")
    logger.info(f"Batch size: {args.batch_size}")

    try:
        with get_db_context() as db:
            service = ResumableBackfillService(db)

            # Create job
            job = service.create_job(
                job_type=args.type,
                tenant_id=args.tenant,
                start_date=start_date,
                end_date=end_date,
            )

            print(f"\n{colorize('Created backfill job:', 'bold')}")
            print(f"  Job ID: {colorize(job.id, 'cyan')}")
            print(f"  Type: {args.type}")
            print(f"  Start: {start_date.date()}")
            print(f"  End: {end_date.date()}")
            print(f"  Status: {colorize(job.status, status_color(job.status))}")
            print()

            if args.dry_run:
                print(colorize("Dry run mode - not executing job", "yellow"))
                return 0

            # Run the job
            print(colorize("Running backfill...", "blue"))
            print()

            job = service.run_job(
                job_id=job.id,
                batch_size=args.batch_size,
                day_by_day=not args.sequential,
            )

            # Show results
            print(f"\n{colorize('Backfill completed:', 'bold')}")
            print(f"  Status: {colorize(job.status, status_color(job.status))}")
            print(f"  Records processed: {job.records_processed}")
            print(f"  Records inserted: {job.records_inserted}")
            print(f"  Records failed: {job.records_failed}")
            print(f"  Duration: {format_duration(job.duration_seconds)}")

            if job.last_error:
                print(f"\n{colorize('Last error:', 'red')} {job.last_error}")

            return 0 if job.is_completed else 1

    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        return 1


def cmd_resume(args: argparse.Namespace) -> int:
    """Handle resume command."""
    logger.info(f"Resuming backfill job {args.job_id}")

    try:
        with get_db_context() as db:
            service = ResumableBackfillService(db)

            job = service.get_job(args.job_id)
            if not job:
                print(colorize(f"Job {args.job_id} not found", "red"))
                return 1

            print(f"Resuming job {colorize(job.id, 'cyan')}...")
            print(f"  Current date: {job.current_date or 'Not started'}")
            print(f"  Progress: {print_progress_bar(job.progress_percent)}")
            print()

            job = service.resume_job(args.job_id, batch_size=args.batch_size)

            print(f"\n{colorize('Resume completed:', 'bold')}")
            print(f"  Status: {colorize(job.status, status_color(job.status))}")
            print(f"  Records processed: {job.records_processed}")
            print(f"  Records inserted: {job.records_inserted}")
            print(f"  Duration: {format_duration(job.duration_seconds)}")

            return 0 if job.is_completed else 1

    except Exception as e:
        logger.error(f"Resume failed: {e}")
        return 1


def cmd_list(args: argparse.Namespace) -> int:
    """Handle list command."""
    try:
        with get_db_context() as db:
            service = ResumableBackfillService(db)

            jobs = service.list_jobs(
                tenant_id=args.tenant,
                job_type=args.type,
                status=args.status,
            )

            if not jobs:
                print("No jobs found")
                return 0

            print(f"\n{colorize('Backfill Jobs:', 'bold')}")
            print("-" * 100)
            print(
                f"{'ID':<36} {'Type':<12} {'Status':<12} {'Progress':<15} "
                f"{'Processed':<10} {'Inserted':<10} {'Tenant':<20}"
            )
            print("-" * 100)

            for job in jobs:
                status_colored = colorize(job.status, status_color(job.status))
                progress = f"{job.progress_percent:.1f}%"
                tenant = (job.tenant_id or "all")[:20]
                print(
                    f"{job.id:<36} {job.job_type:<12} {status_colored:<20} "
                    f"{progress:<15} {job.records_processed:<10} "
                    f"{job.records_inserted:<10} {tenant:<20}"
                )

            print("-" * 100)
            print(f"Total: {len(jobs)} job(s)")

            return 0

    except Exception as e:
        logger.error(f"List failed: {e}")
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    """Handle status command."""
    try:
        with get_db_context() as db:
            service = ResumableBackfillService(db)

            job = service.get_job(args.job_id)
            if not job:
                print(colorize(f"Job {args.job_id} not found", "red"))
                return 1

            print(f"\n{colorize('Backfill Job Details:', 'bold')}")
            print("-" * 50)
            print(f"  Job ID:        {colorize(job.id, 'cyan')}")
            print(f"  Type:          {job.job_type}")
            print(f"  Status:        {colorize(job.status, status_color(job.status))}")
            print(f"  Progress:      {print_progress_bar(job.progress_percent)}")
            print()
            print("  Date Range:")
            print(f"    Start:       {job.start_date.date()}")
            print(f"    End:         {job.end_date.date()}")
            print(f"    Current:     {job.current_date.date() if job.current_date else 'N/A'}")
            print()
            print("  Records:")
            print(f"    Processed:   {job.records_processed}")
            print(f"    Inserted:    {job.records_inserted}")
            print(f"    Failed:      {job.records_failed}")
            print()
            print("  Timestamps:")
            print(f"    Created:     {format_datetime(job.created_at)}")
            print(f"    Started:     {format_datetime(job.started_at)}")
            print(f"    Completed:   {format_datetime(job.completed_at)}")
            print(f"    Paused:      {format_datetime(job.paused_at)}")
            print(f"    Cancelled:   {format_datetime(job.cancelled_at)}")
            print(f"    Duration:    {format_duration(job.duration_seconds)}")
            print()
            print(f"  Errors:        {job.error_count}")
            if job.last_error:
                print(f"  Last Error:    {colorize(job.last_error, 'red')}")
            print("-" * 50)

            return 0

    except Exception as e:
        logger.error(f"Status failed: {e}")
        return 1


def cmd_cancel(args: argparse.Namespace) -> int:
    """Handle cancel command."""
    try:
        with get_db_context() as db:
            service = ResumableBackfillService(db)

            job = service.cancel_job(args.job_id)

            print(f"\n{colorize('Job cancelled successfully:', 'green')}")
            print(f"  Job ID: {colorize(job.id, 'cyan')}")
            print(f"  Status: {colorize(job.status, status_color(job.status))}")
            print(f"  Cancelled at: {format_datetime(job.cancelled_at)}")

            return 0

    except ValueError as e:
        print(colorize(f"Error: {e}", "red"))
        return 1
    except Exception as e:
        logger.error(f"Cancel failed: {e}")
        return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s run --tenant abc-123 --type costs --months 6
  %(prog)s run --type identity --months 12 --batch-size 500
  %(prog)s resume --job-id abc-123 --batch-size 500
  %(prog)s list --tenant abc-123
  %(prog)s list --type costs --status running
  %(prog)s status --job-id abc-123
  %(prog)s cancel --job-id abc-123
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run command
    run_parser = subparsers.add_parser("run", help="Start new backfill")
    run_parser.add_argument("--tenant", type=str, help="Tenant ID (default: all tenants)")
    run_parser.add_argument(
        "--type",
        choices=["costs", "identity", "compliance", "resources"],
        required=True,
        help="Type of data to backfill",
    )
    run_parser.add_argument("--months", type=int, default=6, help="Number of months to backfill")
    run_parser.add_argument("--batch-size", type=int, default=500, help="Batch insert size")
    run_parser.add_argument(
        "--sequential", action="store_true", help="Process days sequentially without checkpointing"
    )
    run_parser.add_argument("--dry-run", action="store_true", help="Create job but don't execute")

    # resume command
    resume_parser = subparsers.add_parser("resume", help="Resume backfill")
    resume_parser.add_argument("--job-id", required=True, help="Job ID to resume")
    resume_parser.add_argument("--batch-size", type=int, default=500, help="Batch insert size")

    # list command
    list_parser = subparsers.add_parser("list", help="List jobs")
    list_parser.add_argument("--tenant", help="Filter by tenant ID")
    list_parser.add_argument(
        "--type",
        choices=["costs", "identity", "compliance", "resources"],
        help="Filter by job type",
    )
    list_parser.add_argument("--status", help="Filter by status")

    # status command
    status_parser = subparsers.add_parser("status", help="Show job status")
    status_parser.add_argument("--job-id", required=True, help="Job ID")

    # cancel command
    cancel_parser = subparsers.add_parser("cancel", help="Cancel job")
    cancel_parser.add_argument("--job-id", required=True, help="Job ID to cancel")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Route to appropriate handler
    handlers: dict[str, Any] = {
        "run": cmd_run,
        "resume": cmd_resume,
        "list": cmd_list,
        "status": cmd_status,
        "cancel": cmd_cancel,
    }

    handler = handlers.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
