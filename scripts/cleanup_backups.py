#!/usr/bin/env python3
"""Clean up old database backups from Azure Blob Storage.

Maintains a retention policy by deleting backups older than specified days.

Usage:
    python scripts/cleanup_backups.py --account mystorage --container backups --retention-days 30

Environment Variables:
    AZURE_STORAGE_ACCOUNT: Storage account name
    AZURE_STORAGE_CONTAINER: Container name
    AZURE_STORAGE_SAS_TOKEN: SAS token for authentication
    AZURE_STORAGE_KEY: Storage account key for ephemeral CI authentication
"""

import argparse
import logging
import os
import sys
from datetime import UTC, datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Clean up old database backups from Azure Blob Storage"
    )
    parser.add_argument(
        "--account",
        default=os.getenv("AZURE_STORAGE_ACCOUNT"),
        help="Azure Storage account name",
    )
    parser.add_argument(
        "--container",
        default=os.getenv("AZURE_STORAGE_CONTAINER", "database-backups"),
        help="Blob container name",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=30,
        help="Number of days to retain backups (default: 30)",
    )
    parser.add_argument(
        "--prefix",
        default="backups/",
        help="Blob name prefix to filter (default: backups/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    return parser.parse_args()


def get_azure_client(account_name: str, container_name: str):
    """Get Azure Blob Service and Container clients."""
    try:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient
    except ImportError as e:
        logger.error(f"Required Azure packages not installed: {e}")
        raise

    account_url = f"https://{account_name}.blob.core.windows.net"

    # Try SAS token first, then an ephemeral storage key, then Azure identity.
    sas_token = os.getenv("AZURE_STORAGE_SAS_TOKEN")
    storage_key = os.getenv("AZURE_STORAGE_KEY")
    if sas_token:
        blob_service = BlobServiceClient(
            account_url=account_url,
            credential=sas_token,
        )
    elif storage_key:
        blob_service = BlobServiceClient(
            account_url=account_url,
            credential=storage_key,
        )
    else:
        credential = DefaultAzureCredential()
        blob_service = BlobServiceClient(
            account_url=account_url,
            credential=credential,
        )

    container_client = blob_service.get_container_client(container_name)
    return container_client


def cleanup_old_backups(
    account_name: str,
    container_name: str,
    retention_days: int,
    prefix: str = "backups/",
    dry_run: bool = False,
) -> tuple[int, int, int]:
    """Clean up old backups based on retention policy.

    Returns:
        Tuple of (total_blobs, deleted_count, preserved_count)
    """
    container_client = get_azure_client(account_name, container_name)

    # Calculate cutoff date
    cutoff_date = datetime.now(UTC) - timedelta(days=retention_days)
    logger.info(f"Retention policy: {retention_days} days (cutoff: {cutoff_date.isoformat()})")

    # List all blobs with prefix
    logger.info(f"Scanning blobs with prefix: {prefix}")
    blobs = list(container_client.list_blobs(name_starts_with=prefix))

    if not blobs:
        logger.info("No backups found")
        return 0, 0, 0

    total_size_deleted = 0
    deleted_count = 0
    preserved_count = 0

    for blob in blobs:
        # Get blob age
        blob_age_days = (datetime.now(UTC) - blob.last_modified).days

        if blob_age_days > retention_days:
            # Blob is older than retention policy
            logger.info(
                f"{'[DRY RUN] Would delete' if dry_run else 'Deleting'}: "
                f"{blob.name} (age: {blob_age_days} days, size: {blob.size} bytes)"
            )

            if not dry_run:
                try:
                    container_client.delete_blob(blob.name)
                    logger.info(f"  ✓ Deleted: {blob.name}")
                except Exception as e:
                    logger.error(f"  ✗ Failed to delete {blob.name}: {e}")
                    continue

            total_size_deleted += blob.size
            deleted_count += 1
        else:
            preserved_count += 1

    # Summary
    action = "Would delete" if dry_run else "Deleted"
    logger.info(
        f"{action} {deleted_count} blobs ({total_size_deleted / (1024 * 1024):.2f} MB), "
        f"preserved {preserved_count} blobs"
    )

    return len(blobs), deleted_count, preserved_count


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Validate required parameters
    if not args.account:
        logger.error(
            "Azure Storage account not specified (use --account or AZURE_STORAGE_ACCOUNT env)"
        )
        return 1

    try:
        total, deleted, preserved = cleanup_old_backups(
            account_name=args.account,
            container_name=args.container,
            retention_days=args.retention_days,
            prefix=args.prefix,
            dry_run=args.dry_run,
        )

        if args.dry_run:
            logger.info(f"[DRY RUN] Would delete {deleted} of {total} blobs")
        else:
            logger.info(f"Cleanup complete: {deleted} deleted, {preserved} preserved")

        # Output for CI/CD
        print(f"::set-output name=total_blobs::{total}")
        print(f"::set-output name=deleted_blobs::{deleted}")
        print(f"::set-output name=preserved_blobs::{preserved}")

        return 0

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
