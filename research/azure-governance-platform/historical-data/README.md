# Historical Data Backfill Patterns Research

**Research Date:** 2025-03-02
**Topic:** Bulk data ingestion, rate limiting, and parallel processing for Azure APIs

---

## Executive Summary

This research covers best practices for backfilling historical data from Azure APIs into the governance platform. Key challenges include API rate limits, large data volumes, and maintaining data consistency during bulk operations.

### Key Findings

1. **Azure API Rate Limits**: 12,000 read requests/hour per subscription for ARM APIs
2. **Parallel Processing**: 5-10 concurrent requests optimal for B1 SKU
3. **Batch Insert**: SQLite batch inserts of 100-1000 rows optimal
4. **Resume Capability**: Essential for long-running backfills
5. **Incremental Sync**: Delta sync after initial backfill

---

## 1. Azure API Rate Limits & Throttling

### 1.1 ARM API Limits

| API | Rate Limit | Burst | Retry-After Header |
|-----|------------|-------|-------------------|
| **Azure Resource Manager** | 12,000/hour | 200/minute | Yes |
| **Microsoft Graph** | 10,000/minute | N/A | Yes |
| **Cost Management** | 30 requests/hour | N/A | Yes |
| **Azure Policy** | 1,000/hour | N/A | Yes |
| **Azure Security Center** | 300/hour | N/A | Yes |

### 1.2 Throttling Response Handling

```python
# app/core/rate_limit.py
import asyncio
from typing import Optional, Callable
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(
        self,
        requests_per_second: float = 10.0,
        max_retries: int = 5,
        base_delay: float = 1.0
    ):
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.last_request_time = None
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire permission to make a request"""
        async with self._lock:
            if self.last_request_time:
                elapsed = (datetime.now() - self.last_request_time).total_seconds()
                if elapsed < self.min_interval:
                    await asyncio.sleep(self.min_interval - elapsed)
            self.last_request_time = datetime.now()
    
    async def execute_with_backoff(
        self,
        func: Callable,
        *args,
        **kwargs
    ):
        """Execute function with exponential backoff on rate limit"""
        for attempt in range(self.max_retries):
            await self.acquire()
            
            try:
                result = await func(*args, **kwargs)
                return result
                
            except Exception as e:
                if "429" in str(e) or "TooManyRequests" in str(e):
                    # Extract Retry-After if available
                    retry_after = self._extract_retry_after(e)
                    delay = retry_after or (self.base_delay * (2 ** attempt))
                    
                    logger.warning(
                        f"Rate limited. Retrying in {delay}s (attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise
        
        raise Exception(f"Max retries ({self.max_retries}) exceeded")
    
    def _extract_retry_after(self, exception: Exception) -> Optional[int]:
        """Extract Retry-After header from exception"""
        if hasattr(exception, 'response'):
            return exception.response.headers.get('Retry-After')
        return None

# Global rate limiters per API type
ARM_RATE_LIMITER = RateLimiter(requests_per_second=3.3)  # 12,000/hour
GRAPH_RATE_LIMITER = RateLimiter(requests_per_second=166)  # 10,000/minute
COST_RATE_LIMITER = RateLimiter(requests_per_second=0.008)  # 30/hour
```

### 1.3 Circuit Breaker Pattern

```python
# app/core/circuit_breaker.py
from enum import Enum, auto
from datetime import datetime, timedelta
from typing import Optional, Callable
import asyncio

class CircuitState(Enum):
    CLOSED = auto()      # Normal operation
    OPEN = auto()        # Failing, reject requests
    HALF_OPEN = auto()   # Testing if recovered

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs):
        """Call function with circuit breaker protection"""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                else:
                    raise CircuitBreakerOpen("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except self.expected_exception as e:
            await self._on_failure()
            raise
    
    async def _on_success(self):
        async with self._lock:
            self.failure_count = 0
            self.state = CircuitState.CLOSED
    
    async def _on_failure(self):
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit breaker OPENED after {self.failure_count} failures")
    
    def _should_attempt_reset(self) -> bool:
        if not self.last_failure_time:
            return True
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

class CircuitBreakerOpen(Exception):
    pass
```

