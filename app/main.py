"""Azure Multi-Tenant Governance Platform - Main Application."""

import logging
import textwrap
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.orm import Session

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
from app.core.auth import jwt_manager
from app.core.cache import cache_manager
from app.core.config import get_settings
from app.core.database import get_db, init_db
from app.core.gpc_middleware import GPCMiddleware
from app.core.logging_config import log_api_request, set_correlation_id, set_request_start_time
from app.core.rate_limit import rate_limiter
from app.core.scheduler import init_scheduler
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.token_blacklist import get_blacklist_backend, get_blacklist_size
from app.core.tracing import setup_tracing

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load settings
settings = get_settings()


# Create FastAPI application with enhanced OpenAPI configuration
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    current_settings = get_settings()
    scheduler = None
    riverside_sched = None

    # Startup
    logger.info("Starting Azure Governance Platform...")

    # Initialize database
    init_db()
    logger.info("Database initialized")

    # Initialize cache
    await cache_manager.initialize()
    logger.info("Cache initialized")

    if current_settings.disable_background_schedulers:
        app.state.scheduler_status = "disabled_for_test"
        logger.info(
            "Background schedulers intentionally disabled for browser-test harness "
            "(ENVIRONMENT=test, E2E_HARNESS=1)"
        )
    else:
        # Initialize and start data sync scheduler
        scheduler = init_scheduler()
        scheduler.start()
        app.state.scheduler_status = "running"
        logger.info("Background scheduler started")

        # Initialize Riverside compliance monitoring scheduler
        # Lazy import to avoid circular dependency at module level
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

    # Shutdown
    logger.info("Shutting down...")
    if riverside_sched is not None:
        riverside_sched.shutdown()
    if scheduler is not None:
        scheduler.shutdown()


# Create FastAPI application with enhanced OpenAPI configuration
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    # textwrap.dedent() strips the common 4-space indent that CommonMark
    # would otherwise render as an indented code block in Swagger UI (ncxl).
    description=textwrap.dedent("""
    **Azure Multi-Tenant Governance Platform**

    A comprehensive platform for managing Azure governance across multiple tenants.

    ## Key Features

    * **Cost Management** - Track, analyze, and optimize Azure spending across tenants
    * **Compliance Monitoring** - Continuous compliance assessment with CIS, ISO 27001, SOC 2, and custom frameworks
    * **Resource Management** - Inventory and lifecycle management for Azure resources
    * **Identity Governance** - MFA tracking, access reviews, and identity hygiene
    * **Riverside Compliance** - Specialized tracking for Riverside Company requirements
    * **DMARC Monitoring** - Email security posture monitoring

    ## Authentication

    The API supports multiple authentication methods:

    1. **OAuth 2.0 / OpenID Connect** via Azure AD (recommended)
    2. **Bearer Token** (JWT) for API access
    3. **API Key** for service-to-service calls

    See the authentication endpoints for details on obtaining tokens.

    ## Rate Limiting

    API requests are rate-limited to ensure fair usage:
    - Default: 100 requests per minute per client
    - Auth endpoints: 10 requests per minute
    - Sync endpoints: 5 concurrent requests

    Rate limit headers are included in all responses:
    - `X-RateLimit-Limit`: Maximum requests allowed
    - `X-RateLimit-Remaining`: Requests remaining in window
    - `X-RateLimit-Reset`: Unix timestamp when limit resets

    ## Security

    All API endpoints are protected with:
    - TLS 1.3 encryption in transit
    - Security headers (CSP, HSTS, X-Frame-Options)
    - Input validation and sanitization
    - Audit logging for sensitive operations

    ## Response Codes

    | Code | Meaning | Description |
    |------|---------|-------------|
    | 200 | OK | Request succeeded |
    | 201 | Created | Resource created successfully |
    | 400 | Bad Request | Invalid request parameters |
    | 401 | Unauthorized | Authentication required |
    | 403 | Forbidden | Insufficient permissions |
    | 404 | Not Found | Resource does not exist |
    | 409 | Conflict | Resource conflict (e.g., duplicate) |
    | 429 | Too Many Requests | Rate limit exceeded |
    | 500 | Internal Error | Server-side error |

    ## Support

    For API support, contact the Cloud Governance Team or visit:
    [Documentation](https://github.com/htt-brands/azure-governance-platform/tree/main/docs)
    """).strip(),
    lifespan=lifespan,
    docs_url=None,  # Disabled - using custom routes with auth protection
    redoc_url=None,  # Disabled - using custom routes with auth protection
    openapi_url="/openapi.json",
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "OAuth2 and token-based authentication endpoints",
        },
        {
            "name": "Dashboard",
            "description": "Dashboard summaries and overview metrics",
        },
        {
            "name": "Costs",
            "description": "Cost analysis, budgets, and spending reports",
        },
        {
            "name": "Compliance",
            "description": "Compliance status, frameworks, and rule management",
        },
        {
            "name": "Resources",
            "description": "Azure resource inventory and lifecycle management",
        },
        {
            "name": "Identity",
            "description": "Identity governance, MFA, and access reviews",
        },
        {
            "name": "Sync",
            "description": "Data synchronization jobs and scheduling",
        },
        {
            "name": "Riverside",
            "description": "Riverside Company compliance tracking",
        },
        {
            "name": "DMARC",
            "description": "Email security and DMARC monitoring",
        },
        {
            "name": "System",
            "description": "Health checks, metrics, and system status",
        },
    ],
    contact={
        "name": "Cloud Governance Team",
        "email": "cloud-governance@example.com",
    },
    license_info={
        "name": "MIT",
        "url": "https://github.com/htt-brands/azure-governance-platform/blob/main/LICENSE",
    },
)

