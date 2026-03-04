"""Tests for Application Insights middleware (4vv)."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request
from starlette.responses import Response
from starlette.testclient import TestClient

from app.core.app_insights import AppInsightsMiddleware, init_app_insights


class TestAppInsightsMiddleware:
    """Tests for the request telemetry middleware."""

    def _make_request(self, path: str = "/api/test", method: str = "GET") -> Request:
        scope = {
            "type": "http",
            "method": method,
            "path": path,
            "query_string": b"",
            "headers": [],
            "root_path": "",
            "server": ("localhost", 8000),
        }
        return Request(scope)

    @pytest.mark.asyncio
    async def test_dispatch_adds_server_timing_header(self):
        """Middleware should add Server-Timing header."""
        middleware = AppInsightsMiddleware(app=MagicMock())

        response = Response(status_code=200)
        call_next = AsyncMock(return_value=response)
        request = self._make_request()

        result = await middleware.dispatch(request, call_next)

        assert "Server-Timing" in result.headers
        assert result.headers["Server-Timing"].startswith("total;dur=")

    @pytest.mark.asyncio
    async def test_dispatch_calls_next(self):
        """Middleware should pass request through to next handler."""
        middleware = AppInsightsMiddleware(app=MagicMock())

        response = Response(status_code=200)
        call_next = AsyncMock(return_value=response)
        request = self._make_request()

        result = await middleware.dispatch(request, call_next)

        call_next.assert_awaited_once_with(request)
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_dispatch_preserves_status_code(self):
        """Middleware should not alter the response status code."""
        middleware = AppInsightsMiddleware(app=MagicMock())

        response = Response(status_code=404)
        call_next = AsyncMock(return_value=response)
        request = self._make_request()

        result = await middleware.dispatch(request, call_next)
        assert result.status_code == 404


class TestInitAppInsights:
    """Tests for init_app_insights helper."""

    def test_adds_middleware_to_app(self):
        """init_app_insights should register the middleware."""
        app = MagicMock()
        init_app_insights(app)
        app.add_middleware.assert_called_once_with(AppInsightsMiddleware)
