#!/usr/bin/env python3
"""Upload database backup to Azure Blob Storage.

Usage:
    python scripts/upload_backup.py --file backup.sql.gz --account mystorage --account mystorage --container backups

Environment Variables:
    AZURE_STORAGE_ACCOUNT: Storage account name
    AZURE_STORAGE_CONTAINER: Container name (default: database-backups)
    AZURE_STORAGE_SAS_TOKEN: SAS token for authentication
    AZURE_CLIENT_ID: Managed Identity client ID (alternative auth)
"""

import argparse
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Upload database backup to Azure Blob Storage")
    parser.add_argument(
        "--file",
        required=True,
        help="Path to backup file to upload",
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
        "--blob-name",
        help="Custom blob name (default: auto-generated with timestamp)",
    )
    parser.add_argument(
        "--metadata",
        nargs="*",
        help="Additional metadata tags (format: key=value)",
    )
    return parser.parse_args()


def get_credential():
    """Get Azure credential using DefaultAzureCredential."""
    try:
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
        logger.info("Using DefaultAzureCredential for authentication")
        return credential
    except ImportError:
        logger.error("azure-identity package not installed")
        raise


def upload_to_azure(
    file_path: str,
    account_name: str,
    container_name: str,
    blob_name: str | None = None,
    metadata: dict | None = None,
) -> str:
    """Upload file to Azure Blob Storage.

    Returns:
        URL of the uploaded blob
    """
    try:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient, ContentSettings
    except ImportError as e:
        logger.error(f"Required Azure packages not installed: {e}")
        raise

    # Generate blob name if not provided
    if not blob_name:
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        source_file = Path(file_path).name
        # Remove .gz extension for the base name if present
        base_name = source_file.replace(".gz", "")
        blob_name = f"backups/{timestamp}_{base_name}.gz"

    # Build blob service client
    account_url = f"https://{account_name}.blob.core.windows.net"

    # Try SAS token first, then DefaultAzureCredential
    sas_token = os.getenv("AZURE_STORAGE_SAS_TOKEN")
    if sas_token:
        blob_service = BlobServiceClient(
            account_url=account_url,
            credential=sas_token,
        )
        logger.info("Using SAS token for authentication")
    else:
        credential = DefaultAzureCredential()
        blob_service = BlobServiceClient(
            account_url=account_url,
            credential=credential,
        )
        logger.info("Using DefaultAzureCredential for authentication")

    # Get container client
    container_client = blob_service.get_container_client(container_name)

    # Create container if it doesn't exist
    try:
        container_client.create_container()
        logger.info(f"Created container: {container_name}")
    except Exception:
        # Container likely already exists
        pass

    # Get blob client
    blob_client = container_client.get_blob_client(blob_name)

    # Prepare metadata
    blob_metadata = {
        "uploaded_at": datetime.now(UTC).isoformat(),
        "source_file": Path(file_path).name,
        "size_bytes": str(os.path.getsize(file_path)),
    }
    if metadata:
        blob_metadata.update(metadata)

    # Set content settings for gzip
    content_settings = ContentSettings(
        content_type="application/gzip",
        content_encoding="gzip",
    )

    # Upload file
    logger.info(f"Uploading {file_path} to {blob_name}...")

    with open(file_path, "rb") as data:
        blob_client.upload_blob(
            data,
            overwrite=True,
            metadata=blob_metadata,
            content_settings=content_settings,
        )

    # Get blob URL
    blob_url = blob_client.url
    logger.info(f"✓ Upload complete: {blob_url}")

    return blob_url


def parse_metadata(metadata_list: list[str] | None) -> dict:
    """Parse metadata key=value pairs."""
    if not metadata_list:
        return {}

    result = {}
    for item in metadata_list:
        if "=" in item:
            key, value = item.split("=", 1)
            result[key] = value
        else:
            logger.warning(f"Invalid metadata format: {item}")
    return result


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Validate required parameters
    if not args.account:
        logger.error(
            "Azure Storage account not specified (use --account or AZURE_STORAGE_ACCOUNT env)"
        )
        return 1

    if not os.path.exists(args.file):
        logger.error(f"File not found: {args.file}")
        return 1

    try:
        # Parse metadata
        metadata = parse_metadata(args.metadata)

        # Upload to Azure
        blob_url = upload_to_azure(
            file_path=args.file,
            account_name=args.account,
            container_name=args.container,
            blob_name=args.blob_name,
            metadata=metadata,
        )

        # Output for CI/CD
        print(f"::set-output name=blob_url::{blob_url}")
        print(f"::set-output name=blob_name::{args.blob_name or blob_url.split('/')[-1]}")

        return 0

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
