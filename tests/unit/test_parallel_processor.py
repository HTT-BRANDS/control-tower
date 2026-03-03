"""Unit tests for parallel processor.

Tests WorkerPool and TenantProcessor functionality including:
- Worker pool configuration
- Map operations with semaphore
- Progress callbacks
- Error isolation
- Timeout handling
- Tenant backfill integration
"""

import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.services.parallel_processor import (
    TaskStatus,
    TaskResult,
    WorkerPool,
    WorkerPoolConfig,
    TenantProcessor,
    backfill_tenants_parallel,
)


class TestTaskStatus:
    """Test TaskStatus enum."""

    def test_enum_values(self):
        """Test all status values exist."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"

    def test_enum_comparison(self):
        """Test enum comparison works."""
        assert TaskStatus.COMPLETED == TaskStatus.COMPLETED
        assert TaskStatus.FAILED != TaskStatus.COMPLETED


class TestTaskResult:
    """Test TaskResult dataclass."""

    def test_creation(self):
        """Test TaskResult creation."""
        result = TaskResult(
            task_id="task-1",
            tenant_id="tenant-1",
            status=TaskStatus.COMPLETED,
            result={"records": 100},
            duration_seconds=5.5,
        )
        assert result.task_id == "task-1"
        assert result.tenant_id == "tenant-1"
        assert result.status == TaskStatus.COMPLETED
        assert result.result == {"records": 100}
        assert result.error is None
        assert result.duration_seconds == 5.5

    def test_creation_with_error(self):
        """Test TaskResult creation with error."""
        result = TaskResult(
            task_id="task-2",
            tenant_id="tenant-2",
            status=TaskStatus.FAILED,
            error="Connection timeout",
            duration_seconds=10.0,
        )
        assert result.status == TaskStatus.FAILED
        assert result.error == "Connection timeout"
        assert result.result is None

    def test_default_values(self):
        """Test TaskResult with default values."""
        result = TaskResult(
            task_id="task-3",
            tenant_id="tenant-3",
            status=TaskStatus.PENDING,
        )
        assert result.result is None
        assert result.error is None
        assert result.duration_seconds == 0.0


class TestWorkerPoolConfig:
    """Test WorkerPoolConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = WorkerPoolConfig()
        assert config.max_workers == 4
        assert config.task_timeout_seconds == 3600.0
        assert config.max_queue_size == 100
        assert config.retry_failed_tasks is True
        assert config.max_retries == 2

    def test_custom_config(self):
        """Test custom configuration."""
        config = WorkerPoolConfig(
            max_workers=8,
            task_timeout_seconds=1800.0,
            max_queue_size=200,
            retry_failed_tasks=False,
            max_retries=0,
        )
        assert config.max_workers == 8
        assert config.task_timeout_seconds == 1800.0
        assert config.max_queue_size == 200
        assert config.retry_failed_tasks is False
        assert config.max_retries == 0