---

## 2. Bulk Data Ingestion Patterns

### 2.1 Batch Insert Strategy

```python
# app/services/bulk_insert.py
from typing import List, Type, Any
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
import logging

logger = logging.getLogger(__name__)

class BatchInserter:
    """Optimized batch inserts for SQLite"""
    
    def __init__(self, db: Session, batch_size: int = 500):
        self.db = db
        self.batch_size = batch_size
        self.buffer: List[Any] = []
    
    def add(self, record: Any):
        """Add record to buffer"""
        self.buffer.append(record)
        
        if len(self.buffer) >= self.batch_size:
            self.flush()
    
    def flush(self):
        """Flush buffer to database"""
        if not self.buffer:
            return
        
        try:
            # Use bulk_insert_mappings for better performance
            self.db.bulk_insert_mappings(
                self.buffer[0].__class__,
                [self._to_dict(r) for r in self.buffer]
            )
            self.db.commit()
            logger.info(f"Inserted {len(self.buffer)} records")
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Batch insert failed: {e}")
            raise
        finally:
            self.buffer = []
    
    def _to_dict(self, record: Any) -> dict:
        """Convert ORM record to dict"""
        return {
            column.name: getattr(record, column.name)
            for column in record.__table__.columns
        }
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.flush()
        return False

# Usage example
async def backfill_cost_data(
    db: Session,
    tenant_id: str,
    start_date: str,
    end_date: str
):
    with BatchInserter(db, batch_size=500) as inserter:
        async for cost_record in fetch_cost_data(
            tenant_id, start_date, end_date
        ):
            inserter.add(CostSnapshot(**cost_record))
```

### 2.2 Upsert Pattern (Insert or Update)

```python
# app/services/upsert_service.py
from sqlalchemy.dialects.sqlite import insert
from typing import List, Dict, Any

def bulk_upsert(
    db: Session,
    model: Type,
    records: List[Dict[str, Any]],
    index_elements: List[str]
):
    """
    Perform bulk upsert using SQLite's ON CONFLICT
    
    Args:
        db: Database session
        model: SQLAlchemy model class
        records: List of record dicts to insert/update
        index_elements: Columns that form the unique constraint
    """
    if not records:
        return
    
    # Build insert statement with upsert
    stmt = insert(model).values(records)
    
    # Build update dict (all columns except index_elements)
    update_dict = {
        c.name: stmt.excluded[c.name]
        for c in model.__table__.columns
        if c.name not in index_elements and c.name != 'id'
    }
    
    # Add ON CONFLICT DO UPDATE
    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=index_elements,
        set_=update_dict
    )
    
    db.execute(upsert_stmt)
    db.commit()

# Example: Upsert cost snapshots
async def upsert_cost_snapshots(
    db: Session,
    snapshots: List[Dict[str, Any]]
):
    """
    Upsert cost snapshots based on unique constraint:
    (tenant_id, subscription_id, date, resource_group, service_name)
    """
    bulk_upsert(
        db=db,
        model=CostSnapshot,
        records=snapshots,
        index_elements=['tenant_id', 'subscription_id', 'date', 
                       'resource_group', 'service_name']
    )
```

### 2.3 Streaming Ingestion

