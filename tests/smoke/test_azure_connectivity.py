"""Comprehensive smoke test suite for Azure Governance Platform.

This module provides smoke tests that verify the deployment health and
Azure connectivity of the Azure Governance Platform. These tests can be
run post-deployment to ensure all components are functioning correctly.

Test Categories:
    - API Health: Basic health checks and metrics endpoints
    - Azure Connectivity: Tests requiring Azure credentials
    - Authentication: Public vs protected endpoint validation
    - Riverside-Specific: Riverside compliance endpoints

Usage:
    # Run all smoke tests
    uv run pytest tests/smoke/ -v

    # Run specific test category
    uv run pytest tests/smoke/test_azure_connectivity.py -v -k "health"

    # Run with Azure credentials (for full connectivity tests)
    export AZURE_TENANT_ID="your-tenant-id"
    export AZURE_CLIENT_ID="your-client-id"
    export AZURE_CLIENT_SECRET="your-client-secret"
    uv run pytest tests/smoke/ -v

Requirements:
    - pytest-asyncio
    - httpx
    - Running instance of Azure Governance Platform

Note:
    Tests marked with `azure_creds_required` will be skipped if Azure
d    credentials are not configured. This allows the test suite to run
    in environments without Azure access while still providing value.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

import httpx
import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


# ============================================================================
# Configuration and Fixtures
# ============================================================================


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "azure_creds_required: marks tests requiring Azure credentials",
    )
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    )
    config.addinivalue_line(
        "markers",
        "auth_required: marks tests requiring authentication",
    )


@pytest.fixture(scope="session")
def base_url() -> str:
    """Provide the base URL for API requests.

    The base URL can be configured via the BASE_URL environment variable.
    Defaults to http://localhost:8000 for local development.

    Returns:
        str: The base URL of the API server.

    Example:
        export BASE_URL="https://api.production.example.com"
        uv run pytest tests/smoke/ -v
    """
    return os.environ.get("BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def azure_credentials_configured() -> bool:
    """Check if Azure credentials are configured.

    Returns True if all required Azure environment variables are set.
    Tests requiring Azure connectivity can use this to conditionally skip.

    Required environment variables:
        - AZURE_TENANT_ID
        - AZURE_CLIENT_ID
        - AZURE_CLIENT_SECRET

    Returns:
        bool: True if all Azure credentials are configured.
    """
    required_vars = ["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET"]
    return all(os.environ.get(var) for var in required_vars)


@pytest.fixture
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an HTTP client for making async requests.

        This fixture provides a configured httpx.AsyncClient with reasonable
    timeouts and automatic cleanup after each test.

        Yields:
            httpx.AsyncClient: Configured async HTTP client.
    """
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), follow_redirects=True) as client:
        yield client


