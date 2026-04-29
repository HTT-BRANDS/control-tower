"""Azure sync services for Riverside compliance data.

This package preserves the historical ``app.services.riverside_sync`` public
import path while keeping table-specific sync implementations in focused modules.
"""

from app.services.riverside_sync.common import (
    RIVERSIDE_DEADLINE,
    TARGET_MATURITY_SCORE,
    ProgressTracker,
    SyncError,
    _get_graph_client,
    _get_monitoring_service,
)
from app.services.riverside_sync.devices import sync_tenant_devices
from app.services.riverside_sync.maturity import sync_maturity_scores
from app.services.riverside_sync.mfa import sync_tenant_mfa
from app.services.riverside_sync.orchestration import run_full_tenant_sync, sync_all_tenants
from app.services.riverside_sync.requirements import sync_requirement_status

__all__ = [
    "RIVERSIDE_DEADLINE",
    "TARGET_MATURITY_SCORE",
    "ProgressTracker",
    "SyncError",
    "_get_graph_client",
    "_get_monitoring_service",
    "run_full_tenant_sync",
    "sync_all_tenants",
    "sync_maturity_scores",
    "sync_requirement_status",
    "sync_tenant_devices",
    "sync_tenant_mfa",
]