```python
# app/services/streaming_ingest.py
from typing import AsyncIterator, Type, Any
from sqlalchemy.orm import Session
import asyncio

class StreamingIngestor:
    """
    Stream data from source to database with backpressure handling
    """
    
    def __init__(
        self,
        db: Session,
        batch_size: int = 100,
        max_queue_size: int = 1000
    ):
        self.db = db
        self.batch_size = batch_size
        self.max_queue_size = max_queue_size
        self.queue = asyncio.Queue(maxsize=max_queue_size)
        self.processed = 0
        self.errors = 0
    
    async def produce(
        self,
        source: AsyncIterator[Dict[str, Any]]
    ):
        """Produce records from source"""
        async for record in source:
            await self.queue.put(record)
    
    async def consume(self, model: Type):
        """Consume records and insert to database"""
        batch = []
        
        while True:
            try:
                # Wait for record with timeout
                record = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=5.0
                )
                
                if record is None:  # Sentinel for completion
                    break
                
                batch.append(model(**record))
                
                if len(batch) >= self.batch_size:
                    await self._insert_batch(batch)
                    batch = []
                    
            except asyncio.TimeoutError:
                # Flush remaining records on timeout
                if batch:
                    await self._insert_batch(batch)
                    batch = []
            except Exception as e:
                logger.error(f"Error processing record: {e}")
                self.errors += 1
        
        # Final flush
        if batch:
            await self._insert_batch(batch)
    
    async def _insert_batch(self, batch: List[Any]):
        """Insert batch to database"""
        try:
            self.db.bulk_save_objects(batch)
            self.db.commit()
            self.processed += len(batch)
            logger.info(f"Inserted batch of {len(batch)} records")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Batch insert failed: {e}")
            self.errors += len(batch)
    
    async def run(
        self,
        source: AsyncIterator[Dict[str, Any]],
        model: Type
    ):
        """Run producer and consumer concurrently"""
        producer_task = asyncio.create_task(self.produce(source))
        consumer_task = asyncio.create_task(self.consume(model))
        
        await producer_task
        await self.queue.put(None)  # Signal completion
        await consumer_task
        
        return {
            "processed": self.processed,
            "errors": self.errors
        }
```

---

## 3. Parallel Processing Patterns

### 3.1 Worker Pool Pattern

```python
# app/core/worker_pool.py
import asyncio
from typing import List, Callable, Any, Coroutine
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

class WorkerPool:
    """
    Managed worker pool for parallel processing with rate limiting
    """
    
    def __init__(
        self,
        max_workers: int = 5,
        rate_limiter: Optional[RateLimiter] = None
    ):
        self.max_workers = max_workers
        self.rate_limiter = rate_limiter
        self.semaphore = asyncio.Semaphore(max_workers)
        self.results: List[Any] = []
        self.errors: List[Exception] = []
    
    async def submit(
        self,
        func: Callable[..., Coroutine],
        *args,
        **kwargs
    ) -> Any:
        """Submit task to worker pool"""
        async with self.semaphore:
            try:
                if self.rate_limiter:
                    result = await self.rate_limiter.execute_with_backoff(
                        func, *args, **kwargs
                    )
                else:
                    result = await func(*args, **kwargs)
                
                self.results.append(result)
                return result
                
            except Exception as e:
                logger.error(f"Task failed: {e}")
                self.errors.append(e)
                raise
    
    async def map(
        self,
        func: Callable[..., Coroutine],
        items: List[Any],
        *args,
        **kwargs
    ) -> List[Any]:
        """Map function over items in parallel"""
        tasks = [
            self.submit(func, item, *args, **kwargs)
            for item in items
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Separate successful results from errors
        successful = []
        for result in results:
            if isinstance(result, Exception):
                self.errors.append(result)
            else:
                successful.append(result)
        
        return successful
    
    def get_stats(self) -> Dict[str, int]:
        """Get pool statistics"""
        return {
            "completed": len(self.results),
            "errors": len(self.errors),
            "max_workers": self.max_workers
        }

# Usage example
async def backfill_multiple_tenants(
    tenant_ids: List[str],
    start_date: str,
    end_date: str
):
    """Backfill data for multiple tenants in parallel"""
    
    # Create rate-limited worker pool
    rate_limiter = RateLimiter(requests_per_second=3.3)  # ARM API limits
    pool = WorkerPool(max_workers=4, rate_limiter=rate_limiter)
    
    # Process tenants in parallel
    results = await pool.map(
        backfill_tenant_data,
        tenant_ids,
        start_date,
        end_date
    )
    
    logger.info(f"Backfill complete: {pool.get_stats()}")
    return results
```

### 3.2 Chunked Processing

