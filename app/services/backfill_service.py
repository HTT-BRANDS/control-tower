"""Resumable backfill service with day-by-day processing.

Features:
- Day-by-day processing with checkpointing
- Batch insert (500 records optimal for SQLite)
- Support for costs, identity, compliance, resources
- Pause/resume/cancel functionality
- Progress tracking
"""

import asyncio
import concurrent.futures
import json
import logging
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import TypeVar

from azure.core.exceptions import HttpResponseError
from sqlalchemy.orm import Session

from app.api.services.azure_client import azure_client_manager
from app.core.database import bulk_insert_chunks
from app.models.backfill_job import BackfillJob, BackfillStatus
from app.models.compliance import ComplianceSnapshot
from app.models.cost import CostSnapshot
from app.models.identity import IdentitySnapshot
from app.models.resource import Resource

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _run_async(coro):
    """Run an async coroutine synchronously for backfill compatibility."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=300)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _log_http_error(context: str, sub_id: str, error: HttpResponseError) -> None:
    """Log Azure HTTP errors with appropriate context."""
    if error.status_code == 403:
        logger.warning(f"{context}: access denied for subscription {sub_id}")
    else:
        logger.warning(
            f"{context}: HTTP {error.status_code} for subscription {sub_id}: {error.message}"
        )


class BatchInserter:
    """Optimized batch insert for SQLite (500 records)."""

    def __init__(self, db: Session, model_class: type[T], batch_size: int = 500) -> None:
        """Initialize batch inserter.

        Args:
            db: Database session
            model_class: SQLAlchemy model class to insert
            batch_size: Number of records per batch (default 500 for SQLite)
        """
        self.db = db
        self.model_class = model_class
        self.batch_size = batch_size
        self._buffer: list[dict] = []
        self._total_inserted = 0

    def add(self, record: dict) -> None:
        """Add a record to the batch buffer.

        Args:
            record: Dictionary of column values
        """
        self._buffer.append(record)
        if len(self._buffer) >= self.batch_size:
            self.flush()

    def add_many(self, records: list[dict]) -> None:
        """Add multiple records to the batch buffer.

        Args:
            records: List of record dictionaries
        """
        for record in records:
            self.add(record)

    def flush(self) -> int:
        """Insert current batch and clear buffer.

        Returns:
            Number of records inserted
        """
        if not self._buffer:
            return 0

        try:
            count = bulk_insert_chunks(
                self.db,
                self.model_class,
                self._buffer,
                batch_size=self.batch_size,
            )
            self._total_inserted += count
            inserted = len(self._buffer)
            self._buffer.clear()
            return inserted
        except Exception as e:
            logger.error(f"Batch insert failed: {e}")
            raise

    def commit(self) -> int:
        """Final commit - flush remaining records.

        Returns:
            Total number of records inserted
        """
        self.flush()
        return self._total_inserted

    @property
    def buffer_size(self) -> int:
        """Current number of records in buffer."""
        return len(self._buffer)

    @property
    def total_inserted(self) -> int:
        """Total number of records inserted so far."""
        return self._total_inserted


class BackfillProcessor(ABC):
    """Abstract base class for data type processors."""

    def __init__(self, db: Session, tenant_id: str) -> None:
        """Initialize processor.

        Args:
            db: Database session
            tenant_id: Tenant ID to process
        """
        self.db = db
        self.tenant_id = tenant_id

    @abstractmethod
    def fetch_data(self, date: datetime) -> list[dict]:
        """Fetch data for a specific date.

        Args:
            date: Date to fetch data for

        Returns:
            List of record dictionaries
        """
        pass

    @abstractmethod
    def get_model_class(self) -> type:
        """Get the SQLAlchemy model class for this processor."""
        pass

    def process_day(
        self,
        date: datetime,
        batch_inserter: BatchInserter,
    ) -> tuple[int, int]:
        """Process a single day of data.

        Args:
            date: Date to process
            batch_inserter: Batch inserter for records

        Returns:
            Tuple of (records fetched, records inserted)
        """
        try:
            records = self.fetch_data(date)
            fetched = len(records)

            if records:
                batch_inserter.add_many(records)

            return fetched, fetched
        except Exception as e:
            logger.error(f"Failed to process {date.date()}: {e}")
            raise


class CostDataProcessor(BackfillProcessor):
    """Processor for cost data backfill."""

    def get_model_class(self) -> type:
        """Return CostSnapshot model class."""
        return CostSnapshot

    def fetch_data(self, date: datetime) -> list[dict]:
        """Fetch cost data for a specific date via Azure Cost Management API.

        Queries subscriptions and retrieves actual cost data using the
        Azure Cost Management query API, grouped by resource group and
        service name. Skips zero-cost entries to save storage.
        """
        from azure.mgmt.costmanagement.models import (
            QueryAggregation,
            QueryDataset,
            QueryDefinition,
            QueryGrouping,
            QueryTimePeriod,
        )

        try:
            subs = _run_async(azure_client_manager.list_subscriptions(self.tenant_id))
        except Exception as e:
            logger.warning(f"Cost backfill: failed listing subs for {self.tenant_id}: {e}")
            return []

        from_date = date.strftime("%Y-%m-%d")
        to_date = (date + timedelta(days=1)).strftime("%Y-%m-%d")
        records = []

        for sub in subs:
            sub_id = sub["subscription_id"]
            if sub.get("state") != "Enabled":
                continue
            try:
                cost_client = azure_client_manager.get_cost_client(
                    self.tenant_id,
                    sub_id,
                )
                query = QueryDefinition(
                    type="ActualCost",
                    timeframe="Custom",
                    time_period=QueryTimePeriod(
                        from_property=from_date,
                        to=to_date,
                    ),
                    dataset=QueryDataset(
                        granularity="Daily",
                        aggregation={
                            "totalCost": QueryAggregation(
                                name="Cost",
                                function="Sum",
                            ),
                        },
                        grouping=[
                            QueryGrouping(
                                type="Dimension",
                                name="ResourceGroupName",
                            ),
                            QueryGrouping(
                                type="Dimension",
                                name="ServiceName",
                            ),
                        ],
                    ),
                )
                result = cost_client.query.usage(
                    scope=f"/subscriptions/{sub_id}",
                    parameters=query,
                )
                if not (result.properties and result.properties.rows):
                    continue
                for row in result.properties.rows:
                    if len(row) < 3:
                        continue
                    cost_value = float(row[0]) if row[0] else 0.0
                    if cost_value == 0.0:
                        continue
                    records.append(
                        {
                            "tenant_id": self.tenant_id,
                            "subscription_id": sub_id,
                            "date": date.date(),
                            "total_cost": cost_value,
                            "currency": str(row[2]) if row[2] else "USD",
                            "resource_group": (str(row[3]) if len(row) > 3 and row[3] else None),
                            "service_name": (str(row[4]) if len(row) > 4 and row[4] else None),
                            "meter_category": None,
                            "synced_at": datetime.utcnow(),
                        }
                    )
            except HttpResponseError as e:
                _log_http_error("Cost backfill", sub_id, e)
            except Exception as e:
                logger.warning(f"Cost backfill: error for sub {sub_id}: {e}")

        logger.info(f"Cost backfill: {len(records)} records for {date.date()}")
        return records


class IdentityDataProcessor(BackfillProcessor):
    """Processor for identity data backfill."""

    def get_model_class(self) -> type:
        """Return IdentitySnapshot model class."""
        return IdentitySnapshot

    def fetch_data(self, date: datetime) -> list[dict]:
        """Fetch identity snapshot data via Microsoft Graph API.

        Identity snapshots are monthly aggregates. Only generates records
        on first-of-month dates. Fetches user counts, guest users,
        privileged users, and MFA status from Graph API.
        """
        if date.day != 1:
            return []

        from app.api.services.graph_client import GraphClient

        try:
            graph_client = GraphClient(self.tenant_id)
            users = _run_async(graph_client.get_users())
            guest_users = _run_async(graph_client.get_guest_users())
            directory_roles = _run_async(graph_client.get_directory_roles())
            service_principals = _run_async(graph_client.get_service_principals())

            # MFA status (may fail with insufficient permissions)
            mfa_enabled_count = 0
            mfa_disabled_count = len(users)
            try:
                mfa_response = _run_async(graph_client.get_mfa_status())
                mfa_users = mfa_response.get("value", [])
                mfa_enabled_count = sum(1 for u in mfa_users if u.get("isMfaRegistered", False))
                mfa_disabled_count = len(mfa_users) - mfa_enabled_count
            except Exception as e:
                logger.warning(f"Identity backfill: could not fetch MFA status: {e}")

            # Calculate active/stale users
            now = datetime.utcnow()
            stale_30d = now - timedelta(days=30)
            stale_90d = now - timedelta(days=90)
            active_count = 0
            stale_30d_count = 0
            stale_90d_count = 0

            for user in users:
                sign_in = user.get("signInActivity", {})
                last_str = sign_in.get("lastSignInDateTime")
                if last_str:
                    try:
                        last_dt = datetime.fromisoformat(last_str.replace("Z", "+00:00")).replace(
                            tzinfo=None
                        )
                        if last_dt >= stale_30d:
                            active_count += 1
                        if last_dt < stale_90d:
                            stale_90d_count += 1
                            stale_30d_count += 1
                        elif last_dt < stale_30d:
                            stale_30d_count += 1
                    except (ValueError, AttributeError):
                        stale_30d_count += 1
                        stale_90d_count += 1
                else:
                    stale_30d_count += 1
                    stale_90d_count += 1

            # Count privileged users from directory roles
            privileged_count = 0
            for role in directory_roles:
                for member in role.get("members", []):
                    if "#microsoft.graph.user" in member.get("@odata.type", ""):
                        privileged_count += 1

            records = [
                {
                    "tenant_id": self.tenant_id,
                    "snapshot_date": date.date(),
                    "total_users": len(users),
                    "active_users": active_count,
                    "guest_users": len(guest_users),
                    "mfa_enabled_users": mfa_enabled_count,
                    "mfa_disabled_users": mfa_disabled_count,
                    "privileged_users": privileged_count,
                    "stale_accounts_30d": stale_30d_count,
                    "stale_accounts_90d": stale_90d_count,
                    "service_principals": len(service_principals),
                    "synced_at": datetime.utcnow(),
                }
            ]
            logger.info(f"Identity backfill: {len(users)} users for {date.date()}")
            return records

        except Exception as e:
            logger.warning(f"Identity backfill: failed for {self.tenant_id}: {e}")
            return []


class ComplianceDataProcessor(BackfillProcessor):
    """Processor for compliance data backfill."""

    def get_model_class(self) -> type:
        """Return ComplianceSnapshot model class."""
        return ComplianceSnapshot

    def fetch_data(self, date: datetime) -> list[dict]:
        """Fetch compliance data via Azure Policy Insights API.

        Queries subscriptions and retrieves compliance states, counting
        compliant, non-compliant, and exempt resources per subscription.
        """
        try:
            subs = _run_async(azure_client_manager.list_subscriptions(self.tenant_id))
        except Exception as e:
            logger.warning(f"Compliance backfill: failed listing subs for {self.tenant_id}: {e}")
            return []

        records = []
        for sub in subs:
            sub_id = sub["subscription_id"]
            if sub.get("state") != "Enabled":
                continue
            try:
                policy_client = azure_client_manager.get_policy_client(
                    self.tenant_id,
                    sub_id,
                )
                compliant = 0
                non_compliant = 0
                exempt = 0

                policy_states = policy_client.policy_states.list_query_results_for_subscription(
                    policy_states_resource="latest",
                    subscription_id=sub_id,
                )
                for state in policy_states:
                    cs = state.compliance_state.value if state.compliance_state else "Unknown"
                    if cs == "Compliant":
                        compliant += 1
                    elif cs == "NonCompliant":
                        non_compliant += 1
                    elif cs == "Exempt":
                        exempt += 1

                total = compliant + non_compliant + exempt
                pct = (compliant / total * 100) if total > 0 else 0.0

                records.append(
                    {
                        "tenant_id": self.tenant_id,
                        "subscription_id": sub_id,
                        "snapshot_date": date.date(),
                        "overall_compliance_percent": pct,
                        "secure_score": None,
                        "compliant_resources": compliant,
                        "non_compliant_resources": non_compliant,
                        "exempt_resources": exempt,
                        "synced_at": datetime.utcnow(),
                    }
                )
            except HttpResponseError as e:
                _log_http_error("Compliance backfill", sub_id, e)
            except Exception as e:
                logger.warning(f"Compliance backfill: error for sub {sub_id}: {e}")

        logger.info(f"Compliance backfill: {len(records)} records for {date.date()}")
        return records


class ResourcesDataProcessor(BackfillProcessor):
    """Processor for resources data backfill."""

    def get_model_class(self) -> type:
        """Return Resource model class."""
        return Resource

    def fetch_data(self, date: datetime) -> list[dict]:
        """Fetch resource inventory via Azure Resource Manager API.

        Queries subscriptions and retrieves the full resource inventory,
        parsing resource IDs for resource group, type, and name.
        Detects orphaned resources via provisioning state and tags.
        """
        try:
            subs = _run_async(azure_client_manager.list_subscriptions(self.tenant_id))
        except Exception as e:
            logger.warning(f"Resources backfill: failed listing subs for {self.tenant_id}: {e}")
            return []

        records = []
        for sub in subs:
            sub_id = sub["subscription_id"]
            if sub.get("state") != "Enabled":
                continue
            try:
                resource_client = azure_client_manager.get_resource_client(
                    self.tenant_id,
                    sub_id,
                )
                resources = resource_client.resources.list(
                    expand="provisioningState,createdTime,changedTime",
                )
                for resource in resources:
                    resource_id = resource.id or ""
                    resource_group = ""
                    resource_type = ""

                    # Parse resource group from resource ID
                    id_parts = resource_id.split("/")
                    for i, part in enumerate(id_parts):
                        if part.lower() == "resourcegroups" and i + 1 < len(id_parts):
                            resource_group = id_parts[i + 1]
                            break

                    # Parse resource type (provider/type)
                    if "/providers/" in resource_id:
                        prov = resource_id.split("/providers/")[-1]
                        prov_parts = prov.split("/")
                        if len(prov_parts) >= 2:
                            resource_type = f"{prov_parts[0]}/{prov_parts[1]}"

                    tags_json = json.dumps(resource.tags) if resource.tags else None

                    # Detect orphaned resources
                    is_orphaned = 0
                    prov_state = resource.provisioning_state or ""
                    if prov_state.lower() in ("failed", "canceled"):
                        is_orphaned = 1
                    elif resource.tags:
                        tag_str = json.dumps(resource.tags).lower()
                        if any(ind in tag_str for ind in ["orphaned", "orphan", "untracked"]):
                            is_orphaned = 1

                    sku_str = None
                    if resource.sku:
                        sku_str = (
                            resource.sku.name
                            if hasattr(resource.sku, "name")
                            else str(resource.sku)
                        )

                    records.append(
                        {
                            "id": resource_id,
                            "tenant_id": self.tenant_id,
                            "subscription_id": sub_id,
                            "resource_group": resource_group,
                            "resource_type": resource_type,
                            "name": resource.name or "",
                            "location": resource.location or "",
                            "provisioning_state": prov_state,
                            "sku": sku_str,
                            "kind": getattr(resource, "kind", None),
                            "tags_json": tags_json,
                            "is_orphaned": is_orphaned,
                            "estimated_monthly_cost": None,
                            "synced_at": datetime.utcnow(),
                        }
                    )
            except HttpResponseError as e:
                _log_http_error("Resources backfill", sub_id, e)
            except Exception as e:
                logger.warning(f"Resources backfill: error for sub {sub_id}: {e}")

        logger.info(f"Resources backfill: {len(records)} records for {date.date()}")
        return records


class BackfillService:
    """Service for managing backfill jobs."""

    PROCESSOR_MAP: dict[str, type[BackfillProcessor]] = {
        "costs": CostDataProcessor,
        "identity": IdentityDataProcessor,
        "compliance": ComplianceDataProcessor,
        "resources": ResourcesDataProcessor,
    }

    def __init__(self, db: Session) -> None:
        """Initialize service.

        Args:
            db: Database session
        """
        self.db = db

    def create_job(
        self,
        job_type: str,
        tenant_id: str | None,
        start_date: datetime,
        end_date: datetime,
    ) -> BackfillJob:
        """Create a new backfill job.

        Args:
            job_type: Type of data to backfill (costs, identity, compliance, resources)
            tenant_id: Optional tenant ID (None for all tenants)
            start_date: Start date for backfill
            end_date: End date for backfill

        Returns:
            Created BackfillJob
        """
        if job_type not in self.PROCESSOR_MAP:
            raise ValueError(f"Invalid job type: {job_type}")

        job = BackfillJob(
            id=str(uuid.uuid4()),
            job_type=job_type,
            tenant_id=tenant_id,
            status=BackfillStatus.PENDING.value,
            start_date=start_date,
            end_date=end_date,
            current_date=None,
            progress_percent=0.0,
            records_processed=0,
            records_inserted=0,
            records_failed=0,
            error_count=0,
        )

        self.db.add(job)
        self.db.commit()

        logger.info(f"Created backfill job {job.id} for {job_type}")
        return job

    def get_job(self, job_id: str) -> BackfillJob | None:
        """Get a backfill job by ID.

        Args:
            job_id: Job ID

        Returns:
            BackfillJob or None if not found
        """
        return self.db.query(BackfillJob).filter(BackfillJob.id == job_id).first()

    def list_jobs(
        self,
        tenant_id: str | None = None,
        job_type: str | None = None,
        status: str | None = None,
    ) -> list[BackfillJob]:
        """List backfill jobs with optional filtering.

        Args:
            tenant_id: Filter by tenant ID
            job_type: Filter by job type
            status: Filter by status

        Returns:
            List of BackfillJob objects
        """
        query = self.db.query(BackfillJob)

        if tenant_id:
            query = query.filter(BackfillJob.tenant_id == tenant_id)
        if job_type:
            query = query.filter(BackfillJob.job_type == job_type)
        if status:
            query = query.filter(BackfillJob.status == status)

        return query.order_by(BackfillJob.created_at.desc()).all()

    def cancel_job(self, job_id: str) -> BackfillJob:
        """Cancel a backfill job.

        Args:
            job_id: Job ID to cancel

        Returns:
            Updated BackfillJob

        Raises:
            ValueError: If job not found or cannot be cancelled
        """
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if not job.can_cancel:
            raise ValueError(f"Cannot cancel job in {job.status} state")

        job.update_status(BackfillStatus.CANCELLED)
        self.db.commit()

        logger.info(f"Cancelled backfill job {job_id}")
        return job


class ResumableBackfillService(BackfillService):
    """Enhanced backfill service with day-by-day processing."""

    def __init__(self, db: Session) -> None:
        """Initialize service.

        Args:
            db: Database session
        """
        super().__init__(db)
        self._cancelled = False

    def _date_range(self, start: datetime, end: datetime) -> Iterator[datetime]:
        """Generate dates from start to end inclusive.

        Args:
            start: Start date
            end: End date

        Yields:
            Dates from start to end
        """
        current = start
        while current <= end:
            yield current
            current += timedelta(days=1)

    def _calculate_progress(self, job: BackfillJob, current_date: datetime) -> float:
        """Calculate progress percentage.

        Args:
            job: Backfill job
            current_date: Current processing date

        Returns:
            Progress percentage (0.0-100.0)
        """
        total_days = (job.end_date - job.start_date).days + 1
        if total_days <= 0:
            return 100.0

        days_processed = (current_date - job.start_date).days + 1
        progress = (days_processed / total_days) * 100.0
        return min(progress, 100.0)

    def _get_processor(self, job_type: str, tenant_id: str) -> BackfillProcessor:
        """Get processor instance for job type.

        Args:
            job_type: Type of data
            tenant_id: Tenant ID

        Returns:
            BackfillProcessor instance
        """
        processor_class = self.PROCESSOR_MAP.get(job_type)
        if not processor_class:
            raise ValueError(f"No processor for job type: {job_type}")

        return processor_class(self.db, tenant_id)

    def process_day(
        self,
        tenant_id: str,
        date: datetime,
        job_type: str,
        batch_size: int = 500,
    ) -> tuple[int, int]:
        """Process a single day of data.

        Args:
            tenant_id: Tenant ID
            date: Date to process
            job_type: Type of data
            batch_size: Batch insert size

        Returns:
            Tuple of (records fetched, records inserted)
        """
        processor = self._get_processor(job_type, tenant_id)
        inserter = BatchInserter(self.db, processor.get_model_class(), batch_size)

        try:
            fetched, inserted = processor.process_day(date, inserter)
            inserter.commit()
            return fetched, inserted
        except Exception:
            # Don't commit on error - let caller handle
            raise

    def process_date_range(
        self,
        tenant_id: str,
        start_date: datetime,
        end_date: datetime,
        job_type: str,
        batch_size: int = 500,
    ) -> dict[str, int]:
        """Process a date range.

        Args:
            tenant_id: Tenant ID
            start_date: Start date
            end_date: End date
            job_type: Type of data
            batch_size: Batch insert size

        Returns:
            Dict with total_records, inserted_records, failed_records
        """
        processor = self._get_processor(job_type, tenant_id)
        inserter = BatchInserter(self.db, processor.get_model_class(), batch_size)

        total_fetched = 0
        total_inserted = 0
        total_failed = 0

        for date in self._date_range(start_date, end_date):
            try:
                fetched, inserted = processor.process_day(date, inserter)
                total_fetched += fetched
                total_inserted += inserted
            except Exception as e:
                logger.error(f"Failed to process {date.date()}: {e}")
                total_failed += 1

        # Final commit
        inserter.commit()

        return {
            "total_records": total_fetched,
            "inserted_records": total_inserted,
            "failed_records": total_failed,
        }

    def run_job(
        self,
        job_id: str,
        batch_size: int = 500,
        day_by_day: bool = True,
    ) -> BackfillJob:
        """Execute backfill job with day-by-day checkpointing.

        Args:
            job_id: Job ID to run
            batch_size: Number of records per batch
            day_by_day: Whether to checkpoint after each day

        Returns:
            Completed BackfillJob

        Raises:
            ValueError: If job not found or cannot be run
        """
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if job.is_running:
            raise ValueError(f"Job {job_id} is already running")

        if job.is_terminal:
            raise ValueError(f"Job {job_id} is in terminal state: {job.status}")

        # Mark as running
        job.update_status(BackfillStatus.RUNNING)
        self.db.commit()

        # Determine start date (resume from checkpoint if paused)
        start_date = job.current_date or job.start_date
        if job.current_date and job.current_date > job.start_date:
            # Resume from next day
            start_date = job.current_date + timedelta(days=1)
        else:
            start_date = job.start_date

        processor = self._get_processor(job.job_type, job.tenant_id or "")
        inserter = BatchInserter(self.db, processor.get_model_class(), batch_size)

        try:
            for date in self._date_range(start_date, job.end_date):
                # Check if cancelled
                if self._cancelled:
                    logger.info(f"Job {job_id} was cancelled")
                    job.update_status(BackfillStatus.CANCELLED)
                    self.db.commit()
                    return job

                # Refresh job status from DB
                self.db.refresh(job)
                if job.is_cancelled:
                    logger.info(f"Job {job_id} was cancelled externally")
                    return job

                try:
                    fetched, inserted = processor.process_day(date, inserter)
                    job.records_processed += fetched
                    job.records_inserted += inserted
                    job.current_date = date
                    job.progress_percent = self._calculate_progress(job, date)

                    if day_by_day:
                        # Flush batch and commit checkpoint
                        inserter.flush()
                        self.db.commit()

                except Exception as e:
                    logger.error(f"Error processing {date.date()}: {e}")
                    job.error_count += 1
                    job.last_error = str(e)
                    job.records_failed += 1

                    # Commit checkpoint even on error
                    if day_by_day:
                        self.db.commit()

                    # Continue to next day or fail based on error count
                    if job.error_count > 10:
                        job.update_status(BackfillStatus.FAILED)
                        self.db.commit()
                        raise

            # Final commit
            inserter.commit()

            # Mark completed
            job.update_status(BackfillStatus.COMPLETED)
            job.progress_percent = 100.0
            self.db.commit()

            logger.info(
                f"Completed backfill job {job_id}: "
                f"{job.records_processed} processed, "
                f"{job.records_inserted} inserted"
            )

        except Exception as e:
            logger.error(f"Backfill job {job_id} failed: {e}")
            job.update_status(BackfillStatus.FAILED)
            job.last_error = str(e)
            self.db.commit()
            raise

        return job

    def pause_job(self, job_id: str) -> BackfillJob:
        """Pause job and save date checkpoint.

        Args:
            job_id: Job ID to pause

        Returns:
            Updated BackfillJob

        Raises:
            ValueError: If job not found or cannot be paused
        """
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if not job.is_running:
            raise ValueError(f"Cannot pause job in {job.status} state")

        job.update_status(BackfillStatus.PAUSED)
        self.db.commit()

        logger.info(f"Paused backfill job {job_id} at {job.current_date}")
        return job

    def resume_job(
        self,
        job_id: str,
        batch_size: int = 500,
    ) -> BackfillJob:
        """Resume a paused or failed backfill job.

        Args:
            job_id: Job ID to resume
            batch_size: Batch insert size

        Returns:
            Completed BackfillJob
        """
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if not job.can_resume:
            raise ValueError(f"Cannot resume job in {job.status} state")

        return self.run_job(job_id, batch_size=batch_size)

    def calculate_progress(self, job: BackfillJob) -> float:
        """Calculate current progress percentage.

        Args:
            job: Backfill job

        Returns:
            Progress percentage (0.0-100.0)
        """
        if job.is_completed:
            return 100.0

        if not job.current_date:
            return 0.0

        return self._calculate_progress(job, job.current_date)
