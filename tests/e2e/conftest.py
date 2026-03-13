"""E2E test configuration and Playwright fixtures.

Spins up a real FastAPI server and provides authenticated/unauthenticated
Playwright browser contexts for full end-to-end testing.
"""

import multiprocessing
import time
from collections.abc import Generator

import httpx
import pytest
from playwright.sync_api import APIRequestContext, Browser, BrowserContext, Page, Playwright

# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------


def _run_server():
    """Run uvicorn server in a subprocess."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8099,
        log_level="warning",
    )


@pytest.fixture(scope="session")
def base_url() -> Generator[str, None, None]:
    """Start the FastAPI app and return its base URL."""
    proc = multiprocessing.Process(target=_run_server, daemon=True)
    proc.start()

    url = "http://127.0.0.1:8099"
    for _ in range(30):
        try:
            r = httpx.get(f"{url}/health", timeout=2)
            if r.status_code == 200:
                break
        except (httpx.ConnectError, httpx.ReadTimeout):
            pass
        time.sleep(0.5)
    else:
        proc.kill()
        pytest.fail("Server did not start within 15 seconds")

    yield url

    proc.kill()
    proc.join(timeout=5)


# ---------------------------------------------------------------------------
# Auth token acquisition
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def auth_token(base_url: str) -> str:
    """Acquire a JWT access token via the dev login endpoint."""
    resp = httpx.post(
        f"{base_url}/api/v1/auth/login",
        data={"username": "admin", "password": "admin"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="session")
def auth_tokens(base_url: str) -> dict:
    """Acquire full token set (access + refresh) via dev login."""
    resp = httpx.post(
        f"{base_url}/api/v1/auth/login",
        data={"username": "admin", "password": "admin"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    return resp.json()


# ---------------------------------------------------------------------------
# Playwright browser fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def browser_context_args():
    """Default browser context arguments."""
    return {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture(scope="session")
def authenticated_context(
    browser: Browser,
    base_url: str,
    auth_token: str,
    browser_context_args: dict,
) -> Generator[BrowserContext, None, None]:
    """Browser context with auth token injected as extra HTTP header."""
    context = browser.new_context(
        **browser_context_args,
        base_url=base_url,
        extra_http_headers={"Authorization": f"Bearer {auth_token}"},
    )
    yield context
    context.close()


@pytest.fixture
def authenticated_page(authenticated_context: BrowserContext) -> Generator[Page, None, None]:
    """A fresh page within the authenticated browser context."""
    page = authenticated_context.new_page()
    yield page
    page.close()


@pytest.fixture
def unauthenticated_page(
    browser: Browser,
    base_url: str,
    browser_context_args: dict,
) -> Generator[Page, None, None]:
    """A fresh page with NO authentication."""
    context = browser.new_context(**browser_context_args, base_url=base_url)
    page = context.new_page()
    yield page
    page.close()
    context.close()


# ---------------------------------------------------------------------------
# Playwright API request context (for pure API E2E tests)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def api_context(
    playwright: Playwright,
    base_url: str,
    auth_token: str,
) -> Generator[APIRequestContext, None, None]:
    """Authenticated Playwright APIRequestContext for API-level E2E tests."""
    context = playwright.request.new_context(
        base_url=base_url,
        extra_http_headers={
            "Authorization": f"Bearer {auth_token}",
            "Accept": "application/json",
        },
    )
    yield context
    context.dispose()


@pytest.fixture(scope="session")
def unauth_api_context(
    playwright: Playwright,
    base_url: str,
) -> Generator[APIRequestContext, None, None]:
    """Unauthenticated Playwright APIRequestContext."""
    context = playwright.request.new_context(
        base_url=base_url,
        extra_http_headers={"Accept": "application/json"},
    )
    yield context
    context.dispose()


# ---------------------------------------------------------------------------
# Screenshot on failure hook
# ---------------------------------------------------------------------------


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture screenshot on test failure for any test using a 'page' fixture."""
    import os

    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        # Try to get page from the test's fixtures
        page = item.funcargs.get("authenticated_page") or item.funcargs.get("unauthenticated_page")
        if page and not page.is_closed():
            try:
                screenshot_dir = "tests/e2e/screenshots"
                os.makedirs(screenshot_dir, exist_ok=True)
                path = f"{screenshot_dir}/{item.nodeid.replace('/', '_').replace('::', '_')}.png"
                page.screenshot(path=path)
            except Exception:
                pass  # Don't fail the test because of screenshot issues