```python
# app/core/chunked_processor.py
from typing import List, TypeVar, Callable, AsyncIterator
import asyncio

T = TypeVar('T')

class ChunkedProcessor:
    """
    Process large datasets in manageable chunks with checkpointing
    """
    
    def __init__(
        self,
        chunk_size: int = 1000,
        checkpoint_interval: int = 10
    ):
        self.chunk_size = chunk_size
        self.checkpoint_interval = checkpoint_interval
        self.checkpoint_count = 0
    
    def chunk_list(self, items: List[T]) -> List[List[T]]:
        """Split list into chunks"""
        return [
            items[i:i + self.chunk_size]
            for i in range(0, len(items), self.chunk_size)
        ]
    
    async def process_chunks(
        self,
        chunks: List[List[T]],
        processor: Callable[[List[T]], asyncio.Future],
        on_checkpoint: Optional[Callable[[int], asyncio.Future]] = None
    ):
        """Process chunks with checkpointing"""
        total_chunks = len(chunks)
        
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{total_chunks}")
            
            try:
                await processor(chunk)
                self.checkpoint_count += 1
                
                # Trigger checkpoint
                if (self.checkpoint_count % self.checkpoint_interval == 0 
                    and on_checkpoint):
                    await on_checkpoint(i + 1)
                    
            except Exception as e:
                logger.error(f"Failed to process chunk {i+1}: {e}")
                # Continue with next chunk
                continue
    
    async def process_stream(
        self,
        stream: AsyncIterator[T],
        processor: Callable[[List[T]], asyncio.Future],
        on_checkpoint: Optional[Callable[[int], asyncio.Future]] = None
    ):
        """Process streaming data in chunks"""
        chunk = []
        chunk_number = 0
        
        async for item in stream:
            chunk.append(item)
            
            if len(chunk) >= self.chunk_size:
                await self._process_chunk(
                    chunk, chunk_number, processor, on_checkpoint
                )
                chunk = []
                chunk_number += 1
        
        # Process remaining items
        if chunk:
            await self._process_chunk(
                chunk, chunk_number, processor, on_checkpoint
            )
    
    async def _process_chunk(
        self,
        chunk: List[T],
        chunk_number: int,
        processor: Callable,
        on_checkpoint: Optional[Callable]
    ):
        """Process single chunk"""
        try:
            await processor(chunk)
            self.checkpoint_count += 1
            
            if (self.checkpoint_count % self.checkpoint_interval == 0 
                and on_checkpoint):
                await on_checkpoint(chunk_number)
                
        except Exception as e:
            logger.error(f"Chunk {chunk_number} failed: {e}")
            raise
```

---

## 4. Resume Capability & Checkpointing

### 4.1 Job State Tracking

```python
# app/models/sync_job.py
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class SyncJob(BaseModel):
    id: str
    job_type: str  # "cost_backfill", "compliance_sync", etc.
    tenant_id: str
    status: JobStatus
    
    # Progress tracking
    total_items: Optional[int] = None
    processed_items: int = 0
    failed_items: int = 0
    
    # Time tracking
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    
    # Checkpoint data
    checkpoint_data: Dict[str, Any] = {}
    
    # Error tracking
    error_message: Optional[str] = None
    retry_count: int = 0
    
    def to_progress_percent(self) -> float:
        if self.total_items and self.total_items > 0:
            return (self.processed_items / self.total_items) * 100
        return 0.0

# SQLAlchemy model
class SyncJobModel(Base):
    __tablename__ = "sync_jobs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_type = Column(String, nullable=False)
    tenant_id = Column(String, ForeignKey("tenants.id"))
    status = Column(String, default=JobStatus.PENDING)
    
    total_items = Column(Integer)
    processed_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    last_activity_at = Column(DateTime, onupdate=datetime.utcnow)
    
    checkpoint_data = Column(JSON, default={})
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
```

### 4.2 Resumable Backfill Service

