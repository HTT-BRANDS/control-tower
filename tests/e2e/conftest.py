"""E2E test configuration and Playwright fixtures.

Spins up a real FastAPI server and provides authenticated/unauthenticated
Playwright browser contexts for full end-to-end testing.
"""

import multiprocessing
import os
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

    os.environ["ENVIRONMENT"] = "test"
    os.environ["E2E_HARNESS"] = "1"
    os.environ["BROWSER_TEST_DISABLE_SCHEDULERS"] = "true"

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
            r = httpx.get(f"{url}/api/v1/health", timeout=2)
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
#
# Browser tests must use real server-issued session cookies, never forged
# cookie values or persisted storage state. The login endpoint returns
# tokens via HttpOnly Set-Cookie headers; we validate that contract and
# then inject the issued cookie values into a fresh Playwright context.
# ---------------------------------------------------------------------------


def _extract_cookie(response: httpx.Response, cookie_name: str) -> str:
    """Extract a named cookie value from an httpx response cookie jar."""
    for cookie in response.cookies.jar:
        if cookie.name == cookie_name:
            return cookie.value
    msg = (
        f"Cookie '{cookie_name}' not found in login response. "
        f"Available cookies: {[c.name for c in response.cookies.jar]}"
    )
    raise KeyError(msg)


def _assert_login_cookie_contract(response: httpx.Response) -> None:
    """Validate that login issued the expected server-side cookie contract."""
    assert response.status_code == 200, f"Login failed: {response.status_code} {response.text}"
    body = response.json()
    assert body.get("cookies_set") is True

    set_cookie_headers = response.headers.get_list("set-cookie")
    for cookie_name in ("access_token", "refresh_token"):
        header = next(
            (value for value in set_cookie_headers if value.lower().startswith(f"{cookie_name}=")),
            None,
        )
        assert header is not None, f"Missing Set-Cookie header for {cookie_name}"
        lowered = header.lower()
        assert "httponly" in lowered, f"{cookie_name} must be HttpOnly"
        assert "path=/" in lowered, f"{cookie_name} must be scoped to /"
        assert "samesite=lax" in lowered, f"{cookie_name} must use SameSite=Lax"


def _login_via_server_session(base_url: str) -> httpx.Response:
    """Authenticate through the real login endpoint and return the raw response."""
    response = httpx.post(
        f"{base_url}/api/v1/auth/login",
        data={"username": "admin", "password": "admin"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    _assert_login_cookie_contract(response)
    return response


def _issued_playwright_cookies(response: httpx.Response, base_url: str) -> list[dict]:
    """Convert server-issued cookies into Playwright cookie payloads."""
    from urllib.parse import urlparse

    domain = urlparse(base_url).hostname
    assert domain, f"Could not determine cookie domain from {base_url}"

    cookies = []
    for cookie_name in ("access_token", "refresh_token"):
        cookies.append(
            {
                "name": cookie_name,
                "value": _extract_cookie(response, cookie_name),
                "domain": domain,
                "path": "/",
                "httpOnly": True,
                "sameSite": "Lax",
                "secure": False,
            }
        )
    return cookies


def _assert_fresh_context(context: BrowserContext) -> None:
    """Fail closed if a browser context already contains auth state."""
    existing_cookies = context.cookies()
    assert existing_cookies == [], (
        f"Expected fresh browser context, found cookies: {existing_cookies}"
    )


def _assert_issued_cookies_present(context: BrowserContext) -> None:
    """Verify the expected server-issued auth cookies exist in the context."""
    issued_names = {cookie["name"] for cookie in context.cookies()}
    expected_names = {"access_token", "refresh_token"}
    assert expected_names.issubset(issued_names), (
        f"Expected issued auth cookies {expected_names}, got {issued_names}"
    )


@pytest.fixture(scope="session")
def auth_token(base_url: str) -> str:
    """Acquire a JWT access token via the real login endpoint."""
    return _extract_cookie(_login_via_server_session(base_url), "access_token")


@pytest.fixture(scope="session")
def auth_tokens(base_url: str) -> dict:
    """Acquire full token set (access + refresh) via real session issuance."""
    response = _login_via_server_session(base_url)
    result = response.json()
    result["access_token"] = _extract_cookie(response, "access_token")
    result["refresh_token"] = _extract_cookie(response, "refresh_token")
    return result


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
def issued_auth_cookies(base_url: str) -> list[dict]:
    """Session-scoped server-issued auth cookies reused across fresh browser contexts."""
    response = _login_via_server_session(base_url)
    return _issued_playwright_cookies(response, base_url)


@pytest.fixture
def authenticated_context(
    browser: Browser,
    base_url: str,
    browser_context_args: dict,
    issued_auth_cookies: list[dict],
) -> Generator[BrowserContext, None, None]:
    """Fresh browser context authenticated with real server-issued cookies."""
    context = browser.new_context(**browser_context_args, base_url=base_url)

    _assert_fresh_context(context)
    context.add_cookies(issued_auth_cookies)
    _assert_issued_cookies_present(context)

    yield context
    context.close()


@pytest.fixture
def authenticated_page(
    authenticated_context: BrowserContext,
    base_url: str,
) -> Generator[Page, None, None]:
    """A fresh authenticated page with no shared storage state."""
    page = authenticated_context.new_page()
    page._base_url = base_url  # type: ignore[attr-defined]
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
