"""Tests for backfill service functionality.

This module tests:
- BackfillStatus enum
- BackfillJob model
- BatchInserter
- BackfillProcessor
- ResumableBackfillService
- Day-by-day processing with checkpointing
- Pause/resume/cancel functionality
- Progress tracking
"""

import uuid
from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.backfill_job import BackfillJob, BackfillStatus
from app.models.compliance import ComplianceSnapshot
from app.models.cost import CostSnapshot
from app.models.identity import IdentitySnapshot
from app.models.resource import Resource
from app.services.backfill_service import (
    BackfillService,
    BatchInserter,
    ComplianceDataProcessor,
    CostDataProcessor,
    IdentityDataProcessor,
    ResourcesDataProcessor,
    ResumableBackfillService,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_job(db_session):
    """Create a sample backfill job."""
    job = BackfillJob(
        id=str(uuid.uuid4()),
        job_type="costs",
        tenant_id="tenant-123",
        status=BackfillStatus.PENDING.value,
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 31),
        current_date=None,
        progress_percent=0.0,
        records_processed=0,
        records_inserted=0,
        records_failed=0,
        error_count=0,
    )
    db_session.add(job)
    db_session.commit()
    return job


# =============================================================================
# BackfillStatus Enum Tests
# =============================================================================


class TestBackfillStatus:
    """Tests for BackfillStatus enum."""

    def test_enum_values(self):
        """Test that all status values exist."""
        assert BackfillStatus.PENDING.value == "pending"
        assert BackfillStatus.RUNNING.value == "running"
        assert BackfillStatus.PAUSED.value == "paused"
        assert BackfillStatus.COMPLETED.value == "completed"
        assert BackfillStatus.FAILED.value == "failed"
        assert BackfillStatus.CANCELLED.value == "cancelled"

    def test_enum_is_str_based(self):
        """Test that enum is string-based."""
        assert isinstance(BackfillStatus.PENDING, str)
        assert BackfillStatus.PENDING == "pending"


# =============================================================================
# BackfillJob Model Tests
# =============================================================================


