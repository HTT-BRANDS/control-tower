"""API routes module."""

from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.costs import router as costs_router
from app.api.routes.compliance import router as compliance_router
from app.api.routes.resources import router as resources_router
from app.api.routes.identity import router as identity_router
from app.api.routes.tenants import router as tenants_router
from app.api.routes.sync import router as sync_router
from app.api.routes.riverside import router as riverside_router

__all__ = [
    "dashboard_router",
    "costs_router",
    "compliance_router",
    "resources_router",
    "identity_router",
    "tenants_router",
    "sync_router",
    "riverside_router",
]
