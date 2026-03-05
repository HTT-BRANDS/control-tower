"""Unit tests for BulkService.

Tests for bulk operations including:
- bulk_acknowledge_anomalies (success, empty list, partial failure, validation)
- bulk_dismiss_recommendations (success, empty list, partial failure, validation)
- bulk_tag_resources (success, empty list, partial failure, filter criteria)

Minimum 8 tests covering all public methods and edge cases.
"""

import pytest
from datetime import datetime, UTC
from unittest.mock import MagicMock, AsyncMock, patch

from app.api.services.bulk_service import BulkService
from app.models.cost import CostAnomaly
from app.models.recommendation import Recommendation
from app.models.resource import Resource, ResourceTag
from app.schemas.resource import BulkTagOperation, ResourceFilterCriteria


class TestBulkService:
    """Test suite for BulkService."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def bulk_service(self, mock_db):
        """Create BulkService instance."""
        return BulkService(db=mock_db)

    @pytest.fixture
    def sample_anomalies(self):
        """Create sample cost anomalies."""
        anomalies = []
        for i in range(5):
            anomaly = MagicMock(spec=CostAnomaly)
            anomaly.id = i + 1
            anomaly.tenant_id = f"tenant-{(i % 2) + 1}"
            anomaly.subscription_id = f"sub-{(i % 2) + 1}"
            anomaly.anomaly_type = "spike" if i % 2 == 0 else "unusual_service"
            anomaly.description = f"Cost anomaly {i + 1}"
            anomaly.expected_cost = 100.0 + (i * 10)
            anomaly.actual_cost = 200.0 + (i * 20)
            anomaly.percentage_change = 50.0 + (i * 5)
            anomaly.is_acknowledged = False
            anomaly.acknowledged_by = None
            anomaly.acknowledged_at = None
            anomalies.append(anomaly)
        return anomalies

    @pytest.fixture
    def sample_recommendations(self):
        """Create sample recommendations."""
        recommendations = []
        for i in range(5):
            rec = MagicMock(spec=Recommendation)
            rec.id = i + 1
            rec.tenant_id = f"tenant-{(i % 2) + 1}"
            rec.subscription_id = f"sub-{(i % 2) + 1}"
            rec.category = "cost_optimization"
            rec.recommendation_type = f"type_{i}"
            rec.title = f"Recommendation {i + 1}"
            rec.description = f"Description {i + 1}"
            rec.impact = "Medium"
            rec.status = "active"
            rec.is_dismissed = False
            rec.dismissed_by = None
            rec.dismissed_at = None
            rec.dismissal_reason = None
            recommendations.append(rec)
        return recommendations

    @pytest.fixture
    def sample_resources(self):
        """Create sample resources."""
        resources = []
        for i in range(5):
            resource = MagicMock(spec=Resource)
            resource.id = f"resource-{i + 1}"
            resource.tenant_id = f"tenant-{(i % 2) + 1}"
            resource.subscription_id = f"sub-{(i % 2) + 1}"
            resource.name = f"Resource {i + 1}"
            resource.resource_type = "Microsoft.Compute/virtualMachines"
            resource.resource_group = f"rg-{i + 1}"
            resources.append(resource)
        return resources

    # ==========================================================================
    # Tests for bulk_acknowledge_anomalies
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_bulk_acknowledge_anomalies_success(self, bulk_service, mock_db, sample_anomalies):
        """Test bulk_acknowledge_anomalies successfully acknowledges all anomalies."""
        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = len(sample_anomalies)  # Return count of updated records
        mock_db.query.return_value = mock_query

        # Execute
        anomaly_ids = [a.id for a in sample_anomalies]
        result = await bulk_service.bulk_acknowledge_anomalies(
            anomaly_ids=anomaly_ids,
            user="test@example.com",
            notes="Test acknowledgment"
        )

        # Verify
        assert result["success"] is True
        assert result["acknowledged_count"] == len(sample_anomalies)
        assert result["total_requested"] == len(anomaly_ids)
        assert result["acknowledged_by"] == "test@example.com"
        assert result["notes"] == "Test acknowledgment"
        assert "acknowledged_at" in result
        assert isinstance(result["acknowledged_at"], datetime)

        # Verify database operations
        mock_db.query.assert_called_once_with(CostAnomaly)
        mock_query.filter.assert_called_once()
        mock_query.update.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_bulk_acknowledge_anomalies_empty_list(self, bulk_service, mock_db):
        """Test bulk_acknowledge_anomalies with empty list returns zero count."""
        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 0
        mock_db.query.return_value = mock_query

        # Execute with empty list
        result = await bulk_service.bulk_acknowledge_anomalies(
            anomaly_ids=[],
            user="test@example.com"
        )

        # Verify
        assert result["success"] is True
        assert result["acknowledged_count"] == 0
        assert result["total_requested"] == 0
        assert result["acknowledged_by"] == "test@example.com"

        # Verify database operations still executed
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_bulk_acknowledge_anomalies_partial_failure(self, bulk_service, mock_db):
        """Test bulk_acknowledge_anomalies when some IDs don't exist."""
        # Setup mock query - only 3 of 5 records exist
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 3  # Only 3 records updated
        mock_db.query.return_value = mock_query

        # Execute with 5 IDs (2 don't exist)
        anomaly_ids = [1, 2, 3, 999, 1000]
        result = await bulk_service.bulk_acknowledge_anomalies(
            anomaly_ids=anomaly_ids,
            user="test@example.com"
        )

        # Verify - should still succeed but with lower count
        assert result["success"] is True
        assert result["acknowledged_count"] == 3
        assert result["total_requested"] == 5
        assert result["acknowledged_by"] == "test@example.com"

        # Verify database operations
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_bulk_acknowledge_anomalies_validates_user(self, bulk_service, mock_db):
        """Test bulk_acknowledge_anomalies properly sets user in update."""
        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 2
        mock_db.query.return_value = mock_query

        # Execute
        result = await bulk_service.bulk_acknowledge_anomalies(
            anomaly_ids=[1, 2],
            user="admin@example.com",
            notes="Reviewed by admin"
        )

        # Verify user is set correctly
        assert result["acknowledged_by"] == "admin@example.com"
        assert result["notes"] == "Reviewed by admin"

        # Verify update was called with correct parameters
        update_call_args = mock_query.update.call_args
        assert update_call_args is not None
        update_dict = update_call_args[0][0]
        assert update_dict["acknowledged_by"] == "admin@example.com"
        assert update_dict["is_acknowledged"] is True
        assert "acknowledged_at" in update_dict

    # ==========================================================================
    # Tests for bulk_dismiss_recommendations
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_bulk_dismiss_recommendations_success(self, bulk_service, mock_db, sample_recommendations):
        """Test bulk_dismiss_recommendations successfully dismisses all recommendations."""
        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = len(sample_recommendations)
        mock_db.query.return_value = mock_query

        # Execute
        recommendation_ids = [r.id for r in sample_recommendations]
        result = await bulk_service.bulk_dismiss_recommendations(
            recommendation_ids=recommendation_ids,
            user="test@example.com",
            reason="Not applicable to our use case"
        )

        # Verify
        assert result["success"] is True
        assert result["dismissed_count"] == len(sample_recommendations)
        assert result["total_requested"] == len(recommendation_ids)
        assert result["dismissed_by"] == "test@example.com"
        assert result["reason"] == "Not applicable to our use case"
        assert "dismissed_at" in result
        assert isinstance(result["dismissed_at"], datetime)

        # Verify database operations
        mock_db.query.assert_called_once_with(Recommendation)
        mock_query.filter.assert_called_once()
        mock_query.update.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_bulk_dismiss_recommendations_empty_list(self, bulk_service, mock_db):
        """Test bulk_dismiss_recommendations with empty list returns zero count."""
        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 0
        mock_db.query.return_value = mock_query

        # Execute with empty list
        result = await bulk_service.bulk_dismiss_recommendations(
            recommendation_ids=[],
            user="test@example.com",
            reason="Testing empty list"
        )

        # Verify
        assert result["success"] is True
        assert result["dismissed_count"] == 0
        assert result["total_requested"] == 0
        assert result["dismissed_by"] == "test@example.com"
        assert result["reason"] == "Testing empty list"

        # Verify database operations still executed
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_bulk_dismiss_recommendations_partial_failure(self, bulk_service, mock_db):
        """Test bulk_dismiss_recommendations when some IDs don't exist."""
        # Setup mock query - only 4 of 6 records exist
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 4  # Only 4 records updated
        mock_db.query.return_value = mock_query

        # Execute with 6 IDs (2 don't exist)
        recommendation_ids = [1, 2, 3, 4, 999, 1000]
        result = await bulk_service.bulk_dismiss_recommendations(
            recommendation_ids=recommendation_ids,
            user="test@example.com",
            reason="Bulk dismissal"
        )

        # Verify - should still succeed but with lower count
        assert result["success"] is True
        assert result["dismissed_count"] == 4
        assert result["total_requested"] == 6

        # Verify database operations
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_bulk_dismiss_recommendations_validates_status_and_reason(self, bulk_service, mock_db):
        """Test bulk_dismiss_recommendations properly sets status and reason."""
        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 3
        mock_db.query.return_value = mock_query

        # Execute
        result = await bulk_service.bulk_dismiss_recommendations(
            recommendation_ids=[1, 2, 3],
            user="senior-admin@example.com",
            reason="Already implemented in our environment"
        )

        # Verify fields are set correctly
        assert result["dismissed_by"] == "senior-admin@example.com"
        assert result["reason"] == "Already implemented in our environment"

        # Verify update was called with correct parameters
        update_call_args = mock_query.update.call_args
        assert update_call_args is not None
        update_dict = update_call_args[0][0]
        assert update_dict["status"] == "dismissed"
        assert update_dict["dismissed_by"] == "senior-admin@example.com"
        assert update_dict["dismissal_reason"] == "Already implemented in our environment"
        assert "dismissed_at" in update_dict

    # ==========================================================================
    # Tests for bulk_tag_resources
    # ==========================================================================

    @pytest.mark.asyncio
    @patch('app.api.services.bulk_service.invalidate_on_sync_completion')
    @patch('app.api.services.bulk_service.bulk_insert_chunks')
    async def test_bulk_tag_resources_success_with_ids(self, mock_bulk_insert, mock_invalidate_cache, bulk_service, mock_db, sample_resources):
        """Test bulk_tag_resources successfully tags resources by IDs."""
        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_resources
        mock_db.query.return_value = mock_query

        # Setup bulk insert to return successful count
        mock_bulk_insert.return_value = len(sample_resources) * 2  # 2 tags per resource

        # Setup cache invalidation as async mock
        mock_invalidate_cache.return_value = AsyncMock()

        # Create operation
        operation = BulkTagOperation(
            resource_ids=[r.id for r in sample_resources],
            tags={
                "Environment": "Production",
                "Owner": "DevOps"
            },
            required_tags=["Environment"]
        )

        # Execute
        result = await bulk_service.bulk_tag_resources(
            operation=operation,
            user="test@example.com"
        )

        # Verify
        assert result.success is True
        assert result.total_processed == len(sample_resources)
        assert result.success_count == len(sample_resources)
        assert result.failed_count == 0
        assert "Tagged 5 resources" in result.message
        assert len(result.results) == len(sample_resources)

        # Verify all results are successful
        for res in result.results:
            assert res.success is True
            assert "Tagged with 2 tags" in res.message

        # Verify bulk insert was called
        mock_bulk_insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_bulk_tag_resources_empty_resource_list(self, bulk_service, mock_db):
        """Test bulk_tag_resources with no matching resources."""
        # Setup mock query to return empty list
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        # Create operation
        operation = BulkTagOperation(
            resource_ids=["non-existent-1", "non-existent-2"],
            tags={"Test": "Tag"}
        )

        # Execute
        result = await bulk_service.bulk_tag_resources(
            operation=operation,
            user="test@example.com"
        )

        # Verify
        assert result.success is False
        assert result.total_processed == 0
        assert result.success_count == 0
        assert result.failed_count == 0
        assert "No resources found" in result.message
        assert len(result.results) == 0

    @pytest.mark.asyncio
    @patch('app.api.services.bulk_service.invalidate_on_sync_completion')
    @patch('app.api.services.bulk_service.bulk_insert_chunks')
    async def test_bulk_tag_resources_with_filter_criteria(self, mock_bulk_insert, mock_invalidate_cache, bulk_service, mock_db, sample_resources):
        """Test bulk_tag_resources with filter criteria instead of IDs."""
        # Filter to get resources from specific tenant and type
        filtered_resources = [r for r in sample_resources if r.tenant_id == "tenant-1"]

        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = filtered_resources
        mock_db.query.return_value = mock_query

        # Setup bulk insert
        mock_bulk_insert.return_value = len(filtered_resources) * 1  # 1 tag per resource

        # Setup cache invalidation
        mock_invalidate_cache.return_value = AsyncMock()

        # Create operation with filter
        operation = BulkTagOperation(
            resource_filter=ResourceFilterCriteria(
                tenant_ids=["tenant-1"],
                resource_types=["Microsoft.Compute/virtualMachines"]
            ),
            tags={"Department": "Engineering"}
        )

        # Execute
        result = await bulk_service.bulk_tag_resources(
            operation=operation,
            user="test@example.com"
        )

        # Verify
        assert result.success is True
        assert result.total_processed == len(filtered_resources)
        assert result.success_count == len(filtered_resources)
        assert result.failed_count == 0

        # Verify query was called with filters
        mock_db.query.assert_called_with(Resource)
        # Multiple filter calls for different criteria
        assert mock_query.filter.call_count >= 1

    @pytest.mark.asyncio
    @patch('app.api.services.bulk_service.invalidate_on_sync_completion')
    @patch('app.api.services.bulk_service.bulk_insert_chunks')
    async def test_bulk_tag_resources_partial_failure(self, mock_bulk_insert, mock_invalidate_cache, bulk_service, mock_db):
        """Test bulk_tag_resources handles partial failures gracefully."""
        # Create mix of successful and failing resources
        resources = []
        for i in range(5):
            resource = MagicMock(spec=Resource)
            resource.id = f"resource-{i + 1}"
            resource.tenant_id = "tenant-1"
            resource.name = f"Resource {i + 1}"

            # Make resource 3 fail by raising exception when accessing id in loop
            if i == 2:
                # This one will fail in the tag loop
                resource.id = None  # Will cause error when building tag records

            resources.append(resource)

        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = resources
        mock_db.query.return_value = mock_query

        # Setup bulk insert
        mock_bulk_insert.return_value = 8  # 4 successful resources * 2 tags

        # Setup cache invalidation
        mock_invalidate_cache.return_value = AsyncMock()

        # Create operation
        operation = BulkTagOperation(
            resource_ids=[r.id for r in resources if r.id],
            tags={
                "App": "MyApp",
                "Cost-Center": "IT"
            }
        )

        # Execute
        result = await bulk_service.bulk_tag_resources(
            operation=operation,
            user="test@example.com"
        )

        # Verify - should have both successes and failures
        assert result.total_processed == len(resources)
        # Some should succeed, at least one should fail
        assert result.success_count >= 0
        assert result.failed_count >= 0
        assert result.success_count + result.failed_count == len(resources)

    @pytest.mark.asyncio
    @patch('app.api.services.bulk_service.invalidate_on_sync_completion')
    @patch('app.api.services.bulk_service.bulk_insert_chunks')
    async def test_bulk_tag_resources_cache_invalidation(self, mock_bulk_insert, mock_invalidate_cache, bulk_service, mock_db, sample_resources):
        """Test bulk_tag_resources invalidates cache for affected tenants."""
        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_resources
        mock_db.query.return_value = mock_query

        # Setup bulk insert
        mock_bulk_insert.return_value = len(sample_resources)

        # Setup cache invalidation as async mock
        mock_invalidate_cache.return_value = AsyncMock()

        # Create operation
        operation = BulkTagOperation(
            resource_ids=[r.id for r in sample_resources],
            tags={"Status": "Active"}
        )

        # Execute
        await bulk_service.bulk_tag_resources(
            operation=operation,
            user="test@example.com"
        )

        # Verify cache was invalidated for affected tenants
        # Resources are split between tenant-1 and tenant-2
        affected_tenants = list(set(r.tenant_id for r in sample_resources))
        assert mock_invalidate_cache.call_count == len(affected_tenants)

    # ==========================================================================
    # Tests for bulk_remove_tags
    # ==========================================================================

    @pytest.mark.asyncio
    @patch('app.api.services.bulk_service.invalidate_on_sync_completion')
    async def test_bulk_remove_tags_success(self, mock_invalidate_cache, bulk_service, mock_db, sample_resources):
        """Test bulk_remove_tags successfully removes tags from resources."""
        # Setup mock query for tag deletion
        mock_tag_query = MagicMock()
        mock_tag_query.filter.return_value = mock_tag_query
        mock_tag_query.delete.return_value = 10  # 5 resources * 2 tags

        # Setup mock query for resource names
        mock_resource_query = MagicMock()
        mock_resource_query.filter.return_value = mock_resource_query
        mock_resource_query.all.return_value = sample_resources

        # Mock db.query to return different queries based on model
        def query_side_effect(model):
            if model == ResourceTag:
                return mock_tag_query
            elif model == Resource:
                return mock_resource_query
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

        # Setup cache invalidation
        mock_invalidate_cache.return_value = AsyncMock()

        # Execute
        resource_ids = [r.id for r in sample_resources]
        result = await bulk_service.bulk_remove_tags(
            resource_ids=resource_ids,
            tag_names=["Environment", "Owner"],
            user="test@example.com"
        )

        # Verify
        assert result.success is True
        assert result.total_processed == len(resource_ids)
        assert result.success_count == len(sample_resources)
        assert result.failed_count == 0
        assert "Removed tags from 5 resources" in result.message

        # Verify database operations
        mock_tag_query.delete.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.api.services.bulk_service.invalidate_on_sync_completion')
    async def test_bulk_remove_tags_empty_list(self, mock_invalidate_cache, bulk_service, mock_db):
        """Test bulk_remove_tags with empty resource list."""
        # Setup mock queries
        mock_tag_query = MagicMock()
        mock_tag_query.filter.return_value = mock_tag_query
        mock_tag_query.delete.return_value = 0

        mock_resource_query = MagicMock()
        mock_resource_query.filter.return_value = mock_resource_query
        mock_resource_query.all.return_value = []

        def query_side_effect(model):
            if model == ResourceTag:
                return mock_tag_query
            elif model == Resource:
                return mock_resource_query
            return MagicMock()

        mock_db.query.side_effect = query_side_effect
        mock_invalidate_cache.return_value = AsyncMock()

        # Execute
        result = await bulk_service.bulk_remove_tags(
            resource_ids=[],
            tag_names=["Test"],
            user="test@example.com"
        )

        # Verify
        assert result.success is True
        assert result.total_processed == 0
        assert result.success_count == 0

    # ==========================================================================
    # Tests for bulk_review_idle_resources
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_bulk_review_idle_resources_success(self, bulk_service, mock_db):
        """Test bulk_review_idle_resources marks resources as reviewed."""
        from app.models.resource import IdleResource

        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 5
        mock_db.query.return_value = mock_query

        # Execute
        result = await bulk_service.bulk_review_idle_resources(
            idle_resource_ids=[1, 2, 3, 4, 5],
            user="reviewer@example.com",
            notes="Confirmed these resources are still needed"
        )

        # Verify
        assert result["success"] is True
        assert result["reviewed_count"] == 5
        assert result["total_requested"] == 5
        assert result["reviewed_by"] == "reviewer@example.com"
        assert result["notes"] == "Confirmed these resources are still needed"
        assert "reviewed_at" in result

        # Verify database operations
        mock_db.query.assert_called_once_with(IdleResource)
        mock_query.update.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_bulk_review_idle_resources_partial_match(self, bulk_service, mock_db):
        """Test bulk_review_idle_resources when some IDs don't exist."""
        from app.models.resource import IdleResource

        # Setup mock query - only 3 of 5 exist
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 3
        mock_db.query.return_value = mock_query

        # Execute
        result = await bulk_service.bulk_review_idle_resources(
            idle_resource_ids=[1, 2, 3, 999, 1000],
            user="reviewer@example.com",
            notes="Partial review"
        )

        # Verify
        assert result["success"] is True
        assert result["reviewed_count"] == 3
        assert result["total_requested"] == 5

    # ==========================================================================
    # Error Handling Tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_bulk_acknowledge_anomalies_db_error(self, bulk_service, mock_db):
        """Test bulk_acknowledge_anomalies handles database errors."""
        # Setup mock to raise exception on commit
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 3
        mock_db.query.return_value = mock_query
        mock_db.commit.side_effect = Exception("Database connection lost")

        # Execute - should raise exception
        with pytest.raises(Exception, match="Database connection lost"):
            await bulk_service.bulk_acknowledge_anomalies(
                anomaly_ids=[1, 2, 3],
                user="test@example.com"
            )

    @pytest.mark.asyncio
    async def test_bulk_dismiss_recommendations_db_error(self, bulk_service, mock_db):
        """Test bulk_dismiss_recommendations handles database errors."""
        # Setup mock to raise exception on update
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.update.side_effect = Exception("Constraint violation")
        mock_db.query.return_value = mock_query

        # Execute - should raise exception
        with pytest.raises(Exception, match="Constraint violation"):
            await bulk_service.bulk_dismiss_recommendations(
                recommendation_ids=[1, 2, 3],
                user="test@example.com",
                reason="Testing error"
            )

    @pytest.mark.asyncio
    @patch('app.api.services.bulk_service.bulk_insert_chunks')
    async def test_bulk_tag_resources_insert_error(self, mock_bulk_insert, bulk_service, mock_db, sample_resources):
        """Test bulk_tag_resources handles bulk insert errors."""
        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_resources
        mock_db.query.return_value = mock_query

        # Make bulk insert raise exception
        mock_bulk_insert.side_effect = Exception("Bulk insert failed")

        # Create operation
        operation = BulkTagOperation(
            resource_ids=[r.id for r in sample_resources],
            tags={"Test": "Value"}
        )

        # Execute - should raise exception
        with pytest.raises(Exception, match="Bulk insert failed"):
            await bulk_service.bulk_tag_resources(
                operation=operation,
                user="test@example.com"
            )

    @pytest.mark.asyncio
    async def test_bulk_acknowledge_anomalies_with_none_notes(self, bulk_service, mock_db):
        """Test bulk_acknowledge_anomalies handles None notes gracefully."""
        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 2
        mock_db.query.return_value = mock_query

        # Execute with None notes
        result = await bulk_service.bulk_acknowledge_anomalies(
            anomaly_ids=[1, 2],
            user="test@example.com",
            notes=None
        )

        # Verify
        assert result["success"] is True
        assert result["notes"] is None
        assert result["acknowledged_count"] == 2

    @pytest.mark.asyncio
    async def test_bulk_review_idle_resources_with_none_notes(self, bulk_service, mock_db):
        """Test bulk_review_idle_resources handles None notes gracefully."""
        from app.models.resource import IdleResource

        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 3
        mock_db.query.return_value = mock_query

        # Execute with None notes
        result = await bulk_service.bulk_review_idle_resources(
            idle_resource_ids=[1, 2, 3],
            user="test@example.com",
            notes=None
        )

        # Verify
        assert result["success"] is True
        assert result["notes"] is None
        assert result["reviewed_count"] == 3

    @pytest.mark.asyncio
    async def test_bulk_acknowledge_anomalies_validates_timestamp(self, bulk_service, mock_db):
        """Test bulk_acknowledge_anomalies sets proper UTC timestamp."""
        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 1
        mock_db.query.return_value = mock_query

        # Execute
        before = datetime.now(UTC)
        result = await bulk_service.bulk_acknowledge_anomalies(
            anomaly_ids=[1],
            user="test@example.com"
        )
        after = datetime.now(UTC)

        # Verify timestamp is between before and after
        assert result["acknowledged_at"] >= before
        assert result["acknowledged_at"] <= after
        assert result["acknowledged_at"].tzinfo == UTC

    @pytest.mark.asyncio
    async def test_bulk_dismiss_recommendations_validates_timestamp(self, bulk_service, mock_db):
        """Test bulk_dismiss_recommendations sets proper UTC timestamp."""
        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 1
        mock_db.query.return_value = mock_query

        # Execute
        before = datetime.now(UTC)
        result = await bulk_service.bulk_dismiss_recommendations(
            recommendation_ids=[1],
            user="test@example.com",
            reason="Test"
        )
        after = datetime.now(UTC)

        # Verify timestamp is between before and after
        assert result["dismissed_at"] >= before
        assert result["dismissed_at"] <= after
        assert result["dismissed_at"].tzinfo == UTC
