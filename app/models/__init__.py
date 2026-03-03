"""Database models module."""

# Brand configuration for multi-tenant theming
from app.models.backfill_job import BackfillJob, BackfillStatus
from app.models.brand_config import BrandConfig
from app.models.compliance import ComplianceSnapshot, PolicyState
from app.models.cost import CostAnomaly, CostSnapshot
from app.models.dmarc import (
    DKIMRecord,
    DMARCAlert,
    DMARCRecord,
    DMARCReport,
)
from app.models.identity import IdentitySnapshot, PrivilegedUser
from app.models.monitoring import Alert, SyncJobLog, SyncJobMetrics
from app.models.notifications import NotificationLog
from app.models.recommendation import Recommendation
from app.models.resource import IdleResource, Resource, ResourceTag
from app.models.riverside import (
    RequirementCategory,
    RequirementPriority,
    RequirementStatus,
    RiversideCompliance,
    RiversideDeviceCompliance,
    RiversideMFA,
    RiversideRequirement,
    RiversideThreatData,
)
from app.models.sync import SyncJob
from app.models.tenant import Subscription, Tenant, UserTenant

__all__ = [
    # Brand config
    "BrandConfig",
    # Tenants
    "Tenant",
    "Subscription",
    "UserTenant",
    "CostSnapshot",
    "CostAnomaly",
    "ComplianceSnapshot",
    "PolicyState",
    "Resource",
    "ResourceTag",
    "IdleResource",
    "IdentitySnapshot",
    "PrivilegedUser",
    "SyncJob",
    # Backfill models
    "BackfillJob",
    "BackfillStatus",
    # Monitoring models
    "SyncJobLog",
    "SyncJobMetrics",
    "Alert",
    "NotificationLog",
    # Recommendation models
    "Recommendation",
    # Riverside models
    "RequirementCategory",
    "RequirementPriority",
    "RequirementStatus",
    "RiversideCompliance",
    "RiversideDeviceCompliance",
    "RiversideMFA",
    "RiversideRequirement",
    "RiversideThreatData",
    # DMARC/DKIM models
    "DMARCRecord",
    "DKIMRecord",
    "DMARCReport",
    "DMARCAlert",
]
