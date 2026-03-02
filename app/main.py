"""Azure Multi-Tenant Governance Platform - Main Application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.core.database import init_db
from app.core.scheduler import init_scheduler
from app.api.routes import (
    costs_router,
    compliance_router,
    dashboard_router,
    identity_router,
    resources_router,
    riverside_router,
    sync_router,
    tenants_router,
)

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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers
app.include_router(dashboard_router)
app.include_router(costs_router)
app.include_router(compliance_router)
app.include_router(resources_router)
app.include_router(identity_router)
app.include_router(tenants_router)
app.include_router(sync_router)
app.include_router(riverside_router)


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
        "azure_configured": settings.is_configured,
    }

    # Check database
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
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

    return {
        "status": "healthy" if all(
            v in ["healthy", "running", True] for v in components.values()
        ) else "degraded",
        "version": settings.app_version,
        "components": components,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again later."},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
