"""Azure Multi-Tenant Governance Platform - Main Application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import (
    auth_router,
    bulk_router,
    compliance_router,
    costs_router,
    dashboard_router,
    dmarc_router,
    exports_router,
    identity_router,
    onboarding_router,
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

# Configure CORS with security restrictions in production
# SECURITY: No wildcards allowed in production - explicit origins only
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
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
            "recent_count": len(monitoring.get_recent_alerts(hours=24)),
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
