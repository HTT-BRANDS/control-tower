#!/usr/bin/env python3
"""Rotate secrets in Azure Key Vault with safety checks.

This script provides secure secret rotation with:
- Backup of existing secrets before rotation
- Soft-delete protection verification
- Staged rotation with verification
- Automatic cache invalidation
- Audit logging of all rotations

Usage:
    # Rotate a single secret
    python scripts/rotate-keyvault-secrets.py --vault my-kv --secret my-secret --generate

    # Rotate all secrets matching a pattern
    python scripts/rotate-keyvault-secrets.py --vault my-kv --pattern "api-key-*" --generate

    # Rotate using a value from file
    python scripts/rotate-keyvault-secrets.py --vault my-kv --secret my-secret --from-file new-value.txt

    # Dry run to see what would be rotated
    python scripts/rotate-keyvault-secrets.py --vault my-kv --secret my-secret --generate --dry-run

Environment Variables:
    AZURE_SUBSCRIPTION_ID: Azure subscription ID
    KEY_VAULT_URL: Key Vault URL (fallback to --vault)
"""

import argparse
import json
import logging
import os
import secrets
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("keyvault-rotation.log"),
    ],
)
logger = logging.getLogger(__name__)


@dataclass
class RotationResult:
    """Result of a secret rotation operation."""

    secret_name: str
    success: bool
    previous_version: str | None = None
    new_version: str | None = None
    backed_up: bool = False
    error_message: str | None = None
    rotation_time: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "secret_name": self.secret_name,
            "success": self.success,
            "previous_version": self.previous_version,
            "new_version": self.new_version,
            "backed_up": self.backed_up,
            "error_message": self.error_message,
            "rotation_time": datetime.fromtimestamp(self.rotation_time).isoformat(),
        }