# Configure CORS — single middleware, no wildcards, no duplicates
# SECURITY: Explicit origins, methods, and headers only (P1 fix)

_cors_origins = list(settings.cors_origins)
if settings.cors_allowed_origins:
    _cors_origins.extend(o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip())
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Initialize OpenTelemetry tracing (after app is created)
# This must happen after app creation but before routes are added
tracer = setup_tracing(app) if settings.enable_tracing else None

# GPC (Global Privacy Control) middleware - Legal compliance for CCPA/GDPR
# Must be after CORS but before security headers to properly set privacy-related headers
app.add_middleware(GPCMiddleware, log_all_requests=False)

# Enhanced Security Headers middleware
# SECURITY: Adds comprehensive security headers (CSP, Permissions-Policy, CORP, COOP, etc.)
app.add_middleware(SecurityHeadersMiddleware)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Add correlation ID to all requests for distributed tracing."""
    # Get or generate correlation ID
    cid = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())[:8]
    set_correlation_id(cid)

    # Process request
    response = await call_next(request)

    # Add to response headers
    response.headers["X-Correlation-ID"] = cid

    return response


@app.middleware("http")
async def api_logging_middleware(request: Request, call_next):
    """Log all API requests with timing and structured data.

    Logs method, path, status code, duration, user context for observability.
    """
    # Skip logging for health checks and metrics endpoints (reduces noise)
    if request.url.path in ["/health", "/health/detailed", "/metrics", "/api/v1/status"]:
        return await call_next(request)

    # Set start time for duration calculation
    set_request_start_time()
    start_time = time.perf_counter()

    # Extract user context if available
    user_id = getattr(request.state, "user_id", None)
    tenant_id = getattr(request.state, "tenant_id", None)

    # Process the request
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        status_code = 500
        raise
    finally:
        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log the request
        log_api_request(
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_ms=duration_ms,
            user_id=user_id,
            tenant_id=tenant_id,
            extra={
                "query_params": str(request.query_params),
                "client_host": request.client.host if request.client else None,
            },
        )

    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting to all requests.

    SECURITY: Provides DDoS protection and abuse prevention.
    """
    # Skip rate limiting for health checks and in development mode
    settings = get_settings()
    if settings.is_development or request.url.path in ["/health", "/health/detailed"]:
        response = await call_next(request)
        return response

    # Determine rate limit based on endpoint
    limit_config = rate_limiter.get_limit_config(request.url.path)

    try:
        allowed, headers = await rate_limiter.is_allowed(request, limit_config)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded. Please try again later."},
                headers={
                    **{k: str(v) for k, v in headers.items()},
                    "Retry-After": str(limit_config.window_seconds),
                },
            )

        response = await call_next(request)

        # Apply rate limit headers to successful responses
        for key, value in headers.items():
            response.headers[key] = str(value)

        return response

    except Exception as e:
        logger.error(f"Rate limiting error: {e}")
        # Fail-closed for auth endpoints (security-critical)
        if "/auth/" in request.url.path:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limiting unavailable. Please try again later."},
                headers={"Retry-After": "60"},
            )
        # Fail-open for non-auth endpoints (availability)
        return await call_next(request)


