"""Unit tests for section page routes.

Tests the page route definitions in app/api/routes/pages.py.

Traces: UI-001 — Page route registration and template rendering
for Costs, Compliance, Resources, and Identity sections.
"""

from app.api.routes.pages import router


class TestPagesRouterRegistration:
    """Tests for pages router registration."""

    def test_router_exists(self):
        """Router should be an APIRouter instance."""
        from fastapi import APIRouter

        assert isinstance(router, APIRouter)

    def test_router_tagged(self):
        """Router should be tagged as 'pages'."""
        assert "pages" in router.tags

    def test_has_costs_route(self):
        """Should have a /costs route."""
        paths = [r.path for r in router.routes]
        assert "/costs" in paths

    def test_has_compliance_route(self):
        """Should have a /compliance route."""
        paths = [r.path for r in router.routes]
        assert "/compliance" in paths

    def test_has_resources_route(self):
        """Should have a /resources route."""
        paths = [r.path for r in router.routes]
        assert "/resources" in paths

    def test_has_identity_route(self):
        """Should have an /identity route."""
        paths = [r.path for r in router.routes]
        assert "/identity" in paths

    def test_route_count(self):
        """Should have exactly 7 page routes (including privacy, admin, and admin partial)."""
        paths = [r.path for r in router.routes]
        assert len(paths) == 7

    def test_all_routes_are_get(self):
        """All page routes should be GET endpoints."""
        for route in router.routes:
            assert "GET" in route.methods
