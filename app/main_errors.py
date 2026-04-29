"""Application-wide exception handlers."""

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse


def register_exception_handlers(app, settings, logger) -> None:
    """Register global HTTP exception handlers."""

    @app.exception_handler(401)
    async def unauthorized_redirect(request: Request, exc):
        """Redirect browser requests to login page on 401."""
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            return RedirectResponse(url="/auth/login", status_code=302)

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