# Prometheus metrics
Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    excluded_handlers=["/health", "/health/detailed"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=True)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers - Auth router first (no auth required for login)
app.include_router(audit_logs_router)
app.include_router(quotas_router)
app.include_router(auth_router)
app.include_router(health_router)  # Health endpoint for load balancers

# Onboarding router (public for self-service)
app.include_router(onboarding_router)

# Protected routers (will be secured via dependencies in route files)
app.include_router(public_router)
app.include_router(dashboard_router)
app.include_router(design_system_router)
app.include_router(costs_router)
app.include_router(budgets_router)
app.include_router(compliance_router)
app.include_router(compliance_frameworks_router)
app.include_router(compliance_rules_router)
app.include_router(resources_router)
app.include_router(identity_router)
app.include_router(tenants_router)
app.include_router(sync_router)
app.include_router(riverside_router)
app.include_router(threats_router)
app.include_router(bulk_router)
app.include_router(dmarc_router)
app.include_router(accessibility_router)
app.include_router(exports_router)
app.include_router(pages_router)
app.include_router(topology_router)
app.include_router(preflight_router)
app.include_router(privacy_router)
app.include_router(search_router)
app.include_router(provisioning_standards_router)
app.include_router(metrics_router)
app.include_router(monitoring_router)
app.include_router(recommendations_router)
app.include_router(admin_router)


# =============================================================================
# API Documentation Routes (with auth protection in production)
# =============================================================================


@app.get("/docs", include_in_schema=False)
async def swagger_ui_html(request: Request) -> HTMLResponse:
    """Swagger UI documentation with auth protection in production.

    In development/staging: accessible without authentication.
    In production: requires valid JWT token (Bearer header or cookie).
    """
    # Require auth only in production (staging needs public docs for CI validation)
    from app.core.config import get_settings

    if get_settings().is_production:
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            token = request.cookies.get("access_token")

        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required to access API documentation"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validate token
        try:
            jwt_manager.decode_token(token)
        except Exception:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

    from fastapi.openapi.docs import get_swagger_ui_html

    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{settings.app_name} - Swagger UI",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )


@app.get("/redoc", include_in_schema=False)
async def redoc_html(request: Request) -> HTMLResponse:
    """ReDoc documentation with auth protection in production.

    In development/staging: accessible without authentication.
    In production: requires valid JWT token (Bearer header or cookie).
    """
    # Require auth only in production (staging needs public docs for CI validation)
    from app.core.config import get_settings

    if get_settings().is_production:
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            token = request.cookies.get("access_token")

        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required to access API documentation"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validate token
        try:
            jwt_manager.decode_token(token)
        except Exception:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

    from fastapi.openapi.docs import get_redoc_html

    return get_redoc_html(
        openapi_url="/openapi.json",
        title=f"{settings.app_name} - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2/bundles/redoc.standalone.js",
    )


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.environment,
    }


@app.get("/healthz/data")
async def healthz_data_alias(db: Session = Depends(get_db)):
    """Friendly alias for /api/v1/health/data — per-tenant sync freshness.

    Mounted at /healthz/data so the UI header partial and staging smoke
    checks can use a short, unversioned path. Delegates to the versioned
    endpoint to avoid duplicating the query logic.
    """
    from app.api.routes.health import data_freshness_check

    return await data_freshness_check(db=db)


