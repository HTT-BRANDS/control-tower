#!/usr/bin/env python3
"""Configure and optimize Azure Cache for Redis.

This script provides Azure Redis configuration management with:
- Automated performance tuning based on SKU tier
- Connection string generation with Azure best practices
- Cluster configuration for Premium tier
- Memory policy optimization
- Diagnostic settings configuration

Usage:
    python scripts/configure-azure-redis.py --name my-redis --resource-group my-rg
    python scripts/configure-azure-redis.py --diagnostics --name my-redis --resource-group my-rg
    python scripts/configure-azure-redis.py --connection-string --name my-redis

Environment Variables:
    AZURE_SUBSCRIPTION_ID: Azure subscription ID
    AZURE_RESOURCE_GROUP: Default resource group
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class RedisConfig:
    """Azure Redis configuration."""

    name: str
    resource_group: str
    sku: str = "Standard"
    family: str = "C"
    capacity: int = 1
    enable_clustering: bool = False
    shard_count: int = 0
    maxmemory_policy: str = "allkeys-lru"
    min_tls_version: str = "1.2"

    # Performance tuning per SKU
    @property
    def recommended_settings(self) -> dict[str, Any]:
        """Get recommended settings based on SKU tier."""
        base_settings = {
            "maxclients": 1000,
            "maxmemory-reserved": 50,
            "maxfragmentationmemory-reserved": 50,
            "maxmemory-delta": 50,
        }

        if self.sku == "Premium":
            return {
                **base_settings,
                "maxclients": 7500,
                "maxmemory-reserved": 200,
                "maxfragmentationmemory-reserved": 200,
                "maxmemory-delta": 200,
            }
        elif self.sku == "Standard":
            return {
                **base_settings,
                "maxclients": 1000,
                "maxmemory-reserved": 50,
                "maxfragmentationmemory-reserved": 50,
                "maxmemory-delta": 50,
            }
        else:  # Basic
            return {
                **base_settings,
                "maxclients": 256,
                "maxmemory-reserved": 20,
                "maxfragmentationmemory-reserved": 20,
                "maxmemory-delta": 20,
            }


def run_az_command(args: list[str], capture_output: bool = True) -> tuple[bool, str]:
    """Run an Azure CLI command and return success status and output."""
    cmd = ["az"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            logger.error(f"Azure CLI error: {result.stderr}")
            return False, result.stderr
        return True, result.stdout
    except FileNotFoundError:
        logger.error("Azure CLI not found. Please install: https://aka.ms/install-azure-cli")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Command failed: {e}")
        return False, str(e)


def get_redis_info(name: str, resource_group: str) -> dict[str, Any] | None:
    """Get Azure Redis cache information."""
    success, output = run_az_command(
        ["redis", "show", "--name", name, "--resource-group", resource_group]
    )
    if success:
        return json.loads(output)
    return None


def get_connection_string(name: str, resource_group: str) -> str | None:
    """Get Redis connection string with access keys."""
    success, output = run_az_command(
        ["redis", "list-keys", "--name", name, "--resource-group", resource_group]
    )
    if not success:
        return None

    keys = json.loads(output)
    primary_key = keys.get("primaryKey")

    # Get hostname
    info = get_redis_info(name, resource_group)
    if not info:
        return None

    host = info.get("hostName")
    ssl_port = info.get("sslPort", 6380)

    # Build connection string with Azure best practices
    connection_string = (
        f"rediss://:{primary_key}@{host}:{ssl_port}?ssl=true&"
        f"ssl_cert_reqs=required&socket_timeout=10&socket_connect_timeout=10&"
        f"retry_on_timeout=true&health_check_interval=30"
    )

    return connection_string


def configure_redis_settings(config: RedisConfig) -> bool:
    """Configure Azure Redis with optimal settings."""
    logger.info(f"Configuring Redis: {config.name} in {config.resource_group}")

    settings = config.recommended_settings

    # Update configuration
    for key, value in settings.items():
        logger.info(f"Setting {key} = {value}")
        success, _ = run_az_command(
            [
                "redis",
                "update",
                "--name",
                config.name,
                "--resource-group",
                config.resource_group,
                "--set",
                f"redisConfiguration.{key}={value}",
            ]
        )
        if not success:
            logger.warning(f"Failed to set {key}")

    # Set memory policy
    logger.info(f"Setting maxmemory-policy = {config.maxmemory_policy}")
    run_az_command(
        [
            "redis",
            "update",
            "--name",
            config.name,
            "--resource-group",
            config.resource_group,
            "--set",
            f"redisConfiguration.maxmemory-policy={config.maxmemory_policy}",
        ]
    )

    # Ensure minimum TLS version
    logger.info(f"Enforcing minimum TLS version: {config.min_tls_version}")
    run_az_command(
        [
            "redis",
            "update",
            "--name",
            config.name,
            "--resource-group",
            config.resource_group,
            "--minimum-tls-version",
            config.min_tls_version,
        ]
    )

    logger.info("Redis configuration updated successfully")
    return True


def enable_clustering(name: str, resource_group: str, shard_count: int) -> bool:
    """Enable Redis clustering for Premium tier."""
    logger.info(f"Enabling clustering with {shard_count} shards...")

    # Check if Premium tier
    info = get_redis_info(name, resource_group)
    if not info:
        return False

    sku = info.get("sku", {}).get("name", "")
    if sku != "Premium":
        logger.error(f"Clustering requires Premium tier. Current: {sku}")
        return False

    success, _ = run_az_command(
        [
            "redis",
            "update",
            "--name",
            name,
            "--resource-group",
            resource_group,
            "--set",
            f"shardCount={shard_count}",
        ]
    )

    if success:
        logger.info(f"Clustering enabled with {shard_count} shards")
    return success


def setup_diagnostics(name: str, resource_group: str, workspace_id: str | None = None) -> bool:
    """Set up diagnostic settings for Azure Redis."""
    logger.info("Configuring diagnostic settings...")

    # If workspace not provided, try to find one
    if not workspace_id:
        success, output = run_az_command(
            [
                "monitor",
                "log-analytics",
                "workspace",
                "list",
                "--resource-group",
                resource_group,
            ]
        )
        if success:
            workspaces = json.loads(output)
            if workspaces:
                workspace_id = workspaces[0].get("id")
                logger.info(f"Using workspace: {workspaces[0].get('name')}")

    if not workspace_id:
        logger.error("No Log Analytics workspace found. Please specify --workspace-id")
        return False

    success, _ = run_az_command(
        [
            "monitor",
            "diagnostic-settings",
            "create",
            "--name",
            f"{name}-diagnostics",
            "--resource",
            f"/subscriptions/{get_subscription_id()}/resourceGroups/{resource_group}/providers/Microsoft.Cache/Redis/{name}",
            "--workspace",
            workspace_id,
            "--logs",
            '[{"category": "ConnectedClientList", "enabled": true}, {"category": "Audit", "enabled": true}]',
            "--metrics",
            '[{"category": "AllMetrics", "enabled": true}]',
        ]
    )

    if success:
        logger.info("Diagnostic settings configured")
    return success


def get_subscription_id() -> str:
    """Get current Azure subscription ID."""
    success, output = run_az_command(["account", "show"], capture_output=True)
    if success:
        account = json.loads(output)
        return account.get("id", "")
    return os.environ.get("AZURE_SUBSCRIPTION_ID", "")


def generate_env_file(name: str, resource_group: str, output_path: str = ".env.redis") -> bool:
    """Generate environment file with Redis configuration."""
    connection_string = get_connection_string(name, resource_group)
    if not connection_string:
        return False

    info = get_redis_info(name, resource_group)
    if not info:
        return False

    sku = info.get("sku", {}).get("name", "Standard")
    is_cluster = info.get("shardCount", 0) > 0

    env_content = f"""# Azure Cache for Redis Configuration