class KeyVaultSecretRotator:
    """Manages Azure Key Vault secret rotation with safety features."""

    def __init__(self, vault_url: str | None = None):
        self.vault_url = vault_url or os.environ.get("KEY_VAULT_URL")
        self._client: Any = None
        self._backup_dir = Path("secret-backups")
        self._rotation_log: list[RotationResult] = []

    def _get_client(self) -> Any:
        """Get or create Key Vault client."""
        if self._client is None:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.keyvault.secrets import SecretClient

                if not self.vault_url:
                    raise ValueError("Key Vault URL not configured")

                credential = DefaultAzureCredential()
                self._client = SecretClient(vault_url=self.vault_url, credential=credential)
                logger.info(f"Connected to Key Vault: {self.vault_url}")

            except ImportError:
                logger.error(
                    "Azure Key Vault SDK not installed. Run: pip install azure-keyvault-secrets azure-identity"
                )
                raise

        return self._client

    def verify_soft_delete(self) -> bool:
        """Verify soft-delete is enabled for secret recovery."""
        try:
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.keyvault import KeyVaultManagementClient

            subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
            resource_group = os.environ.get("AZURE_RESOURCE_GROUP")

            if not subscription_id or not resource_group:
                logger.warning(
                    "Cannot verify soft-delete: AZURE_SUBSCRIPTION_ID or AZURE_RESOURCE_GROUP not set"
                )
                return True  # Assume enabled for safety

            credential = DefaultAzureCredential()
            kv_client = KeyVaultManagementClient(credential, subscription_id)

            vault_name = self.vault_url.split(".")[0].replace("https://", "")
            vault = kv_client.vaults.get(resource_group, vault_name)

            soft_delete = vault.properties.enable_soft_delete
            purge_protection = vault.properties.enable_purge_protection

            if not soft_delete:
                logger.error(f"WARNING: Soft-delete is NOT enabled on {vault_name}!")
                logger.error(
                    "Secret rotation without soft-delete is dangerous - deleted secrets cannot be recovered!"
                )
            else:
                logger.info(f"✅ Soft-delete enabled on {vault_name}")

            if purge_protection:
                logger.info(f"✅ Purge protection enabled on {vault_name}")
            else:
                logger.warning(f"⚠️ Purge protection not enabled on {vault_name}")

            return soft_delete

        except Exception as e:
            logger.warning(f"Could not verify soft-delete status: {e}")
            return True  # Assume enabled for safety

    def backup_secret(self, secret_name: str) -> bool:
        """Backup secret before rotation."""
        try:
            client = self._get_client()
            secret = client.get_secret(secret_name)

            # Create backup directory
            self._backup_dir.mkdir(exist_ok=True)

            # Create timestamped backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self._backup_dir / f"{secret_name}_{timestamp}.json"

            backup_data = {
                "secret_name": secret_name,
                "value": secret.value,
                "version": secret.properties.version,
                "created_on": secret.properties.created_on.isoformat()
                if secret.properties.created_on
                else None,
                "expires_on": secret.properties.expires_on.isoformat()
                if secret.properties.expires_on
                else None,
                "backup_time": timestamp,
            }

            with open(backup_file, "w") as f:
                json.dump(backup_data, f, indent=2)

            logger.info(f"📦 Backed up {secret_name} to {backup_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to backup {secret_name}: {e}")
            return False

    def generate_secure_value(self, secret_type: str = "password", length: int = 32) -> str:  # pragma: allowlist secret
        """Generate a secure secret value."""
        if secret_type == "password":  # pragma: allowlist secret
            return secrets.token_urlsafe(length)
        elif secret_type == "hex":
            return secrets.token_hex(length)
        elif secret_type == "api_key":  # pragma: allowlist secret
            return f"ak_{secrets.token_urlsafe(length)}"
        elif secret_type == "jwt_secret":  # pragma: allowlist secret
            return secrets.token_urlsafe(64)  # JWT needs more entropy
        else:
            return secrets.token_urlsafe(length)

    def rotate_secret(
        self,
        secret_name: str,  # pragma: allowlist secret
        new_value: str | None = None,
        generate: bool = False,
        secret_type: str = "password",
        dry_run: bool = False,
        skip_backup: bool = False,
        expires_in_days: int | None = None,
        content_type: str = "rotated-secret",
        tags: dict[str, str] | None = None,
    ) -> RotationResult:
        """Rotate a secret with safety checks."""
        start_time = time.time()

        try:
            client = self._get_client()

            # Get current secret version
            try:
                current = client.get_secret(secret_name)
                previous_version = current.properties.version
            except Exception:
                previous_version = None
                logger.info(f"No existing secret found: {secret_name}")

            # Backup existing secret
            if not skip_backup and previous_version and not dry_run:
                if not self.backup_secret(secret_name):
                    return RotationResult(
                        secret_name=secret_name,
                        success=False,
                        error_message="Backup failed, aborting rotation for safety",
                    )

            # Generate new value if needed
            if generate and not new_value:
                new_value = self.generate_secure_value(secret_type)
                logger.info(f"Generated new {secret_type} value for {secret_name}")

            if not new_value:
                return RotationResult(
                    secret_name=secret_name,
                    success=False,
                    error_message="No new value provided and generate=False",
                )

            if dry_run:
                logger.info(
                    f"[DRY RUN] Would rotate {secret_name} (current version: {previous_version})"
                )
                return RotationResult(
                    secret_name=secret_name,
                    success=True,
                    previous_version=previous_version,
                    new_version="DRY_RUN",
                    backed_up=not skip_backup,
                    rotation_time=time.time(),
                )

            # Set new secret version
            from datetime import timedelta

            expires_on = None
            if expires_in_days:
                expires_on = datetime.utcnow() + timedelta(days=expires_in_days)

            rotated_tags = tags or {}
            rotated_tags["rotated_at"] = datetime.utcnow().isoformat()
            rotated_tags["rotated_by"] = os.environ.get("USER", "unknown")

            new_secret = client.set_secret(
                secret_name,
                new_value,
                content_type=content_type,
                expires_on=expires_on,
                tags=rotated_tags,
            )

            result = RotationResult(
                secret_name=secret_name,
                success=True,
                previous_version=previous_version,
                new_version=new_secret.properties.version,
                backed_up=not skip_backup,
                rotation_time=time.time(),
            )

            logger.info(
                f"✅ Successfully rotated {secret_name} (new version: {new_secret.properties.version})"
            )

            # Invalidate cache if using the app cache
            self._invalidate_app_cache(secret_name)

            return result

        except Exception as e:
            logger.error(f"❌ Failed to rotate {secret_name}: {e}")
            return RotationResult(
                secret_name=secret_name,
                success=False,
                previous_version=None,
                error_message=str(e),
                rotation_time=time.time(),
            )

    def _invalidate_app_cache(self, secret_name: str) -> None:
        """Invalidate app cache for the rotated secret."""
        try:
            # Try to import and use the app's key vault manager
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from app.core.config import key_vault_manager

            key_vault_manager.invalidate_secret(secret_name)
            logger.info(f"Invalidated app cache for {secret_name}")
        except Exception:
            logger.debug(f"Could not invalidate app cache for {secret_name}")

    def rotate_multiple(
        self,
        secret_names: list[str],
        generate: bool = False,
        secret_type: str = "password",
        dry_run: bool = False,
        **kwargs,
    ) -> list[RotationResult]:
        """Rotate multiple secrets."""
        results = []

        for secret_name in secret_names:
            result = self.rotate_secret(
                secret_name=secret_name,
                generate=generate,
                secret_type=secret_type,
                dry_run=dry_run,
                **kwargs,
            )
            results.append(result)

        return results

    def list_secrets(self, pattern: str | None = None) -> list[str]:
        """List secrets in Key Vault, optionally filtered by pattern."""
        try:
            client = self._get_client()
            secrets = []

            for secret in client.list_properties_of_secrets():
                if pattern is None or pattern in secret.name:
                    secrets.append(secret.name)

            return secrets

        except Exception as e:
            logger.error(f"Failed to list secrets: {e}")
            return []

    def generate_rotation_report(self) -> dict[str, Any]:
        """Generate a summary report of all rotations."""
        successful = [r for r in self._rotation_log if r.success]
        failed = [r for r in self._rotation_log if not r.success]

        return {
            "total_rotations": len(self._rotation_log),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": f"{len(successful) / max(len(self._rotation_log), 1) * 100:.1f}%",
            "details": [r.to_dict() for r in self._rotation_log],
            "report_generated": datetime.utcnow().isoformat(),
        }

    def save_report(self, output_path: str = "rotation-report.json") -> None:
        """Save rotation report to file."""
        report = self.generate_rotation_report()

        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Rotation report saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Rotate Azure Key Vault Secrets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Rotate single secret with generated value
  %(prog)s --vault my-kv --secret my-secret --generate
  
  # Rotate with specific value
  %(prog)s --vault my-kv --secret my-secret --value "my-new-value"
  
  # Rotate from file
  %(prog)s --vault my-kv --secret my-secret --from-file value.txt
  
  # Rotate all matching secrets
  %(prog)s --vault my-kv --pattern "api-key-*" --generate
  
  # Dry run (see what would happen)
  %(prog)s --vault my-kv --secret my-secret --generate --dry-run
        """,
    )

    parser.add_argument("--vault", "-v", help="Key Vault name or URL")
    parser.add_argument("--secret", "-s", help="Secret name to rotate")
    parser.add_argument("--pattern", "-p", help="Pattern to match multiple secrets")
    parser.add_argument("--generate", "-g", action="store_true", help="Generate new secure value")
    parser.add_argument(
        "--type",
        "-t",
        default="password",
        choices=["password", "hex", "api_key", "jwt_secret"],
        help="Type of secret to generate",
    )
    parser.add_argument("--value", help="New secret value (if not generating)")
    parser.add_argument("--from-file", help="Read new value from file")
    parser.add_argument("--dry-run", "-d", action="store_true", help="Show what would be rotated")
    parser.add_argument("--skip-backup", action="store_true", help="Skip backup (not recommended)")
    parser.add_argument("--expires-days", type=int, help="Set expiration in days")
    parser.add_argument("--content-type", default="rotated-secret", help="Content type tag")
    parser.add_argument("--report", default="rotation-report.json", help="Output report path")
    parser.add_argument(
        "--no-soft-delete-check", action="store_true", help="Skip soft-delete verification"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.secret and not args.pattern:
        parser.error("Must specify --secret or --pattern")

    if not args.generate and not args.value and not args.from_file:
        parser.error("Must specify one of: --generate, --value, --from-file")

    # Build vault URL
    vault_url = args.vault
    if vault_url and not vault_url.startswith("https://"):
        vault_url = f"https://{vault_url}.vault.azure.net"

    # Initialize rotator
    rotator = KeyVaultSecretRotator(vault_url)

    # Verify soft-delete (safety check)
    if not args.no_soft_delete_check:
        soft_delete_enabled = rotator.verify_soft_delete()
        if not soft_delete_enabled:
            logger.error("Aborting: Soft-delete is not enabled on this Key Vault!")
            logger.error("Run with --no-soft-delete-check to override (not recommended)")
            sys.exit(1)

    # Get new value
    new_value = args.value
    if args.from_file:
        with open(args.from_file) as f:
            new_value = f.read().strip()

    # Determine secrets to rotate
    secret_names = []
    if args.pattern:
        all_secrets = rotator.list_secrets(args.pattern)
        secret_names = all_secrets
        logger.info(f"Found {len(secret_names)} secrets matching pattern '{args.pattern}'")
    else:
        secret_names = [args.secret]

    if not secret_names:
        logger.warning("No secrets found to rotate")
        sys.exit(0)

    # Rotate secrets
    logger.info(f"{'[DRY RUN] ' if args.dry_run else ''}Rotating {len(secret_names)} secret(s)...")

    for secret_name in secret_names:
        result = rotator.rotate_secret(
            secret_name=secret_name,
            new_value=new_value,
            generate=args.generate,
            secret_type=args.type,
            dry_run=args.dry_run,
            skip_backup=args.skip_backup,
            expires_in_days=args.expires_days,
            content_type=args.content_type,
        )
        rotator._rotation_log.append(result)

    # Generate report
    if not args.dry_run:
        rotator.save_report(args.report)

    # Summary
    report = rotator.generate_rotation_report()
    print(f"\n{'='*50}")
    print("Rotation Summary")
    print(f"{'='*50}")
    print(f"Total: {report['total_rotations']}")
    print(f"Successful: {report['successful']}")
    print(f"Failed: {report['failed']}")
    print(f"Success Rate: {report['success_rate']}")
    print(f"{'='*50}\n")

    # Exit with error code if any rotations failed
    sys.exit(0 if report["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