@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with component status and pool statistics."""
    from app.core.database import _IS_SQLITE, SessionLocal, _get_engine

    components = {
        "database": "unknown",
        "scheduler": "unknown",
        "cache": "unknown",
        "azure_configured": settings.is_configured,
    }
    pool_stats = {}

    # Check database with pool stats
    try:
        from sqlalchemy import text

        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        components["database"] = "healthy"

        # Get connection pool statistics for SQL Server/Azure SQL
        if not _IS_SQLITE:
            engine = _get_engine()
            pool = engine.pool
            pool_stats = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
            }
    except Exception as e:
        components["database"] = f"unhealthy: {str(e)}"

    # Check scheduler
    from app.core.scheduler import get_scheduler

    scheduler = get_scheduler()
    if scheduler and scheduler.running:
        components["scheduler"] = "running"
    else:
        components["scheduler"] = "not_running"

    # Check cache with detailed metrics
    try:
        cache_metrics = cache_manager.get_metrics()
        components["cache"] = cache_metrics.get("backend", "unknown")
    except Exception as e:
        components["cache"] = f"error: {str(e)}"

    # Check token blacklist
    blacklist_backend = get_blacklist_backend()
    components["token_blacklist"] = blacklist_backend

    # Valid non-error states: explicit health statuses, booleans, and backend names
    _healthy_values = {"healthy", "running", "memory", "redis", True}

    # Build detailed cache metrics
    detailed_cache_metrics = {}
    try:
        cm = cache_manager.get_metrics()
        detailed_cache_metrics = {
            "backend": cm.get("backend", "unknown"),
            "hit_rate_percent": cm.get("hit_rate_percent", 0),
            "hits": cm.get("hits", 0),
            "misses": cm.get("misses", 0),
            "sets": cm.get("sets", 0),
            "deletes": cm.get("deletes", 0),
            "avg_get_time_ms": cm.get("avg_get_time_ms", 0),
        }
    except Exception as e:
        detailed_cache_metrics = {"error": str(e)}

    return {
        "status": "healthy"
        if all(v in _healthy_values for v in components.values())
        else "degraded",
        "version": settings.app_version,
        "components": components,
        "cache_metrics": detailed_cache_metrics,
        "database_pool": pool_stats if pool_stats else "n/a (SQLite)",
        "token_blacklist": {
            "backend": blacklist_backend,
            "size": get_blacklist_size(),
        },
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
async def root(request: Request):
    """Root endpoint - redirect to dashboard or login."""
    from fastapi.responses import RedirectResponse

    # Check if user has a token (cookie or header)
    has_token = request.cookies.get("access_token") or (
        request.headers.get("Authorization", "").startswith("Bearer ")
    )
    if has_token:
        return RedirectResponse(url="/dashboard")
    return RedirectResponse(url="/auth/login")


@app.exception_handler(401)
async def unauthorized_redirect(request: Request, exc):
    """Redirect browser requests to login page on 401."""
    from fastapi.responses import RedirectResponse

    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return RedirectResponse(url="/auth/login", status_code=302)
    # Preserve the original error detail from the HTTPException
    detail = getattr(exc, "detail", "Could not validate credentials")
    return JSONResponse(
        status_code=401,
        content={"detail": detail},
        headers={"WWW-Authenticate": "Bearer"},
    )


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


def load_openapi_examples() -> dict:
    """Load OpenAPI examples from docs/openapi-examples directory.

    Returns a dictionary of examples organized by category.
    """
    import json
    from pathlib import Path

    examples_dir = Path(__file__).parent.parent / "docs" / "openapi-examples"
    examples = {
        "auth": {},
        "requests": {},
        "responses": {},
    }

    if not examples_dir.exists():
        logger.warning(f"OpenAPI examples directory not found: {examples_dir}")
        return examples

    try:
        # Load auth examples
        auth_dir = examples_dir / "auth"
        if auth_dir.exists():
            for file in auth_dir.glob("*.json"):
                with open(file) as f:
                    examples["auth"][file.stem] = json.load(f)

        # Load request examples
        requests_dir = examples_dir / "requests"
        if requests_dir.exists():
            for file in requests_dir.glob("*.json"):
                with open(file) as f:
                    examples["requests"][file.stem] = json.load(f)

        # Load response examples
        responses_dir = examples_dir / "responses"
        if responses_dir.exists():
            for file in responses_dir.glob("*.json"):
                with open(file) as f:
                    examples["responses"][file.stem] = json.load(f)

        logger.info(
            f"Loaded OpenAPI examples: {len(examples['auth'])} auth, "
            f"{len(examples['requests'])} requests, "
            f"{len(examples['responses'])} responses"
        )
    except Exception as e:
        logger.warning(f"Failed to load OpenAPI examples: {e}")

    return examples


# Store examples on app state for access in routes
app.state.openapi_examples = load_openapi_examples()


def custom_openapi() -> dict:
    """Generate custom OpenAPI schema with enhanced documentation."""
    if app.openapi_schema:
        return app.openapi_schema

    from fastapi.openapi.utils import get_openapi

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
        contact=app.contact,
        license_info=app.license_info,
    )

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token obtained from Azure AD OAuth2 flow",
        },
        "oauth2": {
            "type": "oauth2",
            "flows": {
                "authorizationCode": {
                    "authorizationUrl": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
                    "tokenUrl": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                    "refreshUrl": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                    "scopes": {
                        "openid": "Authenticate user identity",
                        "profile": "Access user profile",
                        "email": "Access user email",
                        "User.Read": "Read user profile from Microsoft Graph",
                    },
                }
            },
            "description": "Azure AD OAuth2 authentication",
        },
        "apiKey": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key for service-to-service authentication",
        },
    }

    # Add security requirements (endpoints can override with [])
    openapi_schema["security"] = [
        {"bearerAuth": []},
        {"oauth2": ["openid", "profile", "email", "User.Read"]},
    ]

    # Add external documentation
    openapi_schema["externalDocs"] = {
        "description": "Full Documentation",
        "url": "https://github.com/htt-brands/azure-governance-platform/tree/main/docs",
    }

    # Add servers info
    openapi_schema["servers"] = [
        {
            "url": "/",
            "description": "Current server",
        },
        {
            "url": "https://api-staging.example.com",
            "description": "Staging server",
        },
        {
            "url": "https://api.example.com",
            "description": "Production server",
        },
    ]

    # Inject examples into P1 endpoint schemas
    _inject_openapi_examples(openapi_schema)

    app.openapi_schema = openapi_schema
    return app.openapi_schema


def _inject_openapi_examples(openapi_schema: dict) -> None:
    """Inject loaded examples into OpenAPI schema for key endpoints.

    Attaches request/response examples to P1 endpoints to enhance
    Swagger UI interactive documentation.
    """
    try:
        examples = getattr(app.state, "openapi_examples", {})
        if not examples:
            return

        responses = examples.get("responses", {})
        requests = examples.get("requests", {})

        # Map endpoint paths to their example files
        endpoint_examples = {
            "/api/v1/costs/summary": {
                "response": responses.get("cost_summary", {}),
                "request_params": requests.get("cost_summary_query", {}),
            },
            "/api/v1/compliance/summary": {
                "response": responses.get("compliance_summary", {}),
                "request_params": requests.get("compliance_summary_query", {}),
            },
            "/api/v1/resources/{resource_id}/history": {
                "response": responses.get("resource_lifecycle_history", {}),
                "request_params": requests.get("resource_lifecycle_query", {}),
            },
        }

        paths = openapi_schema.get("paths", {})

        for path, example_data in endpoint_examples.items():
            if path not in paths:
                continue

            methods = paths[path]
            for method, operation in methods.items():
                if method not in ("get", "post", "put", "patch", "delete"):
                    continue

                # Add response examples for 200 status
                if "response" in example_data and example_data["response"]:
                    response_example = example_data["response"]
                    if isinstance(response_example, dict):
                        # Extract example value from file structure
                        if "value" in response_example:
                            example_value = response_example["value"]
                        elif "example_response" in response_example:
                            example_value = response_example["example_response"]
                        else:
                            example_value = response_example

                        # Ensure response structure exists
                        if "responses" not in operation:
                            operation["responses"] = {}
                        if "200" not in operation["responses"]:
                            operation["responses"]["200"] = {"description": "Successful response"}

                        # Add example to content
                        if "content" not in operation["responses"]["200"]:
                            operation["responses"]["200"]["content"] = {
                                "application/json": {"schema": {"type": "object"}}
                            }

                        operation["responses"]["200"]["content"]["application/json"]["example"] = (
                            example_value
                        )

                        # Add summary/description from example file
                        if "summary" in response_example:
                            operation["responses"]["200"]["content"]["application/json"]["schema"][
                                "title"
                            ] = response_example["summary"]

                # Add parameter examples
                if "request_params" in example_data and example_data["request_params"]:
                    params_example = example_data["request_params"]
                    if isinstance(params_example, dict) and "value" in params_example:
                        for param_name, param_value in params_example["value"].items():
                            # Find or create parameter
                            param_found = False
                            for param in operation.get("parameters", []):
                                if param.get("name") == param_name:
                                    param["example"] = param_value
                                    param_found = True
                                    break

                            if not param_found:
                                if "parameters" not in operation:
                                    operation["parameters"] = []
                                operation["parameters"].append(
                                    {
                                        "name": param_name,
                                        "in": "query",
                                        "schema": {"type": _infer_schema_type(param_value)},
                                        "example": param_value,
                                    }
                                )

    except Exception as e:
        logger.warning(f"Failed to inject OpenAPI examples: {e}")


def _infer_schema_type(value) -> str:
    """Infer JSON Schema type from a Python value."""
    if isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "integer"
    elif isinstance(value, float):
        return "number"
    elif isinstance(value, list):
        return "array"
    elif isinstance(value, dict):
        return "object"
    else:
        return "string"


# Replace the default OpenAPI schema generator
app.openapi = custom_openapi


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
