"""Bulk operations service for efficient batch processing.

Provides bulk operations for:
- Tagging multiple resources at once
- Acknowledging/dismissing anomalies in bulk
- Batch inserts for sync jobs (reduce transaction overhead)
"""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.cache import invalidate_on_sync_completion
from app.core.config import get_settings
from app.core.database import bulk_insert_chunks, get_db_bulk_context
from app.models.cost import CostAnomaly
from app.models.recommendation import Recommendation
from app.models.resource import IdleResource, Resource, ResourceTag
from app.schemas.resource import BulkTagOperation, BulkTagResponse, TagOperationResult

logger = logging.getLogger(__name__)
settings = get_settings()


class BulkService:
    """Service for bulk operations."""

    def __init__(self, db: Session):
        self.db = db

    # ==========================================================================
    # Bulk Tag Operations
    # ==========================================================================

    async def bulk_tag_resources(
        self,
        operation: BulkTagOperation,
        user: str,
    ) -> BulkTagResponse:
        """Apply tags to multiple resources in a single operation.

        Args:
            operation: Bulk tag operation specification
            user: User performing the operation

        Returns:
            BulkTagResponse with results
        """
        results: list[TagOperationResult] = []
        success_count = 0
        failed_count = 0

        # Get resources to tag
        query = self.db.query(Resource)

        if operation.resource_ids:
            query = query.filter(Resource.id.in_(operation.resource_ids))
        elif operation.resource_filter:
            # Apply filters
            filters = operation.resource_filter
            if filters.tenant_ids:
                query = query.filter(Resource.tenant_id.in_(filters.tenant_ids))
            if filters.resource_types:
                query = query.filter(Resource.resource_type.in_(filters.resource_types))
            if filters.subscription_ids:
                query = query.filter(Resource.subscription_id.in_(filters.subscription_ids))
            if filters.resource_group:
                query = query.filter(Resource.resource_group == filters.resource_group)
            if filters.tag_criteria:
                # Filter by existing tags (simplified - in production use JSON query)
                pass

        resources = query.all()

        if not resources:
            return BulkTagResponse(
                success=False,
                message="No resources found matching criteria",
                total_processed=0,
                success_count=0,
                failed_count=0,
                results=[],
            )

        # Prepare tag records for bulk insert
        tag_records = []
        now = datetime.now(UTC)

        for resource in resources:
            try:
                for tag_name, tag_value in operation.tags.items():
                    tag_records.append(
                        {
                            "resource_id": resource.id,
                            "tag_name": tag_name,
                            "tag_value": tag_value,
                            "is_required": tag_name in (operation.required_tags or []),
                            "synced_at": now,
                        }
                    )

                results.append(
                    TagOperationResult(
                        resource_id=resource.id,
                        resource_name=resource.name,
                        success=True,
                        message=f"Tagged with {len(operation.tags)} tags",
                    )
                )
                success_count += 1

            except Exception as e:
                logger.error(f"Failed to tag resource {resource.id}: {e}")
                results.append(
                    TagOperationResult(
                        resource_id=resource.id,
                        resource_name=resource.name,
                        success=False,
                        message=str(e),
                    )
                )
                failed_count += 1

        # Perform bulk insert if we have records
        if tag_records:
            inserted = bulk_insert_chunks(
                self.db, ResourceTag, tag_records, settings.bulk_batch_size
            )
            logger.info(f"Bulk inserted {inserted} tag records")

        # Invalidate cache for affected tenants
        tenant_ids = list({r.tenant_id for r in resources})
        for tenant_id in tenant_ids:
            await invalidate_on_sync_completion(tenant_id)

        return BulkTagResponse(
            success=failed_count == 0,
            message=f"Tagged {success_count} resources"
            + (f", {failed_count} failed" if failed_count > 0 else ""),
            total_processed=len(resources),
            success_count=success_count,
            failed_count=failed_count,
            results=results[:100],  # Limit detailed results
        )

    async def bulk_remove_tags(
        self,
        resource_ids: list[str],
        tag_names: list[str],
        user: str,
    ) -> BulkTagResponse:
        """Remove tags from multiple resources.

        Args:
            resource_ids: Resource IDs to untag
            tag_names: Tag names to remove
            user: User performing the operation

        Returns:
            BulkTagResponse with results
        """
        results: list[TagOperationResult] = []
        success_count = 0

        # Delete in bulk
        deleted = (
            self.db.query(ResourceTag)
            .filter(
                ResourceTag.resource_id.in_(resource_ids),
                ResourceTag.tag_name.in_(tag_names),
            )
            .delete(synchronize_session=False)
        )

        self.db.commit()

        logger.info(f"Bulk deleted {deleted} tag records")

        # Get resource names for results
        resources = self.db.query(Resource).filter(Resource.id.in_(resource_ids)).all()
        for resource in resources:
            results.append(
                TagOperationResult(
                    resource_id=resource.id,
                    resource_name=resource.name,
                    success=True,
                    message=f"Removed {len(tag_names)} tags",
                )
            )
            success_count += 1

        # Invalidate cache
        tenant_ids = list({r.tenant_id for r in resources})
        for tenant_id in tenant_ids:
            await invalidate_on_sync_completion(tenant_id)

        return BulkTagResponse(
            success=True,
            message=f"Removed tags from {success_count} resources",
            total_processed=len(resource_ids),
            success_count=success_count,
            failed_count=0,
            results=results[:100],
        )

    # ==========================================================================
    # Bulk Anomaly Operations
    # ==========================================================================

    async def bulk_acknowledge_anomalies(
        self,
        anomaly_ids: list[int],
        user: str,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Acknowledge multiple cost anomalies at once.

        Args:
            anomaly_ids: List of anomaly IDs to acknowledge
            user: User performing the acknowledgment
            notes: Optional notes

        Returns:
            Summary of operation results
        """
        now = datetime.now(UTC)

        # Bulk update using SQL for performance
        result = (
            self.db.query(CostAnomaly)
            .filter(CostAnomaly.id.in_(anomaly_ids))
            .update(
                {
                    "is_acknowledged": True,
                    "acknowledged_by": user,
                    "acknowledged_at": now,
                },
                synchronize_session=False,
            )
        )

        self.db.commit()

        logger.info(f"Bulk acknowledged {result} anomalies by {user}")

        return {
            "success": True,
            "acknowledged_count": result,
            "total_requested": len(anomaly_ids),
            "acknowledged_by": user,
            "acknowledged_at": now,
            "notes": notes,
        }

    async def bulk_dismiss_recommendations(
        self,
        recommendation_ids: list[int],
        user: str,
        reason: str,
    ) -> dict[str, Any]:
        """Dismiss multiple recommendations at once.

        Args:
            recommendation_ids: List of recommendation IDs to dismiss
            user: User performing the dismissal
            reason: Reason for dismissal

        Returns:
            Summary of operation results
        """
        now = datetime.now(UTC)

        # Bulk update
        result = (
            self.db.query(Recommendation)
            .filter(Recommendation.id.in_(recommendation_ids))
            .update(
                {
                    "status": "dismissed",
                    "dismissed_by": user,
                    "dismissed_at": now,
                    "dismissal_reason": reason,
                },
                synchronize_session=False,
            )
        )

        self.db.commit()

        logger.info(f"Bulk dismissed {result} recommendations by {user}")

        return {
            "success": True,
            "dismissed_count": result,
            "total_requested": len(recommendation_ids),
            "dismissed_by": user,
            "dismissed_at": now,
            "reason": reason,
        }

    # ==========================================================================
    # Bulk Idle Resource Operations
    # ==========================================================================

    async def bulk_review_idle_resources(
        self,
        idle_resource_ids: list[int],
        user: str,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Mark multiple idle resources as reviewed.

        Args:
            idle_resource_ids: List of idle resource IDs
            user: User performing the review
            notes: Optional review notes

        Returns:
            Summary of operation results
        """
        now = datetime.now(UTC)

        # Bulk update
        result = (
            self.db.query(IdleResource)
            .filter(IdleResource.id.in_(idle_resource_ids))
            .update(
                {
                    "is_reviewed": True,
                    "reviewed_by": user,
                    "reviewed_at": now,
                    "review_notes": notes,
                },
                synchronize_session=False,
            )
        )

        self.db.commit()

        logger.info(f"Bulk reviewed {result} idle resources by {user}")

        return {
            "success": True,
            "reviewed_count": result,
            "total_requested": len(idle_resource_ids),
            "reviewed_by": user,
            "reviewed_at": now,
            "notes": notes,
        }

    # ==========================================================================
    # Batch Sync Operations
    # ==========================================================================

    @staticmethod
    def batch_sync_resources(
        resources_data: list[dict],
        tenant_id: str,
    ) -> dict[str, Any]:
        """Batch insert resources during sync for better performance.

        Uses bulk insert in chunks to reduce transaction overhead.

        Args:
            resources_data: List of resource dictionaries
            tenant_id: Tenant ID for these resources

        Returns:
            Summary of sync operation
        """
        if not resources_data:
            return {"inserted": 0, "updated": 0, "errors": 0}

        # Add tenant_id to all records
        for record in resources_data:
            record["tenant_id"] = tenant_id

        inserted = 0
        updated = 0
        errors = 0

        with get_db_bulk_context() as db:
            try:
                # Use bulk insert for new records
                inserted = bulk_insert_chunks(
                    db, Resource, resources_data, settings.bulk_batch_size
                )
                logger.info(f"Batch synced {inserted} resources for tenant {tenant_id}")
            except Exception as e:
                logger.error(f"Batch sync error: {e}")
                errors = len(resources_data)

        return {
            "inserted": inserted,
            "updated": updated,
            "errors": errors,
            "total": len(resources_data),
        }

    @staticmethod
    def batch_sync_costs(
        costs_data: list[dict],
        tenant_id: str,
    ) -> dict[str, Any]:
        """Batch insert cost snapshots during sync.

        Args:
            costs_data: List of cost snapshot dictionaries
            tenant_id: Tenant ID for these records

        Returns:
            Summary of sync operation
        """
        from app.models.cost import CostSnapshot

        if not costs_data:
            return {"inserted": 0, "errors": 0}

        for record in costs_data:
            record["tenant_id"] = tenant_id

        with get_db_bulk_context() as db:
            inserted = bulk_insert_chunks(db, CostSnapshot, costs_data, settings.bulk_batch_size)

        return {
            "inserted": inserted,
            "errors": 0,
            "total": len(costs_data),
        }

    @staticmethod
    def batch_sync_compliance(
        policy_states_data: list[dict],
        tenant_id: str,
    ) -> dict[str, Any]:
        """Batch insert compliance policy states during sync.

        Args:
            policy_states_data: List of policy state dictionaries
            tenant_id: Tenant ID for these records

        Returns:
            Summary of sync operation
        """
        from app.models.compliance import PolicyState

        if not policy_states_data:
            return {"inserted": 0, "errors": 0}

        for record in policy_states_data:
            record["tenant_id"] = tenant_id

        with get_db_bulk_context() as db:
            inserted = bulk_insert_chunks(
                db, PolicyState, policy_states_data, settings.bulk_batch_size
            )

        return {
            "inserted": inserted,
            "errors": 0,
            "total": len(policy_states_data),
        }

    @staticmethod
    def batch_sync_identities(
        identity_data: list[dict],
        tenant_id: str,
    ) -> dict[str, Any]:
        """Batch insert identity data during sync.

        Args:
            identity_data: List of privileged user dictionaries
            tenant_id: Tenant ID for these records

        Returns:
            Summary of sync operation
        """
        from app.models.identity import PrivilegedUser

        if not identity_data:
            return {"inserted": 0, "errors": 0}

        for record in identity_data:
            record["tenant_id"] = tenant_id

        with get_db_bulk_context() as db:
            inserted = bulk_insert_chunks(
                db, PrivilegedUser, identity_data, settings.bulk_batch_size
            )

        return {
            "inserted": inserted,
            "errors": 0,
            "total": len(identity_data),
        }