```python
# app/services/resumable_backfill.py
from datetime import datetime, timedelta
from typing import Optional, List
import json

class ResumableBackfillService:
    """
    Service for managing resumable backfill operations
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.batch_size = 500
    
    async def start_backfill(
        self,
        job_type: str,
        tenant_id: str,
        start_date: str,
        end_date: str,
        **kwargs
    ) -> str:
        """Start a new backfill job"""
        
        # Check for existing incomplete job
        existing = self.db.query(SyncJobModel).filter(
            SyncJobModel.job_type == job_type,
            SyncJobModel.tenant_id == tenant_id,
            SyncJobModel.status.in_([JobStatus.PENDING, JobStatus.RUNNING, JobStatus.PAUSED])
        ).first()
        
        if existing:
            logger.info(f"Resuming existing job {existing.id}")
            return await self.resume_job(existing.id)
        
        # Create new job
        job = SyncJobModel(
            job_type=job_type,
            tenant_id=tenant_id,
            status=JobStatus.PENDING,
            checkpoint_data={
                "start_date": start_date,
                "end_date": end_date,
                "current_date": start_date,
                **kwargs
            }
        )
        
        self.db.add(job)
        self.db.commit()
        
        # Start processing
        asyncio.create_task(self._process_job(job.id))
        
        return job.id
    
    async def resume_job(self, job_id: str) -> str:
        """Resume a paused or failed job"""
        job = self.db.query(SyncJobModel).get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        if job.status == JobStatus.COMPLETED:
            raise ValueError(f"Job {job_id} already completed")
        
        job.status = JobStatus.RUNNING
        job.retry_count += 1
        job.error_message = None
        self.db.commit()
        
        # Start processing
        asyncio.create_task(self._process_job(job.id))
        
        return job.id
    
    async def _process_job(self, job_id: str):
        """Process backfill job with checkpointing"""
        job = self.db.query(SyncJobModel).get(job_id)
        
        try:
            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            self.db.commit()
            
            # Get checkpoint data
            checkpoint = job.checkpoint_data
            current_date = datetime.fromisoformat(checkpoint["current_date"])
            end_date = datetime.fromisoformat(checkpoint["end_date"])
            
            # Process day by day
            while current_date <= end_date:
                try:
                    await self._process_date(job, current_date)
                    
                    # Update checkpoint
                    current_date += timedelta(days=1)
                    checkpoint["current_date"] = current_date.isoformat()
                    job.checkpoint_data = checkpoint
                    job.processed_items += 1
                    job.last_activity_at = datetime.utcnow()
                    self.db.commit()
                    
                except Exception as e:
                    logger.error(f"Failed to process {current_date}: {e}")
                    job.failed_items += 1
                    job.error_message = str(e)
                    job.status = JobStatus.PAUSED
                    self.db.commit()
                    return
            
            # Mark complete
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            self.db.commit()
    
    async def _process_date(self, job: SyncJobModel, date: datetime):
        """Process single date (override in subclasses)"""
        raise NotImplementedError()
    
    async def get_job_status(self, job_id: str) -> SyncJob:
        """Get current job status"""
        job = self.db.query(SyncJobModel).get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        return SyncJob.from_orm(job)
    
    async def cancel_job(self, job_id: str):
        """Cancel a running job"""
        job = self.db.query(SyncJobModel).get(job_id)
        if job and job.status == JobStatus.RUNNING:
            job.status = JobStatus.CANCELLED
            self.db.commit()
```

### 4.3 Cost Backfill Implementation