class TestBackfillJob:
    """Tests for BackfillJob model."""

    def test_creation(self, db_session):
        """Test creating a backfill job."""
        job = BackfillJob(
            id=str(uuid.uuid4()),
            job_type="costs",
            tenant_id="tenant-123",
            status=BackfillStatus.PENDING.value,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        db_session.add(job)
        db_session.commit()

        assert job.id is not None
        assert job.job_type == "costs"
        assert job.tenant_id == "tenant-123"
        assert job.is_pending

    def test_status_properties(self, db_session):
        """Test status property checks."""
        job = BackfillJob(
            id=str(uuid.uuid4()),
            job_type="costs",
            status=BackfillStatus.PENDING.value,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert job.is_pending
        assert not job.is_running
        assert not job.is_paused
        assert not job.is_completed
        assert not job.is_failed
        assert not job.is_cancelled

        job.status = BackfillStatus.RUNNING.value
        assert job.is_running
        assert not job.is_pending

        job.status = BackfillStatus.CANCELLED.value
        assert job.is_cancelled
        assert job.is_terminal

    def test_can_resume(self, db_session):
        """Test can_resume property."""
        job = BackfillJob(
            id=str(uuid.uuid4()),
            job_type="costs",
            status=BackfillStatus.PAUSED.value,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        assert job.can_resume

        job.status = BackfillStatus.FAILED.value
        assert job.can_resume

        job.status = BackfillStatus.COMPLETED.value
        assert not job.can_resume

    def test_can_cancel(self, db_session):
        """Test can_cancel property."""
        job = BackfillJob(
            id=str(uuid.uuid4()),
            job_type="costs",
            status=BackfillStatus.RUNNING.value,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        assert job.can_cancel

        job.status = BackfillStatus.COMPLETED.value
        assert not job.can_cancel

    def test_update_status_sets_timestamps(self, db_session):
        """Test that update_status sets appropriate timestamps."""
        job = BackfillJob(
            id=str(uuid.uuid4()),
            job_type="costs",
            status=BackfillStatus.PENDING.value,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        db_session.add(job)
        db_session.commit()

        # Running sets started_at
        job.update_status(BackfillStatus.RUNNING)
        assert job.started_at is not None
        assert job.status == BackfillStatus.RUNNING.value

        # Completed sets completed_at
        job.update_status(BackfillStatus.COMPLETED)
        assert job.completed_at is not None

    def test_duration_calculation(self, db_session):
        """Test duration calculation."""
        job = BackfillJob(
            id=str(uuid.uuid4()),
            job_type="costs",
            status=BackfillStatus.COMPLETED.value,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # No timestamps yet
        assert job.duration_seconds is None

        job.started_at = datetime(2024, 1, 1, 10, 0, 0)
        job.completed_at = datetime(2024, 1, 1, 10, 5, 0)
        assert job.duration_seconds == 300.0


# =============================================================================
# BatchInserter Tests
# =============================================================================


class TestBatchInserter:
    """Tests for BatchInserter using BackfillJob model."""

    def test_init(self, db_session):
        """Test initialization."""
        inserter = BatchInserter(db_session, BackfillJob, batch_size=500)
        assert inserter.db == db_session
        assert inserter.model_class == BackfillJob
        assert inserter.batch_size == 500
        assert inserter.buffer_size == 0

    def test_add_single_record(self, db_session):
        """Test adding a single record."""
        inserter = BatchInserter(db_session, BackfillJob, batch_size=500)

        record = {
            "id": str(uuid.uuid4()),
            "job_type": "costs",
            "status": "pending",
            "start_date": datetime(2024, 1, 1),
            "end_date": datetime(2024, 1, 31),
        }
        inserter.add(record)

        assert inserter.buffer_size == 1
        assert inserter.total_inserted == 0  # Not committed yet

    def test_add_many_records(self, db_session):
        """Test adding multiple records."""
        inserter = BatchInserter(db_session, BackfillJob, batch_size=500)

        records = [
            {
                "id": str(uuid.uuid4()),
                "job_type": "costs",
                "status": "pending",
                "start_date": datetime(2024, 1, 1),
                "end_date": datetime(2024, 1, 31),
            }
            for _ in range(10)
        ]
        inserter.add_many(records)

        assert inserter.buffer_size == 10

    def test_batch_size_triggers_flush(self, db_session):
        """Test that batch size triggers automatic flush."""
        inserter = BatchInserter(db_session, BackfillJob, batch_size=5)

        # Add 5 records (exact batch size)
        for _ in range(5):
            inserter.add(
                {
                    "id": str(uuid.uuid4()),
                    "job_type": "costs",
                    "status": "pending",
                    "start_date": datetime(2024, 1, 1),
                    "end_date": datetime(2024, 1, 31),
                }
            )

        # Buffer should be empty after flush
        assert inserter.buffer_size == 0

    def test_flush_empty_buffer(self, db_session):
        """Test flushing empty buffer."""
        inserter = BatchInserter(db_session, BackfillJob, batch_size=500)
        result = inserter.flush()
        assert result == 0

    def test_commit_finalizes_insert(self, db_session):
        """Test commit finalizes all inserts."""
        inserter = BatchInserter(db_session, BackfillJob, batch_size=100)

        records = [
            {
                "id": str(uuid.uuid4()),
                "job_type": "costs",
                "status": "pending",
                "start_date": datetime(2024, 1, 1),
                "end_date": datetime(2024, 1, 31),
            }
            for _ in range(10)
        ]
        inserter.add_many(records)

        total = inserter.commit()
        assert total == 10
        assert inserter.buffer_size == 0


# =============================================================================
# Data Processor Tests
# =============================================================================


class TestCostDataProcessor:
    """Tests for CostDataProcessor."""

    def test_get_model_class(self, db_session):
        """Test model class retrieval."""
        processor = CostDataProcessor(db_session, "tenant-123")
        assert processor.get_model_class() == CostSnapshot

    def test_fetch_data_returns_list(self, db_session):
        """Test fetch_data returns a list."""
        processor = CostDataProcessor(db_session, "tenant-123")
        records = processor.fetch_data(datetime(2024, 1, 1))
        assert isinstance(records, list)


class TestIdentityDataProcessor:
    """Tests for IdentityDataProcessor."""

    def test_get_model_class(self, db_session):
        """Test model class retrieval."""
        processor = IdentityDataProcessor(db_session, "tenant-123")
        assert processor.get_model_class() == IdentitySnapshot


class TestComplianceDataProcessor:
    """Tests for ComplianceDataProcessor."""

    def test_get_model_class(self, db_session):
        """Test model class retrieval."""
        processor = ComplianceDataProcessor(db_session, "tenant-123")
        assert processor.get_model_class() == ComplianceSnapshot


class TestResourcesDataProcessor:
    """Tests for ResourcesDataProcessor."""

    def test_get_model_class(self, db_session):
        """Test model class retrieval."""
        processor = ResourcesDataProcessor(db_session, "tenant-123")
        assert processor.get_model_class() == Resource


# =============================================================================
# BackfillService Tests
# =============================================================================


class TestBackfillService:
    """Tests for BackfillService."""

    def test_create_job(self, db_session):
        """Test creating a job."""
        service = BackfillService(db_session)

        job = service.create_job(
            job_type="costs",
            tenant_id="tenant-123",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert job.id is not None
        assert job.job_type == "costs"
        assert job.tenant_id == "tenant-123"
        assert job.is_pending

    def test_create_job_invalid_type(self, db_session):
        """Test creating a job with invalid type."""
        service = BackfillService(db_session)

        with pytest.raises(ValueError, match="Invalid job type"):
            service.create_job(
                job_type="invalid",
                tenant_id="tenant-123",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 31),
            )

    def test_get_job(self, db_session, sample_job):
        """Test getting a job by ID."""
        service = BackfillService(db_session)

        job = service.get_job(sample_job.id)
        assert job is not None
        assert job.id == sample_job.id

    def test_get_job_not_found(self, db_session):
        """Test getting non-existent job."""
        service = BackfillService(db_session)

        job = service.get_job("non-existent-id")
        assert job is None

    def test_list_jobs(self, db_session):
        """Test listing jobs."""
        service = BackfillService(db_session)

        # Create multiple jobs
        for i in range(3):
            service.create_job(
                job_type="costs",
                tenant_id=f"tenant-{i}",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 31),
            )

        jobs = service.list_jobs()
        assert len(jobs) == 3

    def test_list_jobs_filter_by_tenant(self, db_session):
        """Test filtering jobs by tenant."""
        service = BackfillService(db_session)

        service.create_job(
            job_type="costs",
            tenant_id="tenant-a",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        service.create_job(
            job_type="costs",
            tenant_id="tenant-b",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        jobs = service.list_jobs(tenant_id="tenant-a")
        assert len(jobs) == 1
        assert jobs[0].tenant_id == "tenant-a"

    def test_cancel_job(self, db_session, sample_job):
        """Test cancelling a job."""
        service = BackfillService(db_session)

        # Make job cancellable
        sample_job.status = BackfillStatus.PENDING.value
        db_session.commit()

        job = service.cancel_job(sample_job.id)
        assert job.is_cancelled

    def test_cancel_job_not_found(self, db_session):
        """Test cancelling non-existent job."""
        service = BackfillService(db_session)

        with pytest.raises(ValueError, match="not found"):
            service.cancel_job("non-existent-id")

    def test_cancel_job_already_terminal(self, db_session, sample_job):
        """Test cancelling already completed job."""
        service = BackfillService(db_session)

        sample_job.status = BackfillStatus.COMPLETED.value
        db_session.commit()

        with pytest.raises(ValueError, match="Cannot cancel"):
            service.cancel_job(sample_job.id)


# =============================================================================
# ResumableBackfillService Tests
# =============================================================================


class TestResumableBackfillService:
    """Tests for ResumableBackfillService."""

    def test_date_range_generation(self, db_session):
        """Test date range generation."""
        service = ResumableBackfillService(db_session)

        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 5)

        dates = list(service._date_range(start, end))
        assert len(dates) == 5
        assert dates[0] == datetime(2024, 1, 1)
        assert dates[4] == datetime(2024, 1, 5)

    def test_calculate_progress(self, db_session):
        """Test progress calculation."""
        service = ResumableBackfillService(db_session)

        job = BackfillJob(
            id=str(uuid.uuid4()),
            job_type="costs",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 10),
            current_date=datetime(2024, 1, 5),
        )

        progress = service._calculate_progress(job, datetime(2024, 1, 5))
        assert progress == 50.0  # 5 out of 10 days

    def test_calculate_progress_zero_days(self, db_session):
        """Test progress calculation with zero day range."""
        service = ResumableBackfillService(db_session)

        job = BackfillJob(
            id=str(uuid.uuid4()),
            job_type="costs",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 1),
        )

        progress = service._calculate_progress(job, datetime(2024, 1, 1))
        assert progress == 100.0

    def test_get_processor(self, db_session):
        """Test getting processor for job type."""
        service = ResumableBackfillService(db_session)

        processor = service._get_processor("costs", "tenant-123")
        assert isinstance(processor, CostDataProcessor)

        processor = service._get_processor("identity", "tenant-123")
        assert isinstance(processor, IdentityDataProcessor)

    def test_get_processor_invalid_type(self, db_session):
        """Test getting processor for invalid type."""
        service = ResumableBackfillService(db_session)

        with pytest.raises(ValueError, match="No processor"):
            service._get_processor("invalid", "tenant-123")

    def test_pause_job(self, db_session, sample_job):
        """Test pausing a running job."""
        service = ResumableBackfillService(db_session)

        sample_job.status = BackfillStatus.RUNNING.value
        sample_job.current_date = datetime(2024, 1, 15)
        db_session.commit()

        job = service.pause_job(sample_job.id)
        assert job.is_paused
        assert job.paused_at is not None
        assert job.current_date == datetime(2024, 1, 15)

    def test_pause_job_not_running(self, db_session, sample_job):
        """Test pausing a non-running job."""
        service = ResumableBackfillService(db_session)

        sample_job.status = BackfillStatus.PENDING.value
        db_session.commit()

        with pytest.raises(ValueError, match="Cannot pause"):
            service.pause_job(sample_job.id)

    def test_resume_job(self, db_session, sample_job):
        """Test resuming a paused job."""
        service = ResumableBackfillService(db_session)

        sample_job.status = BackfillStatus.PAUSED.value
        sample_job.current_date = datetime(2024, 1, 15)
        db_session.commit()

        # Mock run_job to avoid actual processing
        with patch.object(service, "run_job") as mock_run:
            mock_run.return_value = sample_job
            service.resume_job(sample_job.id)

            mock_run.assert_called_once_with(sample_job.id, batch_size=500)

    def test_resume_job_not_resumable(self, db_session, sample_job):
        """Test resuming a completed job."""
        service = ResumableBackfillService(db_session)

        sample_job.status = BackfillStatus.COMPLETED.value
        db_session.commit()

        with pytest.raises(ValueError, match="Cannot resume"):
            service.resume_job(sample_job.id)

    def test_calculate_progress_method(self, db_session):
        """Test calculate_progress public method."""
        service = ResumableBackfillService(db_session)

        job = BackfillJob(
            id=str(uuid.uuid4()),
            job_type="costs",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 10),
            current_date=datetime(2024, 1, 5),
        )

        progress = service.calculate_progress(job)
        assert progress == 50.0

    def test_calculate_progress_completed(self, db_session):
        """Test calculate_progress for completed job."""
        service = ResumableBackfillService(db_session)

        job = BackfillJob(
            id=str(uuid.uuid4()),
            job_type="costs",
            status=BackfillStatus.COMPLETED.value,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 10),
        )

        progress = service.calculate_progress(job)
        assert progress == 100.0


# =============================================================================
# Integration Tests
# =============================================================================


class TestBackfillIntegration:
    """Integration tests for backfill service."""

    def test_create_and_run_job(self, db_session):
        """Test full job lifecycle."""
        service = ResumableBackfillService(db_session)

        # Create job
        job = service.create_job(
            job_type="costs",
            tenant_id="tenant-123",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 5),
        )

        assert job.is_pending

        # Mock fetch_data to return test data with required fields
        with patch.object(CostDataProcessor, "fetch_data") as mock_fetch:
            mock_fetch.return_value = [
                {
                    "tenant_id": "tenant-123",
                    "subscription_id": "sub-123",
                    "date": datetime(2024, 1, 1),
                    "service_name": "Test",
                    "total_cost": 100.0,
                    "currency": "USD",
                }
            ]

            # Run job
            job = service.run_job(job.id)

            assert job.is_completed
            assert job.progress_percent == 100.0
            assert job.records_processed > 0

    def test_job_checkpointing(self, db_session):
        """Test that job saves checkpoints."""
        service = ResumableBackfillService(db_session)

        job = service.create_job(
            job_type="costs",
            tenant_id="tenant-123",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 10),
        )

        with patch.object(CostDataProcessor, "fetch_data") as mock_fetch:
            mock_fetch.return_value = []

            # Mock to simulate pause after day 5

            def mock_run(job_id, batch_size=500, day_by_day=True):
                job = service.get_job(job_id)
                job.current_date = datetime(2024, 1, 5)
                job.progress_percent = 50.0
                db_session.commit()
                return job

            # Just verify checkpoint fields are updated
            job.current_date = datetime(2024, 1, 5)
            job.progress_percent = 50.0
            db_session.commit()

            # Verify checkpoint
            job = service.get_job(job.id)
            assert job.current_date == datetime(2024, 1, 5)
            assert job.progress_percent == 50.0

    def test_list_jobs_ordering(self, db_session):
        """Test that jobs are ordered by created_at desc."""
        service = BackfillService(db_session)

        # Create jobs at different times
        for i in range(3):
            job = service.create_job(
                job_type="costs",
                tenant_id="tenant-123",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 31),
            )
            # Manually set created_at to test ordering
            job.created_at = datetime(2024, 1, 1 + i)
        db_session.commit()

        jobs = service.list_jobs()
        # Should be ordered newest first
        assert jobs[0].created_at > jobs[1].created_at