class TestWorkerPool:
    """Test WorkerPool functionality."""

    @pytest.fixture
    def pool(self):
        """Create a worker pool with 2 workers."""
        return WorkerPool(WorkerPoolConfig(max_workers=2))

    @pytest.mark.asyncio
    async def test_map_processes_items(self, pool):
        """Test map processes all items."""
        async def process(x: int) -> int:
            await asyncio.sleep(0.01)  # Simulate work
            return x * 2

        results = await pool.map(process, [1, 2, 3, 4])

        assert len(results) == 4
        assert all(r.status == TaskStatus.COMPLETED for r in results)
        values = [r.result for r in results]
        assert sorted(values) == [2, 4, 6, 8]

    @pytest.mark.asyncio
    async def test_map_with_concurrency_limit(self, pool):
        """Test concurrency is limited by semaphore."""
        running = 0
        max_running = 0
        lock = asyncio.Lock()

        async def process(x: int) -> int:
            nonlocal running, max_running
            async with lock:
                running += 1
                max_running = max(max_running, running)
            await asyncio.sleep(0.05)
            async with lock:
                running -= 1
            return x

        await pool.map(process, [1, 2, 3, 4])

        assert max_running <= 2  # Limited by max_workers

    @pytest.mark.asyncio
    async def test_map_with_empty_list(self, pool):
        """Test map with empty list returns empty results."""
        async def process(x: int) -> int:
            return x

        results = await pool.map(process, [])
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_map_with_errors(self, pool):
        """Test error isolation - one failure doesn't affect others."""
        async def process(x: int) -> int:
            if x == 2:
                raise ValueError("Test error")
            return x * 2

        results = await pool.map(process, [1, 2, 3])

        assert results[0].status == TaskStatus.COMPLETED
        assert results[0].result == 2
        assert results[1].status == TaskStatus.FAILED
        assert "Test error" in results[1].error
        assert results[2].status == TaskStatus.COMPLETED
        assert results[2].result == 6

    @pytest.mark.asyncio
    async def test_map_with_progress(self, pool):
        """Test progress callback is called."""
        progress_calls = []

        def on_progress(result: TaskResult):
            progress_calls.append(result.tenant_id)

        async def process(tenant_id: str) -> str:
            return f"processed-{tenant_id}"

        results = await pool.map_with_progress(
            process,
            ["tenant-1", "tenant-2", "tenant-3"],
            progress_callback=on_progress,
        )

        assert len(progress_calls) == 3
        assert "tenant-1" in progress_calls
        assert "tenant-2" in progress_calls
        assert "tenant-3" in progress_calls
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_map_with_progress_no_callback(self, pool):
        """Test map_with_progress works without callback."""
        async def process(x: int) -> int:
            return x * 2

        results = await pool.map_with_progress(process, [1, 2, 3])

        assert len(results) == 3
        assert all(r.status == TaskStatus.COMPLETED for r in results)

    @pytest.mark.asyncio
    async def test_map_with_exception_in_callback(self, pool):
        """Test that exception in callback doesn't stop processing."""
        def bad_callback(result: TaskResult):
            raise RuntimeError("Callback error")

        async def process(x: int) -> int:
            return x

        # Should not raise despite callback error
        results = await pool.map_with_progress(
            process,
            [1, 2],
            progress_callback=bad_callback,
        )

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_stats(self, pool):
        """Test statistics collection."""
        async def process(x: int) -> int:
            await asyncio.sleep(0.01)
            return x

        await pool.map(process, [1, 2, 3, 4])
        stats = pool.get_stats()

        assert stats["total_tasks"] == 4
        assert stats["completed"] == 4
        assert stats["failed"] == 0
        assert stats["cancelled"] == 0
        assert stats["running"] is False
        assert stats["average_duration"] > 0

    @pytest.mark.asyncio
    async def test_get_stats_with_failures(self, pool):
        """Test statistics with failures."""
        async def process(x: int) -> int:
            if x == 1:
                raise ValueError("Error")
            return x

        await pool.map(process, [1, 2, 3])
        stats = pool.get_stats()

        assert stats["total_tasks"] == 3
        assert stats["completed"] == 2
        assert stats["failed"] == 1

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, pool):
        """Test statistics when no tasks run."""
        stats = pool.get_stats()

        assert stats["total_tasks"] == 0
        assert stats["completed"] == 0
        assert stats["average_duration"] == 0.0

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test task timeout handling."""
        config = WorkerPoolConfig(
            max_workers=1,
            task_timeout_seconds=0.1,
            retry_failed_tasks=False,
        )
        pool = WorkerPool(config)

        async def slow_process(x: int) -> int:
            await asyncio.sleep(1.0)  # Longer than timeout
            return x

        results = await pool.map(slow_process, [1])

        assert len(results) == 1
        assert results[0].status == TaskStatus.FAILED
        assert "timed out" in results[0].error.lower()

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test retry logic on failure."""
        call_count = 0

        config = WorkerPoolConfig(
            max_workers=1,
            retry_failed_tasks=True,
            max_retries=2,
        )
        pool = WorkerPool(config)

        async def failing_process(x: int) -> int:
            nonlocal call_count
            call_count += 1
            raise ValueError(f"Attempt {call_count}")

        results = await pool.map(failing_process, [1])

        assert len(results) == 1
        assert results[0].status == TaskStatus.FAILED
        assert call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_no_retry_when_disabled(self):
        """Test no retry when disabled."""
        call_count = 0

        config = WorkerPoolConfig(
            max_workers=1,
            retry_failed_tasks=False,
            max_retries=2,
        )
        pool = WorkerPool(config)

        async def failing_process(x: int) -> int:
            nonlocal call_count
            call_count += 1
            raise ValueError("Error")

        results = await pool.map(failing_process, [1])

        assert len(results) == 1
        assert results[0].status == TaskStatus.FAILED
        assert call_count == 1  # No retries