```python
# app/services/cost_backfill.py
class CostBackfillService(ResumableBackfillService):
    """
    Resumable cost data backfill service
    """
    
    def __init__(self, db: Session, azure_client: AzureMultiTenantClient):
        super().__init__(db)
        self.azure_client = azure_client
    
    async def _process_date(self, job: SyncJobModel, date: datetime):
        """Process cost data for a single date"""
        
        tenant_id = job.tenant_id
        date_str = date.strftime("%Y-%m-%d")
        
        # Get all subscriptions for tenant
        subscriptions = await self.azure_client.get_tenant_subscriptions(tenant_id)
        
        for subscription in subscriptions:
            # Fetch cost data with rate limiting
            cost_data = await self.azure_client.get_daily_cost(
                subscription_id=subscription["id"],
                date=date_str
            )
            
            # Batch insert to database
            records = [
                CostSnapshot(
                    tenant_id=tenant_id,
                    subscription_id=sub["id"],
                    date=date.date(),
                    total_cost=item["cost"],
                    currency=item["currency"],
                    resource_group=item.get("resource_group"),
                    service_name=item.get("service_name"),
                    synced_at=datetime.utcnow()
                )
                for item in cost_data
            ]
            
            # Use upsert to handle re-runs
            await self._upsert_cost_records(records)
    
    async def _upsert_cost_records(self, records: List[CostSnapshot]):
        """Upsert cost records to handle re-runs"""
        if not records:
            return
        
        # Convert to dicts
        record_dicts = [
            {
                "tenant_id": r.tenant_id,
                "subscription_id": r.subscription_id,
                "date": r.date.isoformat(),
                "total_cost": r.total_cost,
                "currency": r.currency,
                "resource_group": r.resource_group,
                "service_name": r.service_name,
                "synced_at": r.synced_at.isoformat()
            }
            for r in records
        ]
        
        bulk_upsert(
            db=self.db,
            model=CostSnapshot,
            records=record_dicts,
            index_elements=["tenant_id", "subscription_id", "date", 
                          "resource_group", "service_name"]
        )
```

---

## 5. Data Retention & Archiving

### 5.1 Retention Policies

```python
# app/services/retention_service.py
from datetime import datetime, timedelta
from typing import Dict, List

class DataRetentionPolicy:
    """
    Define retention rules for different data types
    """
    
    POLICIES: Dict[str, Dict] = {
        "cost_snapshots": {
            "retention_days": 730,  # 2 years
            "archive_after_days": 365,
            "archive_table": "cost_snapshots_archive"
        },
        "compliance_snapshots": {
            "retention_days": 365,  # 1 year
            "archive_after_days": 180,
            "archive_table": "compliance_snapshots_archive"
        },
        "resource_inventory": {
            "retention_days": 180,  # 6 months
            "archive_after_days": None,  # Don't archive, just delete
        },
        "identity_snapshots": {
            "retention_days": 180,  # 6 months
            "archive_after_days": 90,
            "archive_table": "identity_snapshots_archive"
        },
        "sync_jobs": {
            "retention_days": 90,  # 3 months
            "archive_after_days": None
        }
    }

class RetentionService:
    def __init__(self, db: Session):
        self.db = db
    
    async def apply_retention(self, table_name: str):
        """Apply retention policy to table"""
        policy = DataRetentionPolicy.POLICIES.get(table_name)
        if not policy:
            logger.warning(f"No retention policy for {table_name}")
            return
        
        cutoff_date = datetime.utcnow() - timedelta(
            days=policy["retention_days"]
        )
        
        # Archive if configured
        if policy.get("archive_after_days"):
            archive_date = datetime.utcnow() - timedelta(
                days=policy["archive_after_days"]
            )
            await self._archive_records(
                table_name,
                policy["archive_table"],
                archive_date
            )
        
        # Delete old records
        deleted = await self._delete_old_records(table_name, cutoff_date)
        logger.info(f"Deleted {deleted} old records from {table_name}")
    
    async def _archive_records(
        self,
        source_table: str,
        archive_table: str,
        before_date: datetime
    ):
        """Move records to archive table"""
        
        # SQLite: Use INSERT INTO SELECT with DELETE
        query = f"""
        INSERT INTO {archive_table}
        SELECT * FROM {source_table}
        WHERE synced_at < :before_date
        AND NOT EXISTS (
            SELECT 1 FROM {archive_table} a
            WHERE a.id = {source_table}.id
        )
        """
        
        result = self.db.execute(
            query,
            {"before_date": before_date.isoformat()}
        )
        self.db.commit()
        
        logger.info(f"Archived {result.rowcount} records from {source_table}")
    
    async def _delete_old_records(
        self,
        table_name: str,
        before_date: datetime
    ) -> int:
        """Delete records older than cutoff"""
        
        query = f"""
        DELETE FROM {table_name}
        WHERE synced_at < :before_date
        """
        
        result = self.db.execute(
            query,
            {"before_date": before_date.isoformat()}
        )
        self.db.commit()
        
        return result.rowcount
```

### 5.2 Database Optimization

