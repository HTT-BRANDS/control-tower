"""Parallel processing service for tenant backfill operations.

Provides worker pool with semaphore-based concurrency for B1 SKU (4 workers).
Supports both map() and map_with_progress() patterns with error isolation.
"""

import asyncio
import logging
import time
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Generic, TypeVar

from sqlalchemy.orm import Session

from app.services.backfill_service import ResumableBackfillService

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class TaskStatus(StrEnum):
    """Status of a parallel task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskResult(Generic[T, R]):
    """Result of a parallel task execution.

    Attributes:
        task_id: Unique task identifier
        tenant_id: Tenant being processed
        status: Final task status
        result: Task result if successful
        error: Error message if failed
        duration_seconds: Execution time
    """

    task_id: str
    tenant_id: str
    status: TaskStatus
    result: R | None = None
    error: str | None = None
    duration_seconds: float = 0.0


@dataclass
class WorkerPoolConfig:
    """Configuration for worker pool."""

    max_workers: int = 4  # B1 SKU: 4 workers
    task_timeout_seconds: float = 3600.0  # 1 hour timeout per task
    max_queue_size: int = 100
    retry_failed_tasks: bool = True
    max_retries: int = 2


class WorkerPool:
    """Worker pool with semaphore-based concurrency.

    Features:
    - Configurable worker count (default: 4 for B1 SKU)
    - Semaphore-based concurrency control
    - Task queue management
    - Error isolation per task
    - Progress tracking

    Usage:
        pool = WorkerPool(max_workers=4)

        # Simple map
        results = await pool.map(process_tenant, tenant_ids)

        # With progress
        async for result in pool.map_with_progress(process_tenant, tenant_ids):
            print(f"Completed: {result.tenant_id}")
    """

    def __init__(self, config: WorkerPoolConfig | None = None) -> None:
        """Initialize worker pool.

        Args:
            config: Worker pool configuration, uses defaults if not provided
        """
        self.config = config or WorkerPoolConfig()
        self._semaphore = asyncio.Semaphore(self.config.max_workers)
        self._task_queue: asyncio.Queue = asyncio.Queue(maxsize=self.config.max_queue_size)
        self._results: list[TaskResult] = []
        self._running = False
        self._stats = {
            "total_tasks": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "total_duration": 0.0,
        }

    async def map(
        self,
        func: Callable[[T], Coroutine[Any, Any, R]],
        items: list[T],
    ) -> list[TaskResult[T, R]]:
        """Process items in parallel with controlled concurrency.

        Args:
            func: Async function to apply to each item
            items: List of items to process

        Returns:
            List of TaskResult objects
        """
        self._running = True
        self._stats["total_tasks"] = len(items)

        # Create tasks for all items
        tasks = []
        for i, item in enumerate(items):
            task_id = f"task-{i}-{uuid.uuid4().hex[:8]}"
            # Convert item to string for tenant_id if it's a string, otherwise use index
            tenant_id = item if isinstance(item, str) else f"item-{i}"
            task = self._execute_task(task_id, tenant_id, func, item)
            tasks.append(task)

        # Run all tasks and gather results
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        self._results = []
        for result in results:
            if isinstance(result, TaskResult):
                self._results.append(result)
                if result.status == TaskStatus.COMPLETED:
                    self._stats["completed"] += 1
                    self._stats["total_duration"] += result.duration_seconds
                elif result.status == TaskStatus.FAILED:
                    self._stats["failed"] += 1
                elif result.status == TaskStatus.CANCELLED:
                    self._stats["cancelled"] += 1
            else:
                # Handle unexpected exceptions
                logger.error(f"Unexpected result type: {type(result)}")

        self._running = False
        return self._results

    async def map_with_progress(
        self,
        func: Callable[[T], Coroutine[Any, Any, R]],
        items: list[T],
        progress_callback: Callable[[TaskResult], None] | None = None,
    ) -> list[TaskResult[T, R]]:
        """Process items with progress callbacks.

        Args:
            func: Async function to apply to each item
            items: List of items to process
            progress_callback: Called after each task completes

        Returns:
            List of TaskResult objects
        """
        self._running = True
        self._stats["total_tasks"] = len(items)
        self._results = []

        # Create tasks
        pending_tasks: set[asyncio.Task] = set()
        item_map: dict[str, tuple[str, T]] = {}  # task_id -> (tenant_id, item)

        for i, item in enumerate(items):
            task_id = f"task-{i}-{uuid.uuid4().hex[:8]}"
            tenant_id = item if isinstance(item, str) else f"item-{i}"

            # Create coroutine wrapped in task
            coro = self._execute_task_with_callback(
                task_id, tenant_id, func, item, progress_callback
            )
            task = asyncio.create_task(coro)
            pending_tasks.add(task)
            item_map[task.get_name()] = (tenant_id, item)

        # Wait for all tasks to complete
        while pending_tasks:
            done, pending_tasks = await asyncio.wait(
                pending_tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                try:
                    result = task.result()
                    if isinstance(result, TaskResult):
                        self._results.append(result)
                        if result.status == TaskStatus.COMPLETED:
                            self._stats["completed"] += 1
                            self._stats["total_duration"] += result.duration_seconds
                        elif result.status == TaskStatus.FAILED:
                            self._stats["failed"] += 1
                        elif result.status == TaskStatus.CANCELLED:
                            self._stats["cancelled"] += 1
                except Exception as e:
                    logger.error(f"Task failed with exception: {e}")

        self._running = False
        return self._results

    async def _execute_task_with_callback(
        self,
        task_id: str,
        tenant_id: str,
        func: Callable[[T], Coroutine[Any, Any, R]],
        item: T,
        progress_callback: Callable[[TaskResult], None] | None,
    ) -> TaskResult[T, R]:
        """Execute task and call progress callback."""
        result = await self._execute_task(task_id, tenant_id, func, item)
        if progress_callback:
            try:
                progress_callback(result)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
        return result

    async def _execute_task(
        self,
        task_id: str,
        tenant_id: str,
        func: Callable[[T], Coroutine[Any, Any, R]],
        item: T,
    ) -> TaskResult[T, R]:
        """Execute a single task with error handling.

        Uses semaphore for concurrency control and handles:
        - Timeouts
        - Exceptions
        - Retry logic
        """
        start_time = time.monotonic()
        retries = 0

        async with self._semaphore:
            while retries <= self.config.max_retries:
                try:
                    # Execute with timeout
                    result_data = await asyncio.wait_for(
                        func(item),
                        timeout=self.config.task_timeout_seconds,
                    )

                    duration = time.monotonic() - start_time
                    return TaskResult(
                        task_id=task_id,
                        tenant_id=tenant_id,
                        status=TaskStatus.COMPLETED,
                        result=result_data,
                        duration_seconds=duration,
                    )

                except TimeoutError:
                    duration = time.monotonic() - start_time
                    if retries < self.config.max_retries and self.config.retry_failed_tasks:
                        logger.warning(
                            f"Task {task_id} timed out, retrying ({retries + 1}/{self.config.max_retries})"
                        )
                        retries += 1
                        continue
                    return TaskResult(
                        task_id=task_id,
                        tenant_id=tenant_id,
                        status=TaskStatus.FAILED,
                        error=f"Task timed out after {self.config.task_timeout_seconds}s",
                        duration_seconds=duration,
                    )

                except Exception as e:
                    duration = time.monotonic() - start_time
                    if retries < self.config.max_retries and self.config.retry_failed_tasks:
                        logger.warning(
                            f"Task {task_id} failed: {e}, retrying ({retries + 1}/{self.config.max_retries})"
                        )
                        retries += 1
                        await asyncio.sleep(0.1 * (retries + 1))  # Exponential backoff
                        continue
                    return TaskResult(
                        task_id=task_id,
                        tenant_id=tenant_id,
                        status=TaskStatus.FAILED,
                        error=str(e),
                        duration_seconds=duration,
                    )

        # Should not reach here, but just in case
        duration = time.monotonic() - start_time
        return TaskResult(
            task_id=task_id,
            tenant_id=tenant_id,
            status=TaskStatus.FAILED,
            error="Unexpected execution path",
            duration_seconds=duration,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics.

        Returns:
            Dictionary with stats:
            - total_tasks
            - completed
            - failed
            - running
            - average_duration
        """
        avg_duration = 0.0
        if self._stats["completed"] > 0:
            avg_duration = self._stats["total_duration"] / self._stats["completed"]

        return {
            "total_tasks": self._stats["total_tasks"],
            "completed": self._stats["completed"],
            "failed": self._stats["failed"],
            "cancelled": self._stats["cancelled"],
            "running": self._running,
            "average_duration": round(avg_duration, 2),
        }


