"""API routes module."""

from app.api.routes.auth import router as auth_router
from app.api.routes.bulk import router as bulk_router
from app.api.routes.compliance import router as compliance_router
from app.api.routes.costs import router as costs_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.dmarc import router as dmarc_router
from app.api.routes.exports import router as exports_router
from app.api.routes.identity import router as identity_router
from app.api.routes.resources import router as resources_router
from app.api.routes.riverside import router as riverside_router
from app.api.routes.tenants import router as tenants_router
from app.api.routes.sync import router as sync_router

__all__ = [
    "auth_router",
    "bulk_router",
    "compliance_router",
    "costs_router",
    "dashboard_router",
    "dmarc_router",
    "exports_router",
    "identity_router",
    "resources_router",
    "riverside_router",
    "tenants_router",
    "sync_router",
]
