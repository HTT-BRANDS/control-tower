"""API services module."""

from app.api.services.azure_ad_admin_service import (
    AdminRoleError,
    AdminRoleMetrics,
    AzureADAdminService,
    azure_ad_admin_service,
)
from app.api.services.azure_client import AzureClientManager
from app.api.services.bulk_service import BulkService
from app.api.services.compliance_service import ComplianceService
from app.api.services.cost_service import CostService
from app.api.services.graph_client import (
    ADMIN_ROLE_TEMPLATE_IDS,
    AdminRoleSummary,
    DirectoryRole,
    GraphClient,
    MFAError,
    MFAMethodDetails,
    PrivilegedAccessAssignment,
    RoleAssignment,
    TenantMFASummary,
    UserMFAStatus,
)
from app.api.services.identity_service import IdentityService
from app.api.services.monitoring_service import MonitoringService
from app.api.services.recommendation_service import RecommendationService
from app.api.services.resource_service import ResourceService
from app.api.services.riverside_analytics import (
    get_deadline_status,
    get_riverside_metrics,
    track_requirement_progress,
)
from app.api.services.riverside_compliance import (
    analyze_mfa_gaps,
    calculate_compliance_summary,
)
from app.api.services.riverside_service import RiversideService

__all__ = [
    # Admin Role Service
    "AdminRoleError",
    "AdminRoleMetrics",
    "AzureADAdminService",
    "azure_ad_admin_service",
    # Graph Client Classes
    "ADMIN_ROLE_TEMPLATE_IDS",
    "AdminRoleSummary",
    "DirectoryRole",
    "GraphClient",
    "MFAError",
    "MFAMethodDetails",
    "PrivilegedAccessAssignment",
    "RoleAssignment",
    "TenantMFASummary",
    "UserMFAStatus",
    # Core Services
    "AzureClientManager",
    "BulkService",
    "ComplianceService",
    "CostService",
    "IdentityService",
    "MonitoringService",
    "RecommendationService",
    "ResourceService",
    "RiversideService",
    # Riverside Analytics
    "calculate_compliance_summary",
    "analyze_mfa_gaps",
    "track_requirement_progress",
    "get_deadline_status",
    "get_riverside_metrics",
]
