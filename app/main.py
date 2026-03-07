"""Azure Multi-Tenant Governance Platform - Main Application."""

import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routes import (
    auth_router,
    bulk_router,
    compliance_router,
    costs_router,
    dashboard_router,
    dmarc_router,
    exports_router,
    identity_router,
    monitoring_router,
    onboarding_router,
    preflight_router,
    recommendations_router,
    resources_router,
    riverside_router,
    sync_router,
    tenants_router,
)
from app.core.cache import cache_manager
from app.core.config import get_settings
from app.core.database import init_db
from app.core.rate_limit import rate_limiter
from app.core.scheduler import init_scheduler
from app.core.tenant_context import register_template_filters

# Initialize Jinja2 templates and register custom filters
templates = Jinja2Templates(directory="app/templates")
register_template_filters(templates.env)

# Expose app version to all templates as a global
from app import __version__ as _app_version  # noqa: E402

templates.env.globals["app_version"] = _app_version

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Azure Governance Platform...")

    # Initialize database
    init_db()
    logger.info("Database initialized")

    # Initialize cache
    await cache_manager.initialize()
    logger.info("Cache initialized")

    # Initialize and start scheduler
    scheduler = init_scheduler()
    scheduler.start()
    logger.info("Background scheduler started")

    yield

    # Shutdown
    logger.info("Shutting down...")
    scheduler.shutdown()


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Multi-tenant Azure governance platform for cost optimization, "
                "compliance monitoring, resource management, and identity governance.",
    lifespan=lifespan,
)

# Configure CORS — single middleware, no wildcards, no duplicates
# SECURITY: Explicit origins, methods, and headers only (P1 fix)
_cors_origins = list(settings.cors_origins)
if settings.cors_allowed_origins:
    _cors_origins.extend(
        o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting to all requests.

    SECURITY: Provides DDoS protection and abuse prevention.
    """
    # Skip rate limiting for health checks
    if request.url.path in ["/health", "/health/detailed"]:
        response = await call_next(request)
        return response

    # Determine rate limit based on endpoint
    limit_config = rate_limiter.get_limit_config(request.url.path)

    try:
        allowed, headers = await rate_limiter.is_allowed(request, limit_config)

        response = await call_next(request)

        # Apply rate limit headers
        for key, value in headers.items():
            response.headers[key] = str(value)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded. Please try again later."},
                headers={
                    **headers,
                    "Retry-After": str(limit_config.window_seconds),
                },
            )

        return response

    except Exception as e:
        # Log error but don't block request if rate limiting fails
        logger.error(f"Rate limiting error: {e}")
        return await call_next(request)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add security response headers to all responses.

    SECURITY: Protects against clickjacking, XSS, MIME sniffing,
    and enforces HTTPS via HSTS.

    CSP nonce is generated per-request and stored on request.state so
    Jinja2 templates can render it via request.state.csp_nonce.
    """
    # Generate a cryptographic nonce for CSP -- available to templates
    # via request.state before the response is rendered.
    nonce = secrets.token_urlsafe(32)
    request.state.csp_nonce = nonce

    response = await call_next(request)
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    # Prevent XSS via MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    # XSS Protection (legacy browsers)
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # Referrer policy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Permissions policy (restrict browser features)
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # Content Security Policy -- nonce replaces 'unsafe-inline' for script-src.
    # 'unsafe-inline' is kept ONLY for style-src (brand CSS variables).
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}' https://unpkg.com https://cdn.jsdelivr.net https://cdn.tailwindcss.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    # HSTS (only in production to avoid dev issues)
    if not settings.is_development:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Prometheus metrics
Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    excluded_handlers=["/health", "/health/detailed"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=True)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers - Auth router first (no auth required for login)
app.include_router(auth_router)

# Onboarding router (public for self-service)
app.include_router(onboarding_router)

# Protected routers (will be secured via dependencies in route files)
app.include_router(dashboard_router)
app.include_router(costs_router)
app.include_router(compliance_router)
app.include_router(resources_router)
app.include_router(identity_router)
app.include_router(tenants_router)
app.include_router(sync_router)
app.include_router(riverside_router)
app.include_router(bulk_router)
app.include_router(dmarc_router)
app.include_router(exports_router)
app.include_router(preflight_router)
app.include_router(monitoring_router)
app.include_router(recommendations_router)


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}


@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with component status."""
    from app.core.database import SessionLocal

    components = {
        "database": "unknown",
        "scheduler": "unknown",
        "cache": "unknown",
        "azure_configured": settings.is_configured,
    }

    # Check database
    try:
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        components["database"] = "healthy"
    except Exception as e:
        components["database"] = f"unhealthy: {str(e)}"

    # Check scheduler
    from app.core.scheduler import get_scheduler
    scheduler = get_scheduler()
    if scheduler and scheduler.running:
        components["scheduler"] = "running"
    else:
        components["scheduler"] = "not_running"

    # Check cache
    cache_metrics = cache_manager.get_metrics()
    components["cache"] = cache_metrics.get("backend", "unknown")

    return {
        "status": "healthy" if all(
            v in ["healthy", "running", True] or v not in ["unhealthy", "not_running"]
            for v in components.values()
        ) else "degraded",
        "version": settings.app_version,
        "components": components,
        "cache_metrics": cache_metrics,
    }


@app.get("/api/v1/status")
async def get_system_status():
    """Get detailed system status and health metrics.

    Returns comprehensive status including:
    - Database health
    - Scheduler status
    - Cache metrics
    - Sync job summaries
    - Active alerts count
    """
    from datetime import UTC, datetime

    from app.api.services.monitoring_service import MonitoringService
    from app.core.database import SessionLocal, get_db_stats
    from app.core.monitoring import get_performance_dashboard

    status = {
        "status": "healthy",
        "version": settings.app_version,
        "timestamp": datetime.now(UTC).isoformat(),
        "components": {},
        "sync_jobs": {},
        "alerts": {},
        "performance": {},
        "cache": {},
    }

    # Check database
    try:
        from sqlalchemy import text
        db = SessionLocal()
        db_stats = get_db_stats(db)
        db.execute(text("SELECT 1"))
        db.close()
        status["components"]["database"] = "healthy"
        status["database_stats"] = db_stats
    except Exception as e:
        status["components"]["database"] = f"unhealthy: {str(e)}"
        status["status"] = "degraded"

    # Check scheduler
    try:
        from app.core.scheduler import get_scheduler
        scheduler = get_scheduler()
        if scheduler and scheduler.running:
            status["components"]["scheduler"] = "running"
            status["sync_jobs"]["active_jobs"] = len(scheduler.get_jobs())
        else:
            status["components"]["scheduler"] = "not_running"
    except Exception as e:
        status["components"]["scheduler"] = f"error: {str(e)}"

    # Check cache
    try:
        cache_metrics = cache_manager.get_metrics()
        status["cache"] = cache_metrics
        status["components"]["cache"] = cache_metrics.get("backend", "unknown")
    except Exception as e:
        status["components"]["cache"] = f"error: {str(e)}"

    # Get performance metrics
    try:
        status["performance"] = get_performance_dashboard()
    except Exception as e:
        status["performance"] = {"error": str(e)}

    # Get alerts summary
    try:
        db = SessionLocal()
        monitoring = MonitoringService(db)
        status["alerts"] = {
            "active_count": len(monitoring.get_active_alerts()),
            "recent_count": len(monitoring.get_active_alerts()),
        }
        db.close()
    except Exception as e:
        status["alerts"] = {"error": str(e)}

    return status


@app.get("/")
async def root():
    """Root endpoint - redirect to dashboard."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An unexpected error occurred",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
