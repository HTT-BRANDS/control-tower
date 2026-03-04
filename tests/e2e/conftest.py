"""E2E test configuration and fixtures.

Uses Playwright for browser-based testing against a running FastAPI server.
"""

import multiprocessing
import time

import httpx
import pytest


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
def base_url():
    """Start the FastAPI app and return its base URL."""
    proc = multiprocessing.Process(target=_run_server, daemon=True)
    proc.start()

    # Wait for server to be ready
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


@pytest.fixture(scope="session")
def browser_context_args():
    """Default browser context arguments."""
    return {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }
