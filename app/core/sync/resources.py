"""Resource inventory synchronization module."""

import json
import logging
from datetime import datetime

from azure.core.exceptions import HttpResponseError

from app.api.services.azure_client import azure_client_manager
from app.api.services.monitoring_service import MonitoringService
from app.core.circuit_breaker import RESOURCE_SYNC_BREAKER, circuit_breaker
from app.core.database import get_db_context
from app.core.retry import RESOURCE_SYNC_POLICY, retry_with_backoff
from app.models.resource import Resource
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)


@circuit_breaker(RESOURCE_SYNC_BREAKER)
@retry_with_backoff(RESOURCE_SYNC_POLICY)
async def sync_resources():
    """Sync resource inventory from all tenants.

    Fetches resource inventory from Azure Resource Manager API
    for all active tenants and their subscriptions, storing results
    in the Resource model. Detects orphaned resources based on
    provisioning state and activity patterns.
    """
    logger.info(f"Starting resource sync at {datetime.utcnow()}")

    total_synced = 0
    total_errors = 0
    total_orphaned = 0
    log_id = None

    try:
        with get_db_context() as db:
            # Start monitoring
            monitoring = MonitoringService(db)
            log_entry = monitoring.start_sync_job(job_type="resources")
            log_id = log_entry.id
            # Get all active tenants
            tenants = db.query(Tenant).filter(Tenant.is_active).all()
            logger.info(f"Found {len(tenants)} active tenants to sync for resources")

            for tenant in tenants:
                logger.info(f"Syncing resources for tenant: {tenant.name} ({tenant.tenant_id})")

                try:
                    # Get subscriptions for this tenant
                    subscriptions = await azure_client_manager.list_subscriptions(tenant.tenant_id)
                    logger.info(
                        f"Found {len(subscriptions)} subscriptions for tenant {tenant.name}"
                    )

                    for sub in subscriptions:
                        sub_id = sub["subscription_id"]
                        sub_name = sub["display_name"]

                        # Skip non-enabled subscriptions
                        if sub["state"] != "Enabled":
                            logger.info(f"Skipping subscription {sub_name} (state: {sub['state']})")
                            continue

                        try:
                            logger.info(
                                f"Querying resources for subscription: {sub_name} ({sub_id[:8]}...)"
                            )

                            # Get resource client for this subscription
                            resource_client = azure_client_manager.get_resource_client(
                                tenant.tenant_id, sub_id
                            )

                            # List all resources in the subscription with pagination
                            resources = resource_client.resources.list(
                                expand="provisioningState,createdTime,changedTime,lastUsedTime"
                            )

                            subscription_synced = 0
                            subscription_orphaned = 0

                            for resource in resources:
                                try:
                                    # Parse resource ID to extract components
                                    # Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/{provider}/{type}/{name}
                                    resource_id = resource.id or ""
                                    resource_group = ""
                                    resource_type = ""

                                    # Extract resource group from ID
                                    id_parts = resource_id.split("/")
                                    if len(id_parts) > 4 and id_parts[1] == "subscriptions":
                                        # Find resourceGroups in path
                                        for i, part in enumerate(id_parts):
                                            if part.lower() == "resourcegroups" and i + 1 < len(
                                                id_parts
                                            ):
                                                resource_group = id_parts[i + 1]
                                                break

                                    # Extract resource type (provider/type)
                                    if "/providers/" in resource_id:
                                        provider_part = resource_id.split("/providers/")[-1]
                                        provider_parts = provider_part.split("/")
                                        if len(provider_parts) >= 2:
                                            resource_type = (
                                                f"{provider_parts[0]}/{provider_parts[1]}"
                                            )

                                    # Serialize tags as JSON
                                    tags_json = None
                                    if resource.tags:
                                        tags_json = json.dumps(resource.tags)

                                    # Detect orphaned resources
                                    is_orphaned = 0
                                    provisioning_state = resource.provisioning_state or ""

                                    # Check for failed/canceled provisioning state
                                    if provisioning_state.lower() in ("failed", "canceled"):
                                        is_orphaned = 1
                                        subscription_orphaned += 1
                                    # Check for orphaned tag indicators
                                    elif resource.tags:
                                        tag_str = json.dumps(resource.tags).lower()
                                        if any(
                                            indicator in tag_str
                                            for indicator in ["orphaned", "orphan", "untracked"]
                                        ):
                                            is_orphaned = 1
                                            subscription_orphaned += 1

                                    # Check SKU - handle as string
                                    sku_str = None
                                    if resource.sku:
                                        if hasattr(resource.sku, "name"):
                                            sku_str = resource.sku.name
                                        else:
                                            sku_str = str(resource.sku)

                                    # Check estimated monthly cost from tags if available
                                    estimated_cost = None
                                    if resource.tags:
                                        for key, value in resource.tags.items():
                                            if "cost" in key.lower() and "month" in key.lower():
                                                try:
                                                    # Try to parse cost value
                                                    cost_val = (
                                                        str(value).replace("$", "").replace(",", "")
                                                    )
                                                    estimated_cost = float(cost_val)
                                                except (ValueError, TypeError):
                                                    pass

                                    # Check if resource already exists
                                    existing = (
                                        db.query(Resource)
                                        .filter(Resource.id == resource_id)
                                        .first()
                                    )

                                    if existing:
                                        # Update existing resource
                                        existing.tenant_id = tenant.id
                                        existing.subscription_id = sub_id
                                        existing.resource_group = resource_group
                                        existing.resource_type = resource_type
                                        existing.name = resource.name or ""
                                        existing.location = resource.location or ""
                                        existing.provisioning_state = provisioning_state
                                        existing.sku = sku_str
                                        existing.tags_json = tags_json
                                        existing.is_orphaned = is_orphaned
                                        if estimated_cost is not None:
                                            existing.estimated_monthly_cost = estimated_cost
                                        existing.synced_at = datetime.utcnow()
                                    else:
                                        # Create new resource
                                        new_resource = Resource(
                                            id=resource_id,
                                            tenant_id=tenant.id,
                                            subscription_id=sub_id,
                                            resource_group=resource_group,
                                            resource_type=resource_type,
                                            name=resource.name or "",
                                            location=resource.location or "",
                                            provisioning_state=provisioning_state,
                                            sku=sku_str,
                                            tags_json=tags_json,
                                            is_orphaned=is_orphaned,
                                            estimated_monthly_cost=estimated_cost,
                                            synced_at=datetime.utcnow(),
                                        )
                                        db.add(new_resource)

                                    subscription_synced += 1

                                except Exception as e:
                                    total_errors += 1
                                    logger.warning(f"Error processing resource {resource.id}: {e}")
                                    continue

                            # Commit all resources for this subscription
                            db.commit()
                            total_synced += subscription_synced
                            total_orphaned += subscription_orphaned

                            logger.info(
                                f"Successfully synced {subscription_synced} resources "
                                f"({subscription_orphaned} orphaned) for subscription {sub_name}"
                            )

                        except HttpResponseError as e:
                            total_errors += 1
                            if e.status_code == 403:
                                logger.error(
                                    f"Access denied to resources for subscription {sub_name}. "
                                    f"Missing Reader role?"
                                )
                            else:
                                logger.error(
                                    f"HTTP error querying resources for {sub_name}: "
                                    f"{e.status_code} - {e.message}"
                                )
                        except Exception as e:
                            total_errors += 1
                            logger.error(
                                f"Error syncing resources for subscription {sub_name}: {e}",
                                exc_info=True,
                            )

                except Exception as e:
                    total_errors += 1
                    logger.error(
                        f"Error processing tenant {tenant.name}: {e}",
                        exc_info=True,
                    )

        # Update monitoring with final status
        if log_id:
            monitoring.complete_sync_job(
                log_id=log_id,
                status="completed" if total_errors == 0 else "failed",
                final_records={
                    "records_processed": total_synced,
                    "records_created": total_synced,
                    "records_updated": 0,
                    "errors_count": total_errors,
                },
            )

        logger.info(
            f"Resource sync completed: {total_synced} resources synced, "
            f"{total_orphaned} orphaned detected, "
            f"{total_errors} errors encountered"
        )

    except Exception as e:
        logger.error(f"Fatal error during resource sync: {e}", exc_info=True)
        # Update monitoring with failure status
        if log_id:
            with get_db_context() as db:
                monitoring = MonitoringService(db)
                monitoring.complete_sync_job(
                    log_id=log_id,
                    status="failed",
                    error_message=str(e)[:1000],
                    final_records={
                        "records_processed": total_synced,
                        "records_created": total_synced,
                        "records_updated": 0,
                        "errors_count": total_errors + 1,
                    },
                )
        raise
