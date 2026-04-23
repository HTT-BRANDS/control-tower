"""Staging test configuration.

Provides fixtures for testing against a live staging URL.
No local server — all requests go to the real deployment.

Cold-start mitigation (bd mvxt compensating control):
    The staging App Service runs on a resource-constrained plan (B1 after
    the April 16 cost-optimization). Post-deploy cold-starts routinely
    exceed 60s, which made every single-attempt `requests.get(/health,
    timeout=10)` fail with ReadTimeout and cascade into dozens of errors
    in the validation suite.

    This file now does two things:
      1. `_warmup_staging` — polls /health with exponential backoff up to
         ~4 minutes before any test runs.
      2. `client` fixture's Session gets a urllib3 Retry adapter so mid-
         suite transient timeouts / 5xx retry instead of hard-failing.

    Root cause (scheduler liveness, SNAT, plan-tier sizing) still under
    investigation in bd mvxt. When that lands, this mitigation can stay
    as defense-in-depth — there's no downside to making CI resilient.
"""

import os
import time

import pytest
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_STAGING_URL = "https://app-governance-staging-xnczpwyv.azurewebsites.net"

# Warmup schedule: five attempts with increasing timeouts. Total worst-case
# wait ≈ 10 + 30 + 60 + 90 + 120 = 310s between delays + timeouts. Matches
# observed B1-plan cold-start upper bound (~3 min) with headroom.
_WARMUP_ATTEMPTS: tuple[tuple[int, int], ...] = (
    # (request_timeout_s, sleep_after_failure_s)
    (10, 5),
    (30, 10),
    (60, 20),
    (90, 30),
    (120, 0),
)


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
def is_production(staging_url: str) -> bool:
    """True when tests target the production URL (docs requires auth there)."""
    return "-prod" in staging_url or "production" in staging_url


def _build_session() -> requests.Session:
    """Session with mid-run retry adapter for transient timeouts / 5xx.

    Not a substitute for _warmup_staging — the warmup handles the initial
    cold-start explicitly with visible progress; this adapter handles the
    in-test flakes that still occur occasionally under load.
    """
    s = requests.Session()
    s.headers.update({"User-Agent": "staging-validator/1.0"})

    # Retry GET+HEAD+OPTIONS only — never auto-retry POST/PUT/DELETE because
    # idempotency is the test's concern, not ours.
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1.5,  # 0s, 1.5s, 4.5s between attempts
        status_forcelist=(502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD", "OPTIONS"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s


def _warmup_staging(session: requests.Session, staging_url: str) -> None:
    """Block until the staging app returns a healthy /health, or give up clearly.

    Raises pytest.fail() with an actionable message when all attempts exhaust —
    no silent swallow, no "just hope it's warm" behavior.
    """
    last_exc: Exception | None = None
    for attempt, (timeout_s, sleep_s) in enumerate(_WARMUP_ATTEMPTS, start=1):
        try:
            resp = session.get(f"{staging_url}/health", timeout=timeout_s)
            if resp.ok:
                if attempt > 1:
                    # Advertise how long the warmup took so CI logs capture the
                    # cold-start cost trend — useful data for the mvxt root-cause.
                    print(f"[staging-warmup] /health OK on attempt {attempt}")
                return
            last_exc = requests.HTTPError(f"HTTP {resp.status_code}")
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_exc = exc
        if sleep_s:
            time.sleep(sleep_s)

    pytest.fail(
        f"Staging warmup failed after {len(_WARMUP_ATTEMPTS)} attempts at "
        f"{staging_url}/health — last error: {last_exc!r}\n"
        "Likely causes (bd mvxt):\n"
        "  1. App Service cold-start exceeded ~3 minutes (B1 plan saturation).\n"
        "  2. Recent deploy didn't actually restart the container.\n"
        "  3. Infra regression (SNAT exhaustion / SQL unavailable).\n"
        "Next: check App Insights for the cold-start log + last deploy success."
    )


@pytest.fixture(scope="session")
def client(staging_url: str) -> requests.Session:
    """Unauthenticated HTTP session with retry adapter + cold-start warmup."""
    s = _build_session()
    _warmup_staging(s, staging_url)
    return s


@pytest.fixture(scope="session")
def health_data(client: requests.Session, staging_url: str) -> dict:
    """Pre-fetched health response (cached for the session).

    Uses a slightly longer timeout than individual test calls because the
    session-scoped cost of this call should absorb the rare follow-on cold-
    start that can happen if only /health was warmed during fixture setup.
    """
    return client.get(f"{staging_url}/health", timeout=30).json()
