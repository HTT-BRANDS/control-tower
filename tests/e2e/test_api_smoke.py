"""E2E smoke tests verifying protected API endpoints reject unauthenticated requests."""

import httpx
import pytest


@pytest.fixture(scope="module")
def client(base_url):
    """HTTP client without auth credentials."""
    with httpx.Client(base_url=base_url, timeout=10) as c:
        yield c


class TestProtectedEndpointsRequireAuth:
    """All protected API endpoints should return 401 or 403 without authentication."""

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/preflight/status",
            "/api/v1/sync/metrics",
            "/api/v1/recommendations",
            "/monitoring/performance",
            "/monitoring/cache",
            "/api/v1/costs/summary",
            "/api/v1/compliance/summary",
            "/api/v1/identity/summary",
        ],
    )
    def test_endpoint_rejects_unauthenticated_request(self, client, path):
        """Protected endpoint should return 401 or 403 without auth token."""
        response = client.get(path)
        assert response.status_code in (401, 403), (
            f"{path} returned {response.status_code}, expected 401 or 403"
        )

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/preflight/run",
            "/api/v1/sync/trigger/costs",
        ],
    )
    def test_post_endpoint_rejects_unauthenticated_request(self, client, path):
        """Protected POST endpoints should also reject without auth."""
        response = client.post(path)
        assert response.status_code in (401, 403, 405), (
            f"POST {path} returned {response.status_code}, expected 401/403/405"
        )