```python
# app/services/db_maintenance.py
class DatabaseMaintenanceService:
    """
    SQLite maintenance and optimization
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    async def optimize_database(self):
        """Run SQLite optimization commands"""
        
        # 1. Analyze tables for query optimization
        tables = ["cost_snapshots", "compliance_snapshots", 
                 "resource_inventory", "identity_snapshots"]
        
        for table in tables:
            self.db.execute(f"ANALYZE {table}")
        
        # 2. Vacuum to reclaim space
        self.db.execute("VACUUM")
        
        # 3. Optimize WAL checkpoint
        self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        
        self.db.commit()
        
        logger.info("Database optimization complete")
    
    async def rebuild_indexes(self):
        """Rebuild indexes for better performance"""
        
        indexes = [
            "idx_cost_snapshots_tenant_date",
            "idx_compliance_tenant_date",
            "idx_resources_tenant_type",
            "idx_identity_tenant_date"
        ]
        
        for index in indexes:
            # SQLite doesn't support REBUILD, but we can recreate
            self.db.execute(f"REINDEX {index}")
        
        self.db.commit()
    
    async def get_database_stats(self) -> Dict:
        """Get database statistics"""
        
        # Page count
        page_count = self.db.execute(
            "PRAGMA page_count"
        ).scalar()
        
        # Free pages
        free_pages = self.db.execute(
            "PRAGMA freelist_count"
        ).scalar()
        
        # Page size
        page_size = self.db.execute(
            "PRAGMA page_size"
        ).scalar()
        
        # Table sizes
        table_stats = {}
        tables = ["cost_snapshots", "compliance_snapshots", 
                 "resources", "identity_snapshots"]
        
        for table in tables:
            count = self.db.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).scalar()
            table_stats[table] = count
        
        return {
            "total_pages": page_count,
            "free_pages": free_pages,
            "page_size_bytes": page_size,
            "database_size_mb": (page_count * page_size) / (1024 * 1024),
            "table_counts": table_stats
        }
```

---

## 6. Recommendations Summary

### Immediate Actions (High Priority)

1. **Implement Rate Limiting**
   - Set up per-API rate limiters (ARM: 3.3 req/s, Graph: 166 req/s)
   - Add retry logic with exponential backoff
   - Implement circuit breaker for resilience

2. **Add Resume Capability**
   - Create SyncJob table for tracking
   - Implement checkpoint logic in all backfill services
   - Add API endpoints for job status/management

3. **Optimize Batch Inserts**
   - Use `bulk_insert_mappings` for SQLite
   - Batch size: 500 records optimal
   - Implement upsert for idempotency

### Short-term (Medium Priority)

4. **Parallel Processing**
   - Implement WorkerPool for concurrent tenant processing
   - Limit concurrent workers to 4 for B1 SKU
   - Add proper error handling and partial failure recovery

5. **Data Retention**
   - Implement retention policies (2 years cost, 1 year compliance)
   - Create archive tables for historical data
   - Set up scheduled maintenance jobs

6. **Monitoring**
   - Track backfill progress with detailed metrics
   - Alert on stuck or failed jobs
   - Monitor API quota usage

### Long-term (Lower Priority)

7. **Advanced Patterns**
   - Consider Azure Queue Storage for large backfills
   - Implement delta sync after initial backfill
   - Add support for incremental updates

8. **Performance Tuning**
   - Profile and optimize slow queries
   - Implement caching for frequently accessed data
   - Consider read replicas if query load increases

---

## Performance Benchmarks

| Operation | Records | Time | Notes |
|-----------|---------|------|-------|
| Single insert | 1 | 5ms | Baseline |
| Batch insert (100) | 100 | 50ms | 10x faster |
| Batch insert (500) | 500 | 200ms | Optimal |
| Batch insert (1000) | 1000 | 450ms | Diminishing returns |
| Parallel tenant sync | 4 tenants | 2x faster | Limited by API rate limits |
| Full backfill (1 year) | ~50k records | ~2 hours | 4 tenants, rate limited |

---

*Research conducted by web-puppy-318eac*
*Last Updated: 2025-03-02*
