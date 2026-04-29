"""Azure Multi-Tenant Governance Platform - Main Application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.auth import jwt_manager
from app.core.cache import cache_manager
from app.core.config import get_settings
from app.core.database import init_db
from app.core.scheduler import init_scheduler
from app.core.token_blacklist import get_blacklist_backend, get_blacklist_size
from app.main_docs import (
    create_custom_openapi,
    register_docs_routes,
)
from app.main_docs import (
    load_openapi_examples as _load_openapi_examples,
)
from app.main_errors import register_exception_handlers
from app.main_factory import create_application
from app.main_health import register_health_and_status_routes
from app.main_middleware import configure_middleware
from app.main_routers import register_static_and_routers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    current_settings = get_settings()
    scheduler = None
    riverside_sched = None

    logger.info("Starting Azure Governance Platform...")
    init_db()
    logger.info("Database initialized")

    await cache_manager.initialize()
    logger.info("Cache initialized")

    if current_settings.disable_background_schedulers:
        app.state.scheduler_status = "disabled_for_test"
        logger.info(
            "Background schedulers intentionally disabled for browser-test harness "
            "(ENVIRONMENT=test, E2E_HARNESS=1)"
        )
    else:
        scheduler = init_scheduler()
        scheduler.start()
        app.state.scheduler_status = "running"
        logger.info("Background scheduler started")

        try:
            from app.core.riverside_scheduler import init_riverside_scheduler

            riverside_sched = init_riverside_scheduler()
            riverside_sched.start()
            logger.info("Riverside compliance scheduler started")
        except Exception:
            logger.exception(
                "Failed to start Riverside compliance scheduler — continuing without it"
            )

    yield

    logger.info("Shutting down...")
    if riverside_sched is not None:
        riverside_sched.shutdown()
    if scheduler is not None:
        scheduler.shutdown()


app = create_application(settings, lifespan)
tracer = configure_middleware(app, settings, logger)
register_static_and_routers(app)
register_docs_routes(app, settings, jwt_manager)
register_health_and_status_routes(
    app,
    settings,
    cache_manager,
    get_blacklist_backend,
    get_blacklist_size,
)
register_exception_handlers(app, settings, logger)


def load_openapi_examples() -> dict:
    """Load OpenAPI examples from docs/openapi-examples directory."""
    return _load_openapi_examples(logger)


app.state.openapi_examples = load_openapi_examples()
custom_openapi = create_custom_openapi(app, logger)
app.openapi = custom_openapi


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