# Generated by configure-azure-redis.py
# Cache: {name} in {resource_group}

# Primary Connection String (SSL enabled for Azure)
REDIS_URL={connection_string}

# Azure Redis Specific Settings
AZURE_REDIS_MAX_RETRIES=3
AZURE_REDIS_RETRY_DELAY=1.0
AZURE_REDIS_RETRY_MAX_DELAY=60.0
AZURE_REDIS_CONNECTION_TIMEOUT=10
AZURE_REDIS_SOCKET_TIMEOUT=10
AZURE_REDIS_HEALTH_CHECK_INTERVAL=30
AZURE_REDIS_MAX_CONNECTIONS=50
AZURE_REDIS_CLUSTER_ENABLED={'true' if is_cluster else 'false'}

# SKU: {sku}
# Cluster Mode: {'Enabled' if is_cluster else 'Disabled'}
"""

    with open(output_path, "w") as f:
        f.write(env_content)

    logger.info(f"Environment file generated: {output_path}")
    return True


def check_redis_health(name: str, resource_group: str) -> bool:
    """Check Azure Redis health status."""
    logger.info("Checking Redis health...")

    info = get_redis_info(name, resource_group)
    if not info:
        return False

    status = info.get("provisioningState", "Unknown")
    host = info.get("hostName", "N/A")
    port = info.get("port", 6379)
    ssl_port = info.get("sslPort", 6380)

    print(f"\n{'='*50}")
    print(f"Redis Cache: {name}")
    print(f"Status: {status}")
    print(f"Host: {host}")
    print(f"Port: {port} (SSL: {ssl_port})")
    print(f"SKU: {info.get('sku', {}).get('name', 'Unknown')}")
    print(f"Shard Count: {info.get('shardCount', 'N/A')}")
    print(f"{'='*50}\n")

    if status == "Succeeded":
        logger.info("✅ Redis cache is healthy")
        return True
    else:
        logger.warning(f"⚠️ Redis cache status: {status}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Configure Azure Cache for Redis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --name my-redis --resource-group my-rg --configure
  %(prog)s --name my-redis --resource-group my-rg --connection-string
  %(prog)s --name my-redis --resource-group my-rg --enable-cluster --shards 3
  %(prog)s --name my-redis --resource-group my-rg --diagnostics
        """,
    )

    parser.add_argument("--name", "-n", required=True, help="Redis cache name")
    parser.add_argument("--resource-group", "-g", help="Resource group name")
    parser.add_argument("--subscription", "-s", help="Azure subscription ID")

    parser.add_argument(
        "--configure", action="store_true", help="Configure Redis with optimal settings"
    )
    parser.add_argument("--connection-string", action="store_true", help="Get connection string")
    parser.add_argument("--generate-env", action="store_true", help="Generate .env.redis file")
    parser.add_argument(
        "--enable-cluster", action="store_true", help="Enable clustering (Premium only)"
    )
    parser.add_argument("--shards", type=int, default=3, help="Number of shards for clustering")
    parser.add_argument("--diagnostics", action="store_true", help="Set up diagnostic settings")
    parser.add_argument("--workspace-id", help="Log Analytics workspace ID for diagnostics")
    parser.add_argument("--health-check", action="store_true", help="Check Redis health status")
    parser.add_argument("--sku", default="Standard", choices=["Basic", "Standard", "Premium"])

    args = parser.parse_args()

    # Get resource group from args or environment
    resource_group = args.resource_group or os.environ.get("AZURE_RESOURCE_GROUP")
    if not resource_group:
        logger.error("Resource group required. Use --resource-group or set AZURE_RESOURCE_GROUP")
        sys.exit(1)

    # Set subscription if provided
    if args.subscription:
        run_az_command(["account", "set", "--subscription", args.subscription])

    # Create config object
    config = RedisConfig(
        name=args.name,
        resource_group=resource_group,
        sku=args.sku,
        enable_clustering=args.enable_cluster,
        shard_count=args.shards,
    )

    # Execute requested operations
    success = True

    if args.health_check or not any(
        [
            args.configure,
            args.connection_string,
            args.diagnostics,
            args.enable_cluster,
            args.generate_env,
        ]
    ):
        success = check_redis_health(args.name, resource_group) and success

    if args.configure:
        success = configure_redis_settings(config) and success

    if args.enable_cluster:
        success = enable_clustering(args.name, resource_group, args.shards) and success

    if args.diagnostics:
        success = setup_diagnostics(args.name, resource_group, args.workspace_id) and success

    if args.connection_string:
        conn_str = get_connection_string(args.name, resource_group)
        if conn_str:
            print(f"\nConnection String:\n{conn_str}\n")
        else:
            success = False

    if args.generate_env:
        success = generate_env_file(args.name, resource_group) and success

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
