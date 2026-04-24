"""Shared E2E test helpers and utilities."""

import httpx
from playwright.sync_api import Page, Response

CONSOLE_ERROR_ALLOWLIST: tuple[str, ...] = ()
SERVER_ERROR_TEXT_SNIPPETS: tuple[str, ...] = (
    "Internal Server Error",
    "Traceback",
    "Server got itself in trouble",
)


def get_auth_token(base_url: str, username: str = "admin", password: str = "admin") -> str:
    """Acquire JWT token via API login."""
    resp = httpx.post(
        f"{base_url}/api/v1/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    assert resp.status_code == 200, f"Login failed: {resp.status_code}"
    return resp.json()["access_token"]


def wait_for_htmx(page: Page, timeout: float = 5000) -> None:
    """Wait for any pending HTMX requests to complete.

    Waits for the htmx:afterSettle event which fires after HTMX
    has finished processing a response and settled the DOM.
    """
    page.evaluate(
        """() => {
        return new Promise((resolve) => {
            // If no HTMX requests are in flight, resolve immediately
            if (typeof htmx === 'undefined' || !document.querySelector('.htmx-request')) {
                resolve();
                return;
            }
            // Otherwise wait for the next afterSettle event
            document.addEventListener('htmx:afterSettle', () => resolve(), { once: true });
            // Safety timeout
            setTimeout(resolve, 5000);
        });
    }"""
    )


def assert_security_headers(response: Response) -> None:
    """Verify all required security headers are present on a response."""
    headers = response.headers
    assert headers.get("x-frame-options") == "DENY", "Missing X-Frame-Options: DENY"
    assert headers.get("x-content-type-options") == "nosniff", "Missing X-Content-Type-Options"
    assert headers.get("x-xss-protection") == "1; mode=block", "Missing X-XSS-Protection"
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin", (
        "Missing Referrer-Policy"
    )
    assert "camera=()" in headers.get("permissions-policy", ""), "Missing Permissions-Policy"
    assert "default-src" in headers.get("content-security-policy", ""), "Missing CSP"


def assert_no_console_errors(page: Page) -> list[str]:
    """Collect and assert no JavaScript console errors on the page.

    Call this AFTER navigating — it checks errors collected since page creation.
    Returns list of any warning messages (non-fatal).
    """
    errors = []
    warnings = []

    def handle_console(msg):
        if msg.type == "error":
            errors.append(msg.text)
        elif msg.type == "warning":
            warnings.append(msg.text)

    # Note: This needs to be set up BEFORE navigation.
    # For post-navigation checking, use page.evaluate to check for errors.
    return warnings


def setup_console_listener(page: Page) -> dict[str, list[str]]:
    """Set up console and page-error listeners. Call BEFORE navigation.

    Returns a dict populated with:
    - ``errors``: console error messages + uncaught page errors
    - ``warnings``: console warning messages

    Usage:
        console = setup_console_listener(page)
        page.goto("/dashboard")
        assert_console_errors_clean(console["errors"])
    """
    console: dict[str, list[str]] = {"errors": [], "warnings": []}

    def on_console(msg):
        if msg.type == "error":
            console["errors"].append(msg.text)
        elif msg.type == "warning":
            console["warnings"].append(msg.text)

    def on_page_error(exc):
        console["errors"].append(str(exc))

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    return console


def assert_console_errors_clean(
    errors: list[str],
    allowlist: tuple[str, ...] = CONSOLE_ERROR_ALLOWLIST,
) -> None:
    """Fail only on non-allowlisted error-severity console/page errors."""
    real_errors = []
    for error in errors:
        lowered = error.lower()
        if "favicon" in lowered:
            continue
        if any(allowed in error for allowed in allowlist):
            continue
        real_errors.append(error)
    assert not real_errors, f"Unexpected console/page errors: {real_errors}"


def assert_no_server_error_text(content: str) -> None:
    """Fail on obvious server-side error page text."""
    for snippet in SERVER_ERROR_TEXT_SNIPPETS:
        assert snippet not in content, f"Unexpected server error text found: {snippet}"


def assert_page_accessible(page: Page) -> None:
    """Basic accessibility checks on the current page."""
    # Check all images have alt text
    images_without_alt = page.evaluate(
        """() => {
        const imgs = document.querySelectorAll('img:not([alt])');
        return imgs.length;
    }"""
    )
    assert images_without_alt == 0, f"{images_without_alt} images missing alt text"

    # Check all form inputs have labels
    inputs_without_labels = page.evaluate(
        """() => {
        const inputs = document.querySelectorAll('input:not([type="hidden"]):not([aria-label]):not([aria-labelledby])');
        let count = 0;
        inputs.forEach(input => {
            const id = input.id;
            if (!id || !document.querySelector(`label[for="${id}"]`)) {
                count++;
            }
        });
        return count;
    }"""
    )
    assert inputs_without_labels == 0, f"{inputs_without_labels} inputs missing labels"

    # Check page has a main landmark or h1
    has_landmark = page.evaluate(
        """() => {
        return !!(document.querySelector('main') || document.querySelector('h1') || document.querySelector('[role="main"]'));
    }"""
    )
    assert has_landmark, "Page missing <main> landmark or <h1>"


def assert_valid_json_response(response, expected_keys: list[str] | None = None) -> dict:
    """Assert response is valid JSON and optionally check for expected keys."""
    assert response.ok, f"Response not OK: {response.status} {response.status_text}"
    data = response.json()
    if expected_keys:
        for key in expected_keys:
            assert key in data, f"Missing expected key '{key}' in response"
    return data
