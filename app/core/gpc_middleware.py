"""
Global Privacy Control (GPC) Middleware

Detects and honors Sec-GPC:1 signals per CCPA/CPRA § 1798.135(b)
https://privacycg.github.io/gpc-spec/
"""

import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class GPCMiddleware(BaseHTTPMiddleware):
    """
    Middleware to detect and honor Global Privacy Control signals.
    
    When Sec-GPC:1 header is present, the user is opting out of:
    - Sale/sharing of personal information
    - Targeted advertising
    - Cross-site tracking
    
    This middleware:
    1. Detects GPC signal from browser headers
    2. Sets request.state.gpc_enabled for downstream use
    3. Logs GPC events for audit trail
    4. Signals to frontend via response header
    """

    def __init__(self, app: ASGIApp, log_all_requests: bool = False):
        super().__init__(app)
        self.log_all_requests = log_all_requests

    async def dispatch(self, request: Request, call_next) -> Response:
        # Detect GPC signal
        gpc_header = request.headers.get("Sec-GPC", "0")
        gpc_enabled = gpc_header == "1"

        # Store in request state for access in routes
        request.state.gpc_enabled = gpc_enabled

        # Log GPC detection (always log when enabled, optionally log all)
        if gpc_enabled or self.log_all_requests:
            logger.info(
                "GPC signal detected" if gpc_enabled else "GPC signal not present",
                extra={
                    "gpc_enabled": gpc_enabled,
                    "path": request.url.path,
                    "method": request.method,
                    "user_agent": request.headers.get("User-Agent", "unknown"),
                    "client_ip": request.client.host if request.client else None,
                }
            )

        # Process request
        response = await call_next(request)

        # Signal GPC status to frontend
        response.headers["X-GPC-Detected"] = "1" if gpc_enabled else "0"

        # Add GPC-related security headers
        if gpc_enabled:
            # Stronger privacy stance when GPC is enabled
            response.headers["Permissions-Policy"] = (
                "geolocation=(), microphone=(), camera=(), "
                "payment=(), usb=(), magnetometer=(), gyroscope=(), "
                "accelerometer=(), interest-cohort=()"
            )

        return response


def get_gpc_status(request: Request) -> bool:
    """
    Helper function to check GPC status in route handlers.
    
    Usage:
        @app.get("/some-route")
        async def some_route(request: Request):
            if get_gpc_status(request):
                # Don't track, don't personalize
                pass
    """
    return getattr(request.state, "gpc_enabled", False)


class GPCConsentManager:
    """
    Manages consent preferences when GPC is enabled.
    
    When GPC signal is present, automatically opts out of:
    - Analytics tracking
    - Marketing cookies
    - Third-party data sharing
    - Personalized content
    """

    GPC_CATEGORIES = {
        "analytics": False,      # GPC opts out of analytics
        "marketing": False,      # GPC opts out of marketing
        "functional": True,      # Functional cookies still allowed
        "necessary": True,       # Necessary cookies always allowed
    }

    @classmethod
    def get_consent_for_gpc_user(cls) -> dict[str, bool]:
        """Returns default consent settings for GPC-enabled users."""
        return cls.GPC_CATEGORIES.copy()

    @classmethod
    def should_track(cls, gpc_enabled: bool) -> bool:
        """Returns False if user has GPC enabled (do not track)."""
        return not gpc_enabled

    @classmethod
    def should_share_data(cls, gpc_enabled: bool) -> bool:
        """Returns False if user has GPC enabled (do not share)."""
        return not gpc_enabled
