"""Staging test configuration.

Provides fixtures for testing against a live staging URL.
No local server — all requests go to the real deployment.
"""

import os

import pytest
import requests


DEFAULT_STAGING_URL = "https://app-governance-staging-xnczpwyv.azurewebsites.net"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--staging-url",
        action="store",
        default=None,
        help="Base URL of the staging environment (overrides STAGING_URL env var)",
    )


@pytest.fixture(scope="session")
def staging_url(request: pytest.FixtureRequest) -> str:
    """Return the staging base URL, stripping trailing slash."""
    url = (
        request.config.getoption("--staging-url")
        or os.environ.get("STAGING_URL")
        or DEFAULT_STAGING_URL
    )
    return url.rstrip("/")


@pytest.fixture(scope="session")
def client(staging_url: str) -> requests.Session:
    """Unauthenticated HTTP session with reasonable timeouts."""
    s = requests.Session()
    s.headers.update({"User-Agent": "staging-validator/1.0"})
    # Verify the app is reachable before any tests run
    try:
        resp = s.get(f"{staging_url}/health", timeout=10)
        resp.raise_for_status()
    except Exception as exc:
        pytest.fail(
            f"Staging environment unreachable at {staging_url}/health — {exc}\n"
            "Deploy first: az webapp restart -g rg-governance-staging "
            "-n app-governance-staging-xnczpwyv"
        )
    return s


@pytest.fixture(scope="session")
def health_data(client: requests.Session, staging_url: str) -> dict:
    """Pre-fetched health response (cached for the session)."""
    return client.get(f"{staging_url}/health", timeout=10).json()
