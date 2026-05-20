"""Application-wide exception handlers.

ct-tdu: now includes a content-negotiated 404 handler — browsers get a
branded HTML page, API clients (anything not asking for ``text/html``)
get the existing JSON shape.
"""

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse


def register_exception_handlers(app, settings, logger) -> None:
    """Register global HTTP exception handlers."""

    # ct-tdu: HTML 404 body — kept in this module (rather than a Jinja
    # template) because exception handlers run very early in the request
    # lifecycle and we want them to work even if the Jinja environment
    # is misconfigured. A static string keeps the failure mode small.
    # The HTML inlines a tiny amount of CSS to stay self-contained;
    # everything else (font, brand colors) gracefully degrades.
    _NOT_FOUND_HTML = (
        "<!DOCTYPE html>"
        '<html lang="en"><head>'
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Page not found — HTT Control Tower</title>"
        '<link rel="icon" type="image/svg+xml" href="/static/favicon.svg">'
        '<meta name="theme-color" content="#500711">'
        "<style>"
        "body{font-family:'Inter',system-ui,sans-serif;background:#f7f5f3;"
        "color:#1f1417;margin:0;min-height:100vh;display:flex;"
        "align-items:center;justify-content:center;padding:2rem}"
        ".card{background:#fff;border-radius:.5rem;box-shadow:0 4px 6px "
        "rgba(0,0,0,.07);padding:2.5rem;max-width:28rem;text-align:center}"
        "h1{color:#500711;font-size:3rem;margin:0 0 .5rem;font-weight:700}"
        "h2{font-size:1.125rem;margin:0 0 1rem;font-weight:600}"
        "p{color:#6b5b5e;font-size:.875rem;margin:0 0 1.5rem}"
        "a{display:inline-block;background:#500711;color:#fff;"
        "padding:.625rem 1.25rem;border-radius:.375rem;text-decoration:none;"
        "font-size:.875rem;font-weight:600}"
        "a:hover{background:#3d050d}"
        "a:focus-visible{outline:2px solid #ffb000;outline-offset:2px}"
        "</style></head>"
        '<body><main class="card" aria-labelledby="nf-heading">'
        '<h1 id="nf-heading">404</h1>'
        "<h2>We can't find that page</h2>"
        "<p>The URL you followed doesn't match any page in HTT Control "
        "Tower. If you arrived here from a bookmark, the link may have "
        "moved during a recent release.</p>"
        '<a href="/">Back to dashboard</a>'
        "</main></body></html>"
    )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: HTTPException):
        """Content-negotiated 404: HTML for browsers, JSON for everyone else.

        Browsers (anything with ``text/html`` in Accept) get the branded
        404 page. API clients keep the original ``{"detail": "..."}``
        JSON shape so existing integrations don't break.
        """
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            return HTMLResponse(content=_NOT_FOUND_HTML, status_code=404)
        detail = getattr(exc, "detail", "Not Found")
        return JSONResponse(status_code=404, content={"detail": detail})

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