@pytest.fixture
async def authenticated_client(
    base_url: str,
    http_client: httpx.AsyncClient,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an authenticated HTTP client.

    This fixture attempts to authenticate with the API and returns a client
    with the access token set in the Authorization header.

    If authentication fails, tests using this fixture will be skipped.

    Yields:
        httpx.AsyncClient: Authenticated async HTTP client.
    """
    # Try to get credentials from environment
    username = os.environ.get("TEST_USERNAME", "test@example.com")
    password = os.environ.get("TEST_PASSWORD", "test")

    auth_url = urljoin(base_url, "/api/v1/auth/login")

    try:
        response = await http_client.post(
            auth_url,
            data={"username": username, "password": password},
        )

        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            if token:
                http_client.headers["Authorization"] = f"Bearer {token}"
                yield http_client
                return
    except Exception as exc:
        pytest.skip(f"Authentication failed: {exc}")

    pytest.skip("Could not authenticate - skipping authenticated tests")


# ============================================================================
# Helper Functions
# ============================================================================


def get_full_url(base_url: str, endpoint: str) -> str:
    """Build a full URL from base URL and endpoint path.

    Args:
        base_url: The base URL of the API.
        endpoint: The API endpoint path.

    Returns:
        str: The full URL.
    """
    return urljoin(base_url, endpoint)


async def assert_successful_response(
    response: httpx.Response,
    expected_status: int = 200,
) -> dict[str, Any]:
    """Assert that a response was successful and return JSON data.

    Args:
        response: The HTTP response to validate.
        expected_status: The expected HTTP status code.

    Returns:
        dict: The response JSON data.

    Raises:
        AssertionError: If response status doesn't match expected.
    """
    assert response.status_code == expected_status, (
        f"Expected status {expected_status}, got {response.status_code}. Response: {response.text}"
    )
    return response.json()


# ============================================================================
# API Health Tests
# ============================================================================


@pytest.mark.asyncio
class TestApiHealth:
    """Tests for API health endpoints.

        These tests verify that the basic health endpoints are responding
    correctly and returning expected response structures.
    """

    async def test_basic_health_endpoint_returns_healthy_status(
        self,
        http_client: httpx.AsyncClient,
        base_url: str,
    ) -> None:
        """Verify /health endpoint returns 200 with 'healthy' status.

        This is the most basic health check that should work even if
        database or external services are unavailable.

        Expected Response:
            {
                "status": "healthy",
                "version": "x.x.x"
            }
        """
        url = get_full_url(base_url, "/health")
        response = await http_client.get(url)

        data = await assert_successful_response(response, 200)
        assert data["status"] == "healthy", "Health status should be 'healthy'"
        assert "version" in data, "Response should include version"

    async def test_detailed_health_endpoint_returns_component_status(
        self,
        http_client: httpx.AsyncClient,
        base_url: str,
    ) -> None:
        """Verify /health/detailed endpoint returns detailed component status.

        This endpoint provides detailed health information about:
        - Database connectivity
        - Scheduler status
        - Azure configuration

        Expected Response:
            {
                "status": "healthy",
                "components": {
                    "database": {...},
                    "scheduler": {...},
                    "azure_config": {...}
                }
            }
        """
        url = get_full_url(base_url, "/health/detailed")
        response = await http_client.get(url)

        data = await assert_successful_response(response, 200)
        assert "status" in data, "Response should include status"
        assert "components" in data, "Response should include components"
        assert isinstance(data["components"], dict), "Components should be a dict"

    @pytest.mark.skip(reason="Prometheus metrics endpoint not yet implemented")
    async def test_metrics_endpoint_returns_prometheus_metrics(
        self,
        http_client: httpx.AsyncClient,
        base_url: str,
    ) -> None:
        """Verify /metrics endpoint returns Prometheus-format metrics.

        The metrics endpoint should return Prometheus exposition format
        metrics for monitoring and alerting.

        Expected Response:
            Prometheus text format with metrics like:
            - http_requests_total
            - http_request_duration_seconds
            - process_cpu_seconds_total
        """
        url = get_full_url(base_url, "/metrics")
        response = await http_client.get(url)

        assert response.status_code == 200, "Metrics endpoint should return 200"
        content_type = response.headers.get("content-type", "")
        assert "text/plain" in content_type, "Metrics should be text/plain format"
        assert len(response.text) > 0, "Metrics should contain data"

        # Verify some standard Prometheus metrics are present
        content = response.text
        assert "# HELP" in content or "# TYPE" in content, (
            "Metrics should include Prometheus HELP/TYPE annotations"
        )


# ============================================================================
# Azure Connectivity Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.azure_creds_required
class TestAzureConnectivity:
    """Tests for Azure connectivity and API access.

    These tests verify that the application can successfully connect to
    Azure APIs and retrieve data. They require Azure credentials to be
    configured and will be skipped if credentials are not available.
    """

    async def test_preflight_status_endpoint_returns_azure_api_status(
        self,
        authenticated_client: httpx.AsyncClient,
        base_url: str,
        azure_credentials_configured: bool,
    ) -> None:
        """Verify /api/v1/preflight/status returns Azure API connectivity status.

        This endpoint tests actual Azure API connectivity by checking:
        - Azure AD authentication
        - Graph API access
        - Resource provider access

        Skipped if Azure credentials are not configured.

        Expected Response:
            {
                "latest_report": {...},
                "last_run_at": "2024-...",
                "is_running": false
            }
        """
        if not azure_credentials_configured:
            pytest.skip("Azure credentials not configured")

        url = get_full_url(base_url, "/api/v1/preflight/status")
        response = await authenticated_client.get(url)

        data = await assert_successful_response(response, 200)
        assert "latest_report" in data, "Response should include latest_report"
        assert "last_run_at" in data, "Response should include last_run_at"
        assert "is_running" in data, "Response should include is_running flag"

    async def test_riverside_summary_endpoint_returns_data(
        self,
        authenticated_client: httpx.AsyncClient,
        base_url: str,
        azure_credentials_configured: bool,
    ) -> None:
        """Verify /api/v1/riverside/summary returns Riverside data access.

        This endpoint tests the Riverside service can access tenant data
        and compile summary statistics.

        Skipped if Azure credentials are not configured.

        Expected Response:
            {
                "total_critical_gaps": 0,
                "mfa_status": {...},
                "maturity_scores": {...}
            }
        """
        if not azure_credentials_configured:
            pytest.skip("Azure credentials not configured")

        url = get_full_url(base_url, "/api/v1/riverside/summary")
        response = await authenticated_client.get(url)

        data = await assert_successful_response(response, 200)
        assert isinstance(data, dict), "Response should be a dictionary"

    async def test_sync_status_endpoint_returns_scheduler_jobs(
        self,
        authenticated_client: httpx.AsyncClient,
        base_url: str,
        azure_credentials_configured: bool,
    ) -> None:
        """Verify /api/v1/sync/status returns scheduler job status.

        This endpoint tests the scheduler is properly initialized and
        can report scheduled jobs.

        Skipped if Azure credentials are not configured.

        Expected Response:
            {
                "status": "running",
                "jobs": [
                    {"id": "...", "name": "...", "next_run": "..."}
                ]
            }
        """
        if not azure_credentials_configured:
            pytest.skip("Azure credentials not configured")

        url = get_full_url(base_url, "/api/v1/sync/status")
        response = await authenticated_client.get(url)

        data = await assert_successful_response(response, 200)
        assert "status" in data, "Response should include status"
        assert "jobs" in data, "Response should include jobs list"
        assert isinstance(data["jobs"], list), "Jobs should be a list"


# ============================================================================
# Authentication/Authorization Tests
# ============================================================================


@pytest.mark.asyncio
class TestAuthentication:
    """Tests for authentication and authorization.

    These tests verify that:
    - Public endpoints are accessible without authentication
    - Protected endpoints require valid authentication
    - Invalid or missing tokens are rejected appropriately
    """

    async def test_public_health_endpoint_accessible_without_auth(
        self,
        http_client: httpx.AsyncClient,
        base_url: str,
    ) -> None:
        """Verify /health endpoint is accessible without authentication.

        Health endpoints should be publicly accessible for load balancer
        health checks and monitoring systems.
        """
        url = get_full_url(base_url, "/health")
        response = await http_client.get(url)

        assert response.status_code == 200, "Health endpoint should be public"

    async def test_public_auth_health_endpoint_accessible_without_auth(
        self,
        http_client: httpx.AsyncClient,
        base_url: str,
    ) -> None:
        """Verify /api/v1/auth/health endpoint is publicly accessible.

        Auth health status should be available without authentication
        for diagnostic purposes.
        """
        url = get_full_url(base_url, "/api/v1/auth/health")
        response = await http_client.get(url)

        assert response.status_code == 200, "Auth health should be public"
        data = response.json()
        assert "jwt_configured" in data, "Should include JWT config status"

    async def test_public_docs_endpoint_accessible_without_auth(
        self,
        http_client: httpx.AsyncClient,
        base_url: str,
    ) -> None:
        """Verify /docs endpoint is accessible without authentication.

        API documentation should be publicly accessible.
        """
        url = get_full_url(base_url, "/docs")
        response = await http_client.get(url)

        assert response.status_code == 200, "API docs should be public"

    async def test_protected_riverside_endpoints_require_auth(
        self,
        http_client: httpx.AsyncClient,
        base_url: str,
    ) -> None:
        """Verify /api/v1/riverside/* endpoints require authentication.

        Riverside data endpoints should reject requests without valid
        authentication tokens.

        Expected Response:
            401 Unauthorized when no token is provided.
        """
        url = get_full_url(base_url, "/api/v1/riverside/summary")
        response = await http_client.get(url)

        assert response.status_code == 401, "Riverside endpoints should require authentication"

    @pytest.mark.skip(reason="Preflight router not yet mounted in main app")
    async def test_protected_preflight_endpoints_require_auth(
        self,
        http_client: httpx.AsyncClient,
        base_url: str,
    ) -> None:
        """Verify /api/v1/preflight/* endpoints require authentication.

        Preflight check endpoints should reject unauthenticated requests.

        Expected Response:
            401 Unauthorized when no token is provided.
        """
        url = get_full_url(base_url, "/api/v1/preflight/status")
        response = await http_client.get(url)

        assert response.status_code == 401, "Preflight endpoints should require authentication"

    async def test_protected_sync_endpoints_require_auth(
        self,
        http_client: httpx.AsyncClient,
        base_url: str,
    ) -> None:
        """Verify /api/v1/sync/* endpoints require authentication.

        Sync management endpoints should reject unauthenticated requests.

        Expected Response:
            401 Unauthorized when no token is provided.
        """
        url = get_full_url(base_url, "/api/v1/sync/status")
        response = await http_client.get(url)

        assert response.status_code == 401, "Sync endpoints should require authentication"

    async def test_invalid_token_rejected_with_401(
        self,
        http_client: httpx.AsyncClient,
        base_url: str,
    ) -> None:
        """Verify invalid tokens are rejected with 401 Unauthorized.

        Requests with malformed or invalid tokens should be rejected.

        Expected Response:
            401 Unauthorized with WWW-Authenticate header.
        """
        url = get_full_url(base_url, "/api/v1/riverside/summary")
        headers = {"Authorization": "Bearer invalid-token"}
        response = await http_client.get(url, headers=headers)

        assert response.status_code == 401, "Invalid tokens should be rejected with 401"
        assert "WWW-Authenticate" in response.headers, (
            "Response should include WWW-Authenticate header"
        )


# ============================================================================
# Riverside-Specific Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.auth_required
class TestRiversideEndpoints:
    """Tests for Riverside-specific endpoints.

        These tests verify the Riverside compliance tracking endpoints
        are functioning correctly. They require authentication and
    can optionally test with Azure credentials for full data access.
    """

    async def test_riverside_mfa_status_endpoint_returns_tracking_data(
        self,
        authenticated_client: httpx.AsyncClient,
        base_url: str,
    ) -> None:
        """Verify /api/v1/riverside/mfa-status returns MFA tracking data.

        This endpoint should return MFA adoption status across tenants
        including coverage percentages and user counts.

        Expected Response:
            {
                "tenants": [...],
                "summary": {...}
            }
        """
        url = get_full_url(base_url, "/api/v1/riverside/mfa-status")
        response = await authenticated_client.get(url)

        data = await assert_successful_response(response, 200)
        assert isinstance(data, dict), "Response should be a dictionary"

    async def test_riverside_maturity_scores_endpoint_returns_scores(
        self,
        authenticated_client: httpx.AsyncClient,
        base_url: str,
    ) -> None:
        """Verify /api/v1/riverside/maturity-scores returns maturity scores.

        This endpoint should return maturity scores for security domains
        including IAM, Governance, and Data Security.

        Expected Response:
            {
                "domains": [...],
                "overall_score": 85
            }
        """
        url = get_full_url(base_url, "/api/v1/riverside/maturity-scores")
        response = await authenticated_client.get(url)

        data = await assert_successful_response(response, 200)
        assert isinstance(data, dict), "Response should be a dictionary"

    async def test_riverside_compliance_gaps_endpoint_returns_gaps(
        self,
        authenticated_client: httpx.AsyncClient,
        base_url: str,
    ) -> None:
        """Verify /api/v1/riverside/gaps returns compliance gaps.

        This endpoint should return identified compliance gaps
        with severity levels and remediation guidance.

        Expected Response:
            {
                "gaps": [...],
                "critical_count": 0,
                "total_count": 5
            }
        """
        url = get_full_url(base_url, "/api/v1/riverside/gaps")
        response = await authenticated_client.get(url)

        data = await assert_successful_response(response, 200)
        assert isinstance(data, dict), "Response should be a dictionary"

    async def test_riverside_requirements_endpoint_returns_requirements(
        self,
        authenticated_client: httpx.AsyncClient,
        base_url: str,
    ) -> None:
        """Verify /api/v1/riverside/requirements returns requirements list.

        This endpoint should return Riverside compliance requirements
        with filtering support.

        Expected Response:
            {
                "requirements": [...],
                "total": 50
            }
        """
        url = get_full_url(base_url, "/api/v1/riverside/requirements")
        response = await authenticated_client.get(url)

        data = await assert_successful_response(response, 200)
        assert isinstance(data, dict), "Response should be a dictionary"


# ============================================================================
# Smoke Test Summary
# ============================================================================


@pytest.mark.asyncio
async def test_smoke_suite_summary(
    base_url: str,
) -> None:
    """Verify smoke test suite can connect to the API.

    This test serves as a quick connectivity check before running
    the full smoke test suite.

    Args:
        base_url: The base URL of the API server.

    Raises:
        pytest.fail: If unable to connect to the API.
    """
    import httpx

    url = get_full_url(base_url, "/health")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.ConnectError as exc:
        pytest.fail(f"Could not connect to API at {base_url}: {exc}")
    except httpx.HTTPStatusError as exc:
        pytest.fail(f"API returned error: {exc}")
    except Exception as exc:
        pytest.fail(f"Unexpected error connecting to API: {exc}")
