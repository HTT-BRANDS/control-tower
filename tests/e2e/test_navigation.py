"""E2E tests for navigation, page rendering, and static asset loading.

These tests verify core navigation behaviour (redirects, login page
structure) and that static assets are served correctly.
"""

import httpx
import pytest


@pytest.fixture(scope="module")
def client(base_url: str) -> httpx.Client:
    """Yield an httpx Client pointed at the running test server."""
    with httpx.Client(base_url=base_url, timeout=10) as c:
        yield c


class TestRootRedirect:
    """GET / should redirect to either /dashboard or /auth/login."""

    def test_root_redirects(self, client: httpx.Client) -> None:
        resp = client.get("/", follow_redirects=True)
        final_url = str(resp.url)
        assert "/dashboard" in final_url or "/auth/login" in final_url, (
            f"Expected redirect to /dashboard or /auth/login, got {final_url}"
        )


class TestLoginPage:
    """GET /auth/login should render a login form."""

    def test_login_page_has_form(self, client: httpx.Client) -> None:
        resp = client.get("/auth/login")
        assert resp.status_code == 200
        assert "<form" in resp.text, "Login page should contain a <form> element"


class TestStaticAssets:
    """Static assets should be served with 200 OK."""

    def test_static_css_loads(self, client: httpx.Client) -> None:
        resp = client.get("/static/css/theme.css")
        assert resp.status_code == 200