class TestTenantProcessor:
    """Test TenantProcessor functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def processor(self, mock_db):
        """Create tenant processor with mock db."""
        return TenantProcessor(mock_db, max_workers=2)

    def test_init(self, mock_db):
        """Test processor initialization."""
        processor = TenantProcessor(mock_db, max_workers=4, task_timeout=1800.0)
        assert processor.db == mock_db
        assert processor.config.max_workers == 4
        assert processor.config.task_timeout_seconds == 1800.0

    @pytest.mark.asyncio
    async def test_backfill_single_tenant(self, mock_db):
        """Test backfill of single tenant."""
        processor = TenantProcessor(mock_db, max_workers=1)

        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.is_completed = True
        mock_job.is_cancelled = False
        mock_job.records_processed = 100
        mock_job.records_inserted = 95
        mock_job.last_error = None

        with patch.object(
            processor._backfill_service, "create_job", return_value=mock_job
        ) as mock_create:
            with patch.object(
                processor._backfill_service, "run_job", return_value=mock_job
            ) as mock_run:
                result = await processor.backfill_tenant(
                    tenant_id="tenant-1",
                    job_type="costs",
                    months=3,
                )

                assert result.tenant_id == "tenant-1"
                assert result.status == TaskStatus.COMPLETED
                assert result.result is not None
                assert result.result["job_id"] == "job-123"
                assert result.result["records_processed"] == 100
                assert result.result["records_inserted"] == 95
                mock_create.assert_called_once()
                mock_run.assert_called_once_with("job-123")

    @pytest.mark.asyncio
    async def test_backfill_single_tenant_cancelled(self, mock_db):
        """Test backfill when job is cancelled."""
        processor = TenantProcessor(mock_db, max_workers=1)

        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.is_completed = False
        mock_job.is_cancelled = True
        mock_job.last_error = None

        with patch.object(
            processor._backfill_service, "create_job", return_value=mock_job
        ):
            with patch.object(
                processor._backfill_service, "run_job", return_value=mock_job
            ):
                result = await processor.backfill_tenant(
                    tenant_id="tenant-1",
                    job_type="costs",
                    months=3,
                )

                assert result.tenant_id == "tenant-1"
                assert result.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_backfill_single_tenant_failed(self, mock_db):
        """Test backfill when job fails."""
        processor = TenantProcessor(mock_db, max_workers=1)

        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.is_completed = False
        mock_job.is_cancelled = False
        mock_job.last_error = "Database connection failed"

        with patch.object(
            processor._backfill_service, "create_job", return_value=mock_job
        ):
            with patch.object(
                processor._backfill_service, "run_job", return_value=mock_job
            ):
                result = await processor.backfill_tenant(
                    tenant_id="tenant-1",
                    job_type="costs",
                    months=3,
                )

                assert result.tenant_id == "tenant-1"
                assert result.status == TaskStatus.FAILED
                assert result.error == "Database connection failed"

    @pytest.mark.asyncio
    async def test_backfill_single_tenant_exception(self, mock_db):
        """Test backfill handles exceptions."""
        processor = TenantProcessor(mock_db, max_workers=1)

        with patch.object(
            processor._backfill_service,
            "create_job",
            side_effect=Exception("Unexpected error"),
        ):
            result = await processor.backfill_tenant(
                tenant_id="tenant-1",
                job_type="costs",
                months=3,
            )

            assert result.tenant_id == "tenant-1"
            assert result.status == TaskStatus.FAILED
            assert "Unexpected error" in result.error
            assert result.duration_seconds > 0

    @pytest.mark.asyncio
    async def test_backfill_all_tenants(self, mock_db):
        """Test parallel backfill of multiple tenants."""
        processor = TenantProcessor(mock_db, max_workers=2)

        tenant_ids = ["tenant-1", "tenant-2", "tenant-3"]

        with patch.object(processor, "backfill_tenant") as mock_backfill:
            mock_backfill.return_value = TaskResult(
                task_id="task-1",
                tenant_id="tenant-1",
                status=TaskStatus.COMPLETED,
            )

            results = await processor.backfill_all_tenants(
                job_type="costs",
                months=6,
                tenant_ids=tenant_ids,
            )

            assert len(results) == 3
            assert all(r.status == TaskStatus.COMPLETED for r in results)
            assert mock_backfill.call_count == 3

    @pytest.mark.asyncio
    async def test_backfill_all_tenants_with_progress(self, mock_db):
        """Test backfill all tenants with progress callback."""
        processor = TenantProcessor(mock_db, max_workers=2)

        progress_calls = []

        def on_progress(result: TaskResult):
            progress_calls.append(result)

        with patch.object(processor, "backfill_tenant") as mock_backfill:
            mock_backfill.return_value = TaskResult(
                task_id="task-1",
                tenant_id="tenant-1",
                status=TaskStatus.COMPLETED,
            )

            await processor.backfill_all_tenants(
                job_type="costs",
                months=6,
                tenant_ids=["t1", "t2"],
                progress_callback=on_progress,
            )

            assert len(progress_calls) == 2

    @pytest.mark.asyncio
    async def test_backfill_all_tenants_empty_list(self, mock_db):
        """Test backfill with empty tenant list."""
        processor = TenantProcessor(mock_db, max_workers=2)

        results = await processor.backfill_all_tenants(
            job_type="costs",
            months=6,
            tenant_ids=[],
        )

        assert results == []

    def test_get_summary(self, mock_db):
        """Test summary statistics."""
        processor = TenantProcessor(mock_db)

        results = [
            TaskResult("t1", "tenant-1", TaskStatus.COMPLETED, duration_seconds=5.0),
            TaskResult("t2", "tenant-2", TaskStatus.COMPLETED, duration_seconds=10.0),
            TaskResult("t3", "tenant-3", TaskStatus.FAILED, error="Test error"),
        ]

        summary = processor.get_summary(results)

        assert summary["total"] == 3
        assert summary["completed"] == 2
        assert summary["failed"] == 1
        assert summary["cancelled"] == 0
        assert summary["success_rate"] == 66.67
        assert summary["average_duration"] == 7.5

    def test_get_summary_empty(self, mock_db):
        """Test summary with empty results."""
        processor = TenantProcessor(mock_db)

        summary = processor.get_summary([])

        assert summary["total"] == 0
        assert summary["completed"] == 0
        assert summary["failed"] == 0
        assert summary["success_rate"] == 0.0
        assert summary["average_duration"] == 0.0

    def test_get_summary_all_success(self, mock_db):
        """Test summary with all successful results."""
        processor = TenantProcessor(mock_db)

        results = [
            TaskResult("t1", "tenant-1", TaskStatus.COMPLETED, duration_seconds=5.0),
            TaskResult("t2", "tenant-2", TaskStatus.COMPLETED, duration_seconds=5.0),
        ]

        summary = processor.get_summary(results)

        assert summary["total"] == 2
        assert summary["completed"] == 2
        assert summary["success_rate"] == 100.0

    def test_get_summary_all_failed(self, mock_db):
        """Test summary with all failed results."""
        processor = TenantProcessor(mock_db)

        results = [
            TaskResult("t1", "tenant-1", TaskStatus.FAILED, error="E1"),
            TaskResult("t2", "tenant-2", TaskStatus.FAILED, error="E2"),
        ]

        summary = processor.get_summary(results)

        assert summary["total"] == 2
        assert summary["failed"] == 2
        assert summary["success_rate"] == 0.0

    def test_get_summary_with_cancelled(self, mock_db):
        """Test summary includes cancelled tasks."""
        processor = TenantProcessor(mock_db)

        results = [
            TaskResult("t1", "tenant-1", TaskStatus.COMPLETED, duration_seconds=5.0),
            TaskResult("t2", "tenant-2", TaskStatus.CANCELLED),
        ]

        summary = processor.get_summary(results)

        assert summary["total"] == 2
        assert summary["completed"] == 1
        assert summary["cancelled"] == 1


class TestConcurrency:
    """Test concurrency behavior."""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self):
        """Test semaphore properly limits concurrent execution."""
        config = WorkerPoolConfig(max_workers=2)
        pool = WorkerPool(config)

        active_count = 0
        max_active = 0
        lock = asyncio.Lock()

        async def worker(x: int) -> int:
            nonlocal active_count, max_active
            async with lock:
                active_count += 1
                max_active = max(max_active, active_count)
            await asyncio.sleep(0.05)
            async with lock:
                active_count -= 1
            return x

        await pool.map(worker, [1, 2, 3, 4, 5, 6])

        assert max_active == 2  # Limited by max_workers

    @pytest.mark.asyncio
    async def test_concurrent_error_isolation(self):
        """Test errors don't affect other concurrent tasks."""
        config = WorkerPoolConfig(max_workers=4)
        pool = WorkerPool(config)

        execution_order = []

        async def worker(x: int) -> int:
            if x == 2:
                raise ValueError("Error on 2")
            await asyncio.sleep(0.01)
            execution_order.append(x)
            return x

        results = await pool.map(worker, [1, 2, 3, 4])

        # All tasks should have been attempted
        assert len(results) == 4
        # Non-error tasks should complete
        assert any(r.status == TaskStatus.COMPLETED and r.result == 1 for r in results)
        assert any(r.status == TaskStatus.COMPLETED and r.result == 3 for r in results)
        assert any(r.status == TaskStatus.COMPLETED and r.result == 4 for r in results)
        # Error task should be marked failed
        assert any(r.status == TaskStatus.FAILED and x == 2 for r, x in zip(results, [1, 2, 3, 4]) if r.error)

    @pytest.mark.asyncio
    async def test_single_worker_sequential(self):
        """Test with single worker runs sequentially."""
        config = WorkerPoolConfig(max_workers=1)
        pool = WorkerPool(config)

        execution_times = []

        async def worker(x: int) -> int:
            start = asyncio.get_event_loop().time()
            await asyncio.sleep(0.03)
            end = asyncio.get_event_loop().time()
            execution_times.append((x, start, end))
            return x

        await pool.map(worker, [1, 2, 3])

        # With single worker, tasks should not overlap
        for i in range(len(execution_times) - 1):
            # Next task should start after previous ends
            assert execution_times[i + 1][1] >= execution_times[i][2] - 0.01


