"""Sync-related Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SyncJob(BaseModel):
    """Sync job model representing a data synchronization operation."""

    job_id: str
    tenant_id: str
    sync_type: str
    status: str  # "pending", "running", "completed", "failed"
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class SyncStatus(BaseModel):
    """Current status of a sync job."""

    job_id: str
    status: str
    progress_percent: float = Field(..., ge=0, le=100)
    current_step: str
    estimated_completion: Optional[datetime] = None


class SyncResult(BaseModel):
    """Results of a completed sync operation."""

    job_id: str
    tenant_id: str
    sync_type: str
    status: str
    records_processed: int
    records_created: int
    records_updated: int
    errors: int
    completed_at: datetime
