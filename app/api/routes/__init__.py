"""API routes module."""

from app.api.routes.accessibility import router as accessibility_router
from app.api.routes.audit_logs import router as audit_logs_router
from app.api.routes.auth import router as auth_router
from app.api.routes.budgets import router as budgets_router
from app.api.routes.bulk import router as bulk_router
from app.api.routes.compliance import router as compliance_router
from app.api.routes.compliance_frameworks import router as compliance_frameworks_router
from app.api.routes.compliance_rules import router as compliance_rules_router
from app.api.routes.costs import router as costs_router
from app.api.routes.dashboard import public_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.device_security import router as device_security_router
from app.api.routes.dmarc import router as dmarc_router
from app.api.routes.exports import router as exports_router
from app.api.routes.identity import router as identity_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.monitoring import router as monitoring_router
from app.api.routes.onboarding import router as onboarding_router
from app.api.routes.pages import router as pages_router
from app.api.routes.preflight import router as preflight_router
from app.api.routes.privacy import router as privacy_router
from app.api.routes.provisioning_standards import router as provisioning_standards_router
from app.api.routes.quotas import router as quotas_router
from app.api.routes.recommendations import router as recommendations_router
from app.api.routes.resources import router as resources_router
from app.api.routes.riverside import router as riverside_router
from app.api.routes.search import router as search_router
from app.api.routes.sui_generis import router as sui_generis_router
from app.api.routes.sync import router as sync_router
from app.api.routes.tenants import router as tenants_router
from app.api.routes.threats import router as threats_router

__all__ = [
    "accessibility_router",
    "audit_logs_router",
    "quotas_router",
    "auth_router",
    "budgets_router",
    "bulk_router",
    "compliance_router",
    "compliance_frameworks_router",
    "compliance_rules_router",
    "costs_router",
    "dashboard_router",
    "device_security_router",
    "dmarc_router",
    "exports_router",
    "identity_router",
    "metrics_router",
    "monitoring_router",
    "onboarding_router",
    "pages_router",
    "preflight_router",
    "privacy_router",
    "provisioning_standards_router",
    "public_router",
    "recommendations_router",
    "resources_router",
    "riverside_router",
    "search_router",
    "sui_generis_router",
    "sync_router",
    "tenants_router",
    "threats_router",
]
