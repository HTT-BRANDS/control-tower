"""Resource management service with caching support."""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.cache import cached, get_tenant_name, invalidate_on_sync_completion
from app.models.resource import IdleResource, Resource
from app.models.tenant import Subscription, Tenant
from app.schemas.resource import (
    IdleResource as IdleResourceSchema,
)
from app.schemas.resource import (
    IdleResourceSummary,
    MissingTags,
    OrphanedResource,
    ResourceInventory,
    ResourceItem,
    TaggingCompliance,
    TagResourceResponse,
)

logger = logging.getLogger(__name__)

# Default required tags for tagging compliance
DEFAULT_REQUIRED_TAGS = ["Environment", "Owner", "CostCenter", "Application"]


class ResourceService:
    """Service for resource management operations."""

    def __init__(self, db: Session) -> None:
        self.db: Session = db

    @cached("resource_inventory")
    async def get_resource_inventory(
        self,
        tenant_id: str | None = None,
        resource_type: str | None = None,
        location: str | None = None,
        limit: int = 500,
    ) -> ResourceInventory:
        """Get inventory of resources with optional filtering.

        Args:
            tenant_id: Filter by tenant ID
            resource_type: Filter by resource type (partial match)
            location: Filter by Azure region/location
            limit: Maximum number of resources to return

        Returns:
            ResourceInventory with aggregated resource data
        """
        query = self.db.query(Resource)

        if tenant_id:
            query = query.filter(Resource.tenant_id == tenant_id)
        if resource_type:
            query = query.filter(Resource.resource_type.contains(resource_type))
        if location:
            query = query.filter(Resource.location.ilike(f"%{location}%"))

        resources = query.limit(limit).all()

        # Get tenant names using cache (eliminates N+1 query)
        # OLD: tenants = {t.id: t.name for t in self.db.query(Tenant).all()}

        # Get subscription display names for lookup
        subscriptions = {
            s.subscription_id: (s.display_name or s.subscription_id)
            for s in self.db.query(Subscription).all()
        }

        # Aggregate by type, location, tenant
        by_type: dict[str, int] = {}
        by_location: dict[str, int] = {}
        by_tenant: dict[str, int] = {}
        orphaned_count = 0
        orphaned_cost = 0.0

        items = []
        for r in resources:
            # Type aggregation
            by_type[r.resource_type] = by_type.get(r.resource_type, 0) + 1

            # Location aggregation
            by_location[r.location] = by_location.get(r.location, 0) + 1

            # Tenant aggregation (using cache - O(1) lookup)
            tenant_name = get_tenant_name(str(r.tenant_id)) or "Unknown"
            by_tenant[tenant_name] = by_tenant.get(tenant_name, 0) + 1

            # Orphaned tracking
            if r.is_orphaned:
                orphaned_count += 1
                orphaned_cost += r.estimated_monthly_cost or 0

            # Parse tags
            tags = {}
            if r.tags_json:
                try:
                    tags = json.loads(r.tags_json)
                except json.JSONDecodeError:
                    pass

            items.append(
                ResourceItem(
                    id=r.id,
                    tenant_id=r.tenant_id,
                    tenant_name=get_tenant_name(str(r.tenant_id)) or "Unknown",
                    subscription_id=r.subscription_id,
                    subscription_name=subscriptions.get(r.subscription_id, r.subscription_id),
                    resource_group=r.resource_group,
                    resource_type=r.resource_type,
                    name=r.name,
                    location=r.location or "Unknown",
                    provisioning_state=r.provisioning_state,
                    sku=r.sku,
                    tags=tags,
                    is_orphaned=bool(r.is_orphaned),
                    estimated_monthly_cost=r.estimated_monthly_cost,
                    last_synced=r.synced_at,
                )
            )

        return ResourceInventory(
            total_resources=len(resources),
            resources_by_type=by_type,
            resources_by_location=by_location,
            resources_by_tenant=by_tenant,
            orphaned_resources=orphaned_count,
            orphaned_estimated_cost=orphaned_cost,
            resources=items,
        )

    @cached("resource_orphaned")
    async def get_orphaned_resources(self) -> list[OrphanedResource]:
        """Get list of orphaned resources."""
        resources = (
            self.db.query(Resource)
            .filter(Resource.is_orphaned == 1)
            .order_by(Resource.estimated_monthly_cost.desc())
            .limit(100)
            .all()
        )

        # Get tenant names using cache (eliminates N+1 query)
        # OLD: tenants = {t.id: t.name for t in self.db.query(Tenant).all()}

        # Get subscription display names for lookup
        subscriptions = {
            s.subscription_id: (s.display_name or s.subscription_id)
            for s in self.db.query(Subscription).all()
        }

        now = datetime.now(UTC)

        def _get_inactive_days(resource: Resource) -> int:
            """Calculate days since resource was last synced."""
            if resource.synced_at is None:
                return 30  # Default fallback
            delta: timedelta = now - resource.synced_at
            return max(0, delta.days)

        def _get_orphan_reason(resource: Resource) -> str:
            """Determine orphan reason based on resource state."""
            if resource.provisioning_state == "Failed":
                return "provisioning_failed"
            if resource.synced_at is None:
                return "orphaned_tag"
            return "stale"

        return [
            OrphanedResource(
                resource_id=r.id,
                resource_name=r.name,
                resource_type=r.resource_type,
                tenant_name=get_tenant_name(str(r.tenant_id)) or "Unknown",
                subscription_name=subscriptions.get(r.subscription_id, r.subscription_id),
                estimated_monthly_cost=r.estimated_monthly_cost,
                days_inactive=_get_inactive_days(r),
                reason=_get_orphan_reason(r),
            )
            for r in resources
        ]

    @cached("resource_tagging")
    async def get_tagging_compliance(
        self, required_tags: list[str] | None = None
    ) -> TaggingCompliance:
        """Get tagging compliance summary."""
        if not required_tags:
            required_tags = DEFAULT_REQUIRED_TAGS

        resources = self.db.query(Resource).all()

        fully_tagged = 0
        partially_tagged = 0
        untagged = 0
        missing_tags_list = []

        for r in resources:
            tags = {}
            if r.tags_json:
                try:
                    tags = json.loads(r.tags_json)
                except json.JSONDecodeError:
                    pass

            tag_keys = set(tags.keys())
            required_set = set(required_tags)
            missing = required_set - tag_keys

            if len(missing) == 0:
                fully_tagged += 1
            elif len(missing) == len(required_tags):
                untagged += 1
                missing_tags_list.append(
                    MissingTags(
                        resource_id=r.id,
                        resource_name=r.name,
                        resource_type=r.resource_type,
                        missing_tags=list(missing),
                    )
                )
            else:
                partially_tagged += 1
                missing_tags_list.append(
                    MissingTags(
                        resource_id=r.id,
                        resource_name=r.name,
                        resource_type=r.resource_type,
                        missing_tags=list(missing),
                    )
                )

        total = len(resources)
        compliance_percent = (fully_tagged / total * 100) if total > 0 else 0

        return TaggingCompliance(
            total_resources=total,
            fully_tagged=fully_tagged,
            partially_tagged=partially_tagged,
            untagged=untagged,
            compliance_percent=compliance_percent,
            required_tags=required_tags,
            missing_tags_by_resource=missing_tags_list[:100],  # Limit output
        )

    def get_idle_resources(
        self,
        tenant_ids: list[str] | None = None,
        idle_type: str | None = None,
        is_reviewed: bool | None = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "estimated_monthly_savings",
        sort_order: str = "desc",
    ) -> list[IdleResourceSchema]:
        """Get idle resources with filtering and pagination (not cached - real-time)."""
        query = self.db.query(IdleResource)

        # Apply filters
        if tenant_ids:
            query = query.filter(IdleResource.tenant_id.in_(tenant_ids))
        if idle_type:
            query = query.filter(IdleResource.idle_type == idle_type)
        if is_reviewed is not None:
            query = query.filter(IdleResource.is_reviewed == (1 if is_reviewed else 0))

        # Apply sorting
        sort_column = getattr(IdleResource, sort_by, IdleResource.estimated_monthly_savings)
        if sort_order.lower() == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        idle_resources = query.offset(offset).limit(limit).all()

        # OLD (N+1 query): tenant_names = {t.id: t.name for t in self.db.query(Tenant).all()}

        return [
            IdleResourceSchema(
                id=r.id,
                resource_id=r.resource_id,
                tenant_id=r.tenant_id,
                tenant_name=get_tenant_name(str(r.tenant_id)) or "Unknown",
                subscription_id=r.subscription_id,
                detected_at=r.detected_at,
                idle_type=r.idle_type,
                description=r.description,
                estimated_monthly_savings=r.estimated_monthly_savings,
                idle_days=r.idle_days,
                is_reviewed=bool(r.is_reviewed),
                reviewed_by=r.reviewed_by,
                reviewed_at=r.reviewed_at,
                review_notes=r.review_notes,
            )
            for r in idle_resources
        ]

    @cached("resource_idle_summary")
    async def get_idle_resources_summary(
        self,
        tenant_ids: list[str] | None = None,
        days_threshold: int = 30,
    ) -> IdleResourceSummary:
        """Summarize idle resources across tenants.

        Args:
            tenant_ids: Optional list of tenant IDs to filter by
            days_threshold: Minimum days of inactivity to consider

        Returns:
            IdleResourceSummary with aggregated idle resource data
        """
        query = self.db.query(IdleResource).filter(IdleResource.is_reviewed == 0)
        query = query.filter(IdleResource.idle_days >= days_threshold)
        if tenant_ids:
            query = query.filter(IdleResource.tenant_id.in_(tenant_ids))
        idle_resources = query.all()

        total_count = len(idle_resources)
        total_monthly_savings = sum((r.estimated_monthly_savings or 0) for r in idle_resources)
        total_annual_savings = total_monthly_savings * 12

        # By type
        by_type: dict[str, int] = {}
        for r in idle_resources:
            by_type[r.idle_type] = by_type.get(r.idle_type, 0) + 1

        # By tenant (using cache - eliminates N+1 query)
        # OLD: tenant_names = {t.id: t.name for t in self.db.query(Tenant).all()}
        by_tenant: dict[str, int] = {}
        for r in idle_resources:
            tenant_name = get_tenant_name(str(r.tenant_id)) or "Unknown"
            by_tenant[tenant_name] = by_tenant.get(tenant_name, 0) + 1

        return IdleResourceSummary(
            total_count=total_count,
            total_potential_savings_monthly=total_monthly_savings,
            total_potential_savings_annual=total_annual_savings,
            by_type=by_type,
            by_tenant=by_tenant,
        )

    async def tag_idle_resource_as_reviewed(
        self, idle_resource_id: int, user: str, notes: str | None = None
    ) -> TagResourceResponse:
        """Tag an idle resource as reviewed."""
        idle_resource = (
            self.db.query(IdleResource).filter(IdleResource.id == idle_resource_id).first()
        )

        if not idle_resource:
            return TagResourceResponse(
                success=False,
                resource_id=str(idle_resource_id),
                tagged_at=datetime.now(UTC),
            )

        idle_resource.is_reviewed = True
        idle_resource.reviewed_by = user
        idle_resource.reviewed_at = datetime.now(UTC)
        idle_resource.review_notes = notes

        self.db.commit()

        # Invalidate cache after state change
        await invalidate_on_sync_completion(idle_resource.tenant_id)

        return TagResourceResponse(
            success=True,
            resource_id=idle_resource.resource_id,
            tagged_at=datetime.now(UTC),
        )

    async def invalidate_cache(self, tenant_id: str | None = None) -> None:
        """Invalidate resource cache after updates."""
        await invalidate_on_sync_completion(tenant_id)
