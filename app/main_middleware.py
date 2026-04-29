"""Middleware and observability setup for the FastAPI app."""

import time
import uuid

from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import get_settings
from app.core.gpc_middleware import GPCMiddleware
from app.core.logging_config import log_api_request, set_correlation_id, set_request_start_time
from app.core.rate_limit import rate_limiter
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.tracing import setup_tracing

QUIET_LOG_PATHS = {"/health", "/health/detailed", "/metrics", "/api/v1/status"}
RATE_LIMIT_EXEMPT_PATHS = {"/health", "/health/detailed"}


def configure_middleware(app, settings, logger):
    """Install CORS, tracing, security, request logging, and rate-limit middleware."""
    _configure_cors(app, settings)
    tracer = setup_tracing(app) if settings.enable_tracing else None

    app.add_middleware(GPCMiddleware, log_all_requests=False)
    app.add_middleware(SecurityHeadersMiddleware)

    _register_correlation_middleware(app)
    _register_api_logging_middleware(app)
    _register_rate_limit_middleware(app, logger)
    _register_prometheus_metrics(app)

    return tracer


def _configure_cors(app, settings) -> None:
    cors_origins = list(settings.cors_origins)
    if settings.cors_allowed_origins:
        cors_origins.extend(
            origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )


def _register_correlation_middleware(app) -> None:
    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next):
        """Add correlation ID to all requests for distributed tracing."""
        cid = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())[:8]
        set_correlation_id(cid)

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = cid
        return response


def _register_api_logging_middleware(app) -> None:
    @app.middleware("http")
    async def api_logging_middleware(request: Request, call_next):
        """Log API requests with timing and structured context."""
        if request.url.path in QUIET_LOG_PATHS:
            return await call_next(request)

        set_request_start_time()
        start_time = time.perf_counter()
        user_id = getattr(request.state, "user_id", None)
        tenant_id = getattr(request.state, "tenant_id", None)

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
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


def _register_rate_limit_middleware(app, logger) -> None:
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        """Apply request rate limiting."""
        current_settings = get_settings()
        if current_settings.is_development or request.url.path in RATE_LIMIT_EXEMPT_PATHS:
            return await call_next(request)

        limit_config = rate_limiter.get_limit_config(request.url.path)

        try:
            allowed, headers = await rate_limiter.is_allowed(request, limit_config)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"error": "Rate limit exceeded. Please try again later."},
                    headers={
                        **{key: str(value) for key, value in headers.items()},
                        "Retry-After": str(limit_config.window_seconds),
                    },
                )

            response = await call_next(request)
            for key, value in headers.items():
                response.headers[key] = str(value)
            return response

        except Exception as exc:
            logger.error(f"Rate limiting error: {exc}")
            if "/auth/" in request.url.path:
                return JSONResponse(
                    status_code=429,
                    content={"error": "Rate limiting unavailable. Please try again later."},
                    headers={"Retry-After": "60"},
                )
            return await call_next(request)


def _register_prometheus_metrics(app) -> None:
    Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        excluded_handlers=["/health", "/health/detailed"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=True)