class TenantProcessor:
    """Specialized processor for multi-tenant backfill operations.

    Integrates with ResumableBackfillService to process tenants in parallel.

    Usage:
        processor = TenantProcessor(db, max_workers=4)

        # Backfill all tenants for a job type
        results = await processor.backfill_all_tenants(
            job_type="costs",
            months=6,
            tenant_ids=["tenant1", "tenant2", "tenant3"],
        )
    """

    def __init__(
        self,
        db: Session,
        max_workers: int = 4,
        task_timeout: float = 3600.0,
    ) -> None:
        """Initialize tenant processor.

        Args:
            db: Database session
            max_workers: Number of parallel workers (default: 4 for B1 SKU)
            task_timeout: Timeout per tenant task in seconds
        """
        self.db = db
        self.config = WorkerPoolConfig(
            max_workers=max_workers,
            task_timeout_seconds=task_timeout,
        )
        self._pool = WorkerPool(self.config)
        self._backfill_service = ResumableBackfillService(db)

    async def backfill_tenant(
        self,
        tenant_id: str,
        job_type: str,
        months: int,
    ) -> TaskResult:
        """Backfill a single tenant.

        Args:
            tenant_id: Tenant to backfill
            job_type: Type of data (costs, identity, compliance, resources)
            months: Number of months to backfill

        Returns:
            TaskResult with backfill outcome
        """
        import time

        task_id = f"backfill-{tenant_id}-{uuid.uuid4().hex[:8]}"
        start_time = time.monotonic()

        try:
            from datetime import datetime, timedelta

            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=30 * months)

            # Create backfill job
            job = self._backfill_service.create_job(
                job_type=job_type,
                tenant_id=tenant_id,
                start_date=start_date,
                end_date=end_date,
            )

            # Run the job
            completed_job = self._backfill_service.run_job(job.id)

            duration = time.monotonic() - start_time

            if completed_job.is_completed:
                return TaskResult(
                    task_id=task_id,
                    tenant_id=tenant_id,
                    status=TaskStatus.COMPLETED,
                    result={
                        "job_id": completed_job.id,
                        "records_processed": completed_job.records_processed,
                        "records_inserted": completed_job.records_inserted,
                    },
                    duration_seconds=duration,
                )
            elif completed_job.is_cancelled:
                return TaskResult(
                    task_id=task_id,
                    tenant_id=tenant_id,
                    status=TaskStatus.CANCELLED,
                    duration_seconds=duration,
                )
            else:
                return TaskResult(
                    task_id=task_id,
                    tenant_id=tenant_id,
                    status=TaskStatus.FAILED,
                    error=completed_job.last_error or "Job failed",
                    duration_seconds=duration,
                )

        except Exception as e:
            duration = time.monotonic() - start_time
            logger.error(f"Failed to backfill tenant {tenant_id}: {e}")
            return TaskResult(
                task_id=task_id,
                tenant_id=tenant_id,
                status=TaskStatus.FAILED,
                error=str(e),
                duration_seconds=duration,
            )

    async def backfill_all_tenants(
        self,
        job_type: str,
        months: int,
        tenant_ids: list[str],
        progress_callback: Callable[[TaskResult], None] | None = None,
    ) -> list[TaskResult]:
        """Backfill all tenants in parallel.

        Args:
            job_type: Type of data to backfill
            months: Number of months to backfill
            tenant_ids: List of tenant IDs to process
            progress_callback: Optional callback for progress updates

        Returns:
            List of TaskResult objects for each tenant
        """
        if not tenant_ids:
            return []

        # Create a wrapper function that captures job_type and months
        async def process_tenant(tenant_id: str) -> dict:
            result = await self.backfill_tenant(tenant_id, job_type, months)
            # Return dict to match expected return type
            if result.result:
                return result.result
            return {"tenant_id": tenant_id, "status": result.status.value}

        # Use map_with_progress for progress tracking
        results = await self._pool.map_with_progress(
            process_tenant,
            tenant_ids,
            progress_callback=progress_callback,
        )

        return results

    def get_summary(self, results: list[TaskResult]) -> dict[str, Any]:
        """Get summary statistics from results.

        Args:
            results: List of task results

        Returns:
            Dictionary with summary statistics
        """
        total = len(results)
        if total == 0:
            return {
                "total": 0,
                "completed": 0,
                "failed": 0,
                "cancelled": 0,
                "success_rate": 0.0,
                "average_duration": 0.0,
            }

        completed = sum(1 for r in results if r.status == TaskStatus.COMPLETED)
        failed = sum(1 for r in results if r.status == TaskStatus.FAILED)
        cancelled = sum(1 for r in results if r.status == TaskStatus.CANCELLED)

        durations = [r.duration_seconds for r in results if r.duration_seconds > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        success_rate = (completed / total) * 100 if total > 0 else 0.0

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "cancelled": cancelled,
            "success_rate": round(success_rate, 2),
            "average_duration": round(avg_duration, 2),
        }


# Convenience functions
async def backfill_tenants_parallel(
    db: Session,
    job_type: str,
    months: int,
    tenant_ids: list[str],
    max_workers: int = 4,
) -> list[TaskResult]:
    """Convenience function for parallel tenant backfill.

    Args:
        db: Database session
        job_type: Type of data to backfill
        months: Number of months to backfill
        tenant_ids: List of tenant IDs
        max_workers: Number of parallel workers

    Returns:
        List of task results
    """
    processor = TenantProcessor(db, max_workers=max_workers)
    return await processor.backfill_all_tenants(job_type, months, tenant_ids)
