"""Router and static asset registration for the FastAPI app."""

from fastapi.staticfiles import StaticFiles

from app.api.routes import (
    accessibility_router,
    admin_router,
    audit_logs_router,
    auth_router,
    budgets_router,
    bulk_router,
    compliance_frameworks_router,
    compliance_router,
    compliance_rules_router,
    costs_router,
    dashboard_router,
    design_system_router,
    dmarc_router,
    exports_router,
    health_router,
    identity_router,
    metrics_router,
    monitoring_router,
    onboarding_router,
    pages_router,
    preflight_router,
    privacy_router,
    provisioning_standards_router,
    public_router,
    quotas_router,
    recommendations_router,
    resources_router,
    riverside_router,
    search_router,
    sync_router,
    tenants_router,
    threats_router,
    topology_router,
)

AUTH_AND_PUBLIC_ROUTERS = (
    audit_logs_router,
    quotas_router,
    auth_router,
    health_router,
    onboarding_router,
)

PROTECTED_ROUTERS = (
    public_router,
    dashboard_router,
    design_system_router,
    costs_router,
    budgets_router,
    compliance_router,
    compliance_frameworks_router,
    compliance_rules_router,
    resources_router,
    identity_router,
    tenants_router,
    sync_router,
    riverside_router,
    threats_router,
    bulk_router,
    dmarc_router,
    accessibility_router,
    exports_router,
    pages_router,
    topology_router,
    preflight_router,
    privacy_router,
    search_router,
    provisioning_standards_router,
    metrics_router,
    monitoring_router,
    recommendations_router,
    admin_router,
)


def register_static_and_routers(app) -> None:
    """Mount static assets and include all API routers in stable order."""
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    for router in AUTH_AND_PUBLIC_ROUTERS:
        app.include_router(router)

    for router in PROTECTED_ROUTERS:
        app.include_router(router)