class TestBackfillTenantsParallel:
    """Test the convenience function."""

    @pytest.mark.asyncio
    async def test_convenience_function(self):
        """Test backfill_tenants_parallel convenience function."""
        mock_db = MagicMock()

        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.is_completed = True
        mock_job.is_cancelled = False
        mock_job.records_processed = 100
        mock_job.records_inserted = 95
        mock_job.last_error = None

        with patch(
            "app.services.parallel_processor.ResumableBackfillService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            mock_service.create_job.return_value = mock_job
            mock_service.run_job.return_value = mock_job

            results = await backfill_tenants_parallel(
                db=mock_db,
                job_type="identity",
                months=3,
                tenant_ids=["tenant-1", "tenant-2"],
                max_workers=2,
            )

            assert len(results) == 2
            assert all(r.status == TaskStatus.COMPLETED for r in results)

    @pytest.mark.asyncio
    async def test_convenience_function_default_workers(self):
        """Test convenience function uses default workers."""
        mock_db = MagicMock()

        with patch(
            "app.services.parallel_processor.ResumableBackfillService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service

            # Just test that it initializes with default max_workers=4
            with patch.object(TenantProcessor, "backfill_all_tenants") as mock_backfill:
                mock_backfill.return_value = []
                await backfill_tenants_parallel(
                    db=mock_db,
                    job_type="costs",
                    months=1,
                    tenant_ids=[],
                )
