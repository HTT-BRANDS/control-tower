#!/usr/bin/env python3
"""Standalone smoke test script for Azure Governance Platform.

This script provides a quick way to verify the deployment status
of the Azure Governance Platform without requiring pytest.

Usage:
    # Run with default settings (localhost:8000)
    python scripts/smoke_test.py

    # Run against specific URL
    python scripts/smoke_test.py --url https://api.example.com

    # Run with verbose output
    python scripts/smoke_test.py --verbose

    # Skip Azure connectivity tests
    python scripts/smoke_test.py --skip-azure

    # Run with authentication
    python scripts/smoke_test.py --username test@example.com --password test

Exit Codes:
    0 - All tests passed
    1 - One or more tests failed
    2 - Configuration error

Example Output:
    $ python scripts/smoke_test.py
    🔄 Smoke testing Azure Governance Platform at http://localhost:8000

    ✅ Public Health Endpoint       PASSED  (0.123s)
    ✅ Detailed Health Endpoint     PASSED  (0.089s)
    ✅ Metrics Endpoint             PASSED  (0.234s)
    ⏭️  Azure Connectivity          SKIPPED (no credentials)
    ⏭️  Riverside Endpoints         SKIPPED (no auth)

    Results: 3 passed, 0 failed, 2 skipped
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

# Try to import httpx
try:
    import httpx
except ImportError:
    print("❌ Error: httpx is required. Install with: uv add httpx")
    sys.exit(2)


# ============================================================================
# Data Classes and Enums
# ============================================================================


class TestStatus(Enum):
    """Test result status."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TestResult:
    """Result of a single test."""

    name: str
    status: TestStatus
    duration: float = 0.0
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class SmokeTestReport:
    """Complete smoke test report."""

    url: str
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    results: list[TestResult] = field(default_factory=list)

    def add_result(self, result: TestResult) -> None:
        """Add a test result to the report."""
        self.results.append(result)

    @property
    def passed_count(self) -> int:
        """Number of passed tests."""
        return sum(1 for r in self.results if r.status == TestStatus.PASSED)

    @property
    def failed_count(self) -> int:
        """Number of failed tests."""
        return sum(1 for r in self.results if r.status == TestStatus.FAILED)

    @property
    def skipped_count(self) -> int:
        """Number of skipped tests."""
        return sum(1 for r in self.results if r.status == TestStatus.SKIPPED)

    @property
    def total_duration(self) -> float:
        """Total test duration."""
        if self.end_time == 0:
            return time.time() - self.start_time
        return self.end_time - self.start_time

    def print_summary(self, verbose: bool = False) -> None:
        """Print test summary."""
        print(f"\n{'=' * 60}")
        print("SMOKE TEST RESULTS")
        print(f"{'=' * 60}")
        print(f"Target URL: {self.url}")
        print(f"Total Duration: {self.total_duration:.3f}s")
        print(
            f"\nResults: {self.passed_count} passed, {self.failed_count} failed, {self.skipped_count} skipped"
        )

        if self.failed_count > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.results:
                if result.status == TestStatus.FAILED:
                    print(f"  • {result.name}: {result.message}")

        if verbose:
            print("\n📋 ALL RESULTS:")
            for result in self.results:
                icon = (
                    "✅"
                    if result.status == TestStatus.PASSED
                    else "❌"
                    if result.status == TestStatus.FAILED
                    else "⏭️"
                )
                print(f"  {icon} {result.name}: {result.status.value} ({result.duration:.3f}s)")
                if result.details and verbose:
                    for key, value in result.details.items():
                        print(f"      {key}: {value}")

        print(f"{'=' * 60}")
        if self.failed_count == 0:
            print("✅ All smoke tests passed!")
        else:
            print(f"❌ {self.failed_count} test(s) failed")


# ============================================================================
# Test Functions
# ============================================================================


class SmokeTester:
    """Smoke test runner."""

    def __init__(
        self,
        base_url: str,
        verbose: bool = False,
        skip_azure: bool = False,
        username: str | None = None,
        password: str | None = None,
    ):
        """Initialize smoke tester.

        Args:
            base_url: Base URL of the API.
            verbose: Enable verbose output.
            skip_azure: Skip Azure connectivity tests.
            username: Username for authentication.
            password: Password for authentication.
        """
        self.base_url = base_url.rstrip("/")
        self.verbose = verbose
        self.skip_azure = skip_azure
        self.username = username
        self.password = password
        self.access_token: str | None = None
        self.report = SmokeTestReport(url=base_url)

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> tuple[int, dict[str, Any] | str, float]:
        """Make HTTP request and return status, data, and duration.

        Args:
            method: HTTP method.
            endpoint: API endpoint.
            **kwargs: Additional arguments for httpx.

        Returns:
            Tuple of (status_code, response_data_or_text, duration_seconds).
        """
        url = urljoin(self.base_url + "/", endpoint)
        start = time.time()

        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), follow_redirects=True) as client:
            try:
                response = await client.request(method, url, **kwargs)
                duration = time.time() - start

                try:
                    data = response.json()
                except Exception:
                    data = response.text

                return response.status_code, data, duration
            except httpx.ConnectError as exc:
                duration = time.time() - start
                return 0, f"Connection error: {exc}", duration
            except httpx.TimeoutException as exc:
                duration = time.time() - start
                return 0, f"Timeout: {exc}", duration
            except Exception as exc:
                duration = time.time() - start
                return 0, str(exc), duration

    async def _authenticate(self) -> bool:
        """Attempt to authenticate and get access token.

        Returns:
            True if authentication successful.
        """
        if not self.username or not self.password:
            return False

        status, data, _ = await self._make_request(
            "POST",
            "/api/v1/auth/login",
            data={"username": self.username, "password": self.password},
        )

        if status == 200 and isinstance(data, dict):
            self.access_token = data.get("access_token")
            return bool(self.access_token)

        return False

    def _auth_headers(self) -> dict[str, str]:
        """Get authentication headers."""
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}

    def _run_test(
        self,
        name: str,
        test_func: Callable[[], Coroutine[Any, Any, TestResult]],
    ) -> TestResult:
        """Run a single test and handle exceptions.

        Args:
            name: Test name.
            test_func: Async test function.

        Returns:
            TestResult.
        """
        try:
            return asyncio.run(test_func())
        except Exception as exc:
            return TestResult(
                name=name,
                status=TestStatus.FAILED,
                message=f"Exception: {exc}",
            )

    # -------------------------------------------------------------------------
    # Health Tests
    # -------------------------------------------------------------------------

    async def test_basic_health(self) -> TestResult:
        """Test basic health endpoint."""
        name = "Public Health Endpoint"
        start = time.time()

        status, data, _ = await self._make_request("GET", "/health")
        duration = time.time() - start

        if status == 0:
            return TestResult(
                name=name,
                status=TestStatus.FAILED,
                duration=duration,
                message="Could not connect to API",
            )

        if status != 200:
            return TestResult(
                name=name,
                status=TestStatus.FAILED,
                duration=duration,
                message=f"Expected 200, got {status}",
            )

        if isinstance(data, dict):
            if data.get("status") != "healthy":
                return TestResult(
                    name=name,
                    status=TestStatus.FAILED,
                    duration=duration,
                    message=f"Unexpected status: {data.get('status')}",
                    details=data,
                )
            return TestResult(
                name=name,
                status=TestStatus.PASSED,
                duration=duration,
                message="Health endpoint responded correctly",
                details=data,
            )

        return TestResult(
            name=name,
            status=TestStatus.FAILED,
            duration=duration,
            message="Response was not JSON",
        )

    async def test_detailed_health(self) -> TestResult:
        """Test detailed health endpoint."""
        name = "Detailed Health Endpoint"
        start = time.time()

        status, data, _ = await self._make_request("GET", "/health/detailed")
        duration = time.time() - start

        if status != 200:
            return TestResult(
                name=name,
                status=TestStatus.FAILED,
                duration=duration,
                message=f"Expected 200, got {status}",
            )

        if isinstance(data, dict) and "components" in data:
            return TestResult(
                name=name,
                status=TestStatus.PASSED,
                duration=duration,
                message="Detailed health endpoint responded correctly",
                details={
                    "status": data.get("status"),
                    "components": list(data.get("components", {}).keys()),
                },
            )

        return TestResult(
            name=name,
            status=TestStatus.FAILED,
            duration=duration,
            message="Response missing 'components'",
        )

    async def test_metrics(self) -> TestResult:
        """Test metrics endpoint."""
        name = "Metrics Endpoint"
        start = time.time()

        status, data, _ = await self._make_request("GET", "/metrics")
        duration = time.time() - start

        if status != 200:
            return TestResult(
                name=name,
                status=TestStatus.FAILED,
                duration=duration,
                message=f"Expected 200, got {status}",
            )

        if isinstance(data, str) and len(data) > 0:
            return TestResult(
                name=name,
                status=TestStatus.PASSED,
                duration=duration,
                message="Metrics endpoint returned data",
                details={"content_length": len(data)},
            )

        return TestResult(
            name=name,
            status=TestStatus.FAILED,
            duration=duration,
            message="Metrics endpoint returned empty response",
        )

    async def test_auth_health(self) -> TestResult:
        """Test auth health endpoint."""
        name = "Auth Health Endpoint"
        start = time.time()

        status, data, _ = await self._make_request("GET", "/api/v1/auth/health")
        duration = time.time() - start

        if status != 200:
            return TestResult(
                name=name,
                status=TestStatus.FAILED,
                duration=duration,
                message=f"Expected 200, got {status}",
            )

        if isinstance(data, dict) and "jwt_configured" in data:
            return TestResult(
                name=name,
                status=TestStatus.PASSED,
                duration=duration,
                message="Auth health endpoint responded correctly",
                details={
                    "jwt_configured": data.get("jwt_configured"),
                    "azure_ad_configured": data.get("azure_ad_configured"),
                },
            )

        return TestResult(
            name=name,
            status=TestStatus.FAILED,
            duration=duration,
            message="Response missing expected fields",
        )

    async def test_api_docs(self) -> TestResult:
        """Test API docs endpoint."""
        name = "API Docs Endpoint"
        start = time.time()

        status, data, _ = await self._make_request("GET", "/docs")
        duration = time.time() - start

        if status != 200:
            return TestResult(
                name=name,
                status=TestStatus.FAILED,
                duration=duration,
                message=f"Expected 200, got {status}",
            )

        return TestResult(
            name=name,
            status=TestStatus.PASSED,
            duration=duration,
            message="API docs endpoint is accessible",
        )

    # -------------------------------------------------------------------------
    # Authentication Tests
    # -------------------------------------------------------------------------

    async def test_protected_endpoints_require_auth(self) -> TestResult:
        """Test that protected endpoints require authentication."""
        name = "Protected Endpoints Require Auth"
        start = time.time()

        # Test a protected endpoint
        status, _, _ = await self._make_request("GET", "/api/v1/riverside/summary")
        duration = time.time() - start

        if status == 401:
            return TestResult(
                name=name,
                status=TestStatus.PASSED,
                duration=duration,
                message="Protected endpoint correctly rejects unauthenticated requests",
            )

        return TestResult(
            name=name,
            status=TestStatus.FAILED,
            duration=duration,
            message=f"Expected 401 for unauthenticated request, got {status}",
        )

    async def test_invalid_token_rejected(self) -> TestResult:
        """Test that invalid tokens are rejected."""
        name = "Invalid Token Rejected"
        start = time.time()

        status, _, _ = await self._make_request(
            "GET",
            "/api/v1/riverside/summary",
            headers={"Authorization": "Bearer invalid-token"},
        )
        duration = time.time() - start

        if status == 401:
            return TestResult(
                name=name,
                status=TestStatus.PASSED,
                duration=duration,
                message="Invalid token correctly rejected",
            )

        return TestResult(
            name=name,
            status=TestStatus.FAILED,
            duration=duration,
            message=f"Expected 401 for invalid token, got {status}",
        )

    # -------------------------------------------------------------------------
    # Azure Connectivity Tests (require auth + Azure creds)
    # -------------------------------------------------------------------------

    async def test_azure_preflight_status(self) -> TestResult:
        """Test Azure preflight status endpoint."""
        name = "Azure Preflight Status"
        start = time.time()

        status, data, _ = await self._make_request(
            "GET",
            "/api/v1/preflight/status",
            headers=self._auth_headers(),
        )
        duration = time.time() - start

        if status == 401 or status == 403:
            return TestResult(
                name=name,
                status=TestStatus.SKIPPED,
                duration=duration,
                message="Authentication required - skipping Azure test",
            )

        if status == 200 and isinstance(data, dict):
            return TestResult(
                name=name,
                status=TestStatus.PASSED,
                duration=duration,
                message="Preflight status endpoint accessible",
                details={"is_running": data.get("is_running")},
            )

        return TestResult(
            name=name,
            status=TestStatus.FAILED,
            duration=duration,
            message=f"Unexpected response: {status}",
        )

    async def test_riverside_summary(self) -> TestResult:
        """Test Riverside summary endpoint."""
        name = "Riverside Summary"
        start = time.time()

        status, data, _ = await self._make_request(
            "GET",
            "/api/v1/riverside/summary",
            headers=self._auth_headers(),
        )
        duration = time.time() - start

        if status == 401 or status == 403:
            return TestResult(
                name=name,
                status=TestStatus.SKIPPED,
                duration=duration,
                message="Authentication required",
            )

        if status == 200 and isinstance(data, dict):
            return TestResult(
                name=name,
                status=TestStatus.PASSED,
                duration=duration,
                message="Riverside summary endpoint accessible",
            )

        return TestResult(
            name=name,
            status=TestStatus.FAILED,
            duration=duration,
            message=f"Unexpected response: {status}",
        )

    async def test_sync_status(self) -> TestResult:
        """Test sync status endpoint."""
        name = "Sync Status"
        start = time.time()

        status, data, _ = await self._make_request(
            "GET",
            "/api/v1/sync/status",
            headers=self._auth_headers(),
        )
        duration = time.time() - start

        if status == 401 or status == 403:
            return TestResult(
                name=name,
                status=TestStatus.SKIPPED,
                duration=duration,
                message="Authentication required",
            )

        if status == 200 and isinstance(data, dict) and "jobs" in data:
            return TestResult(
                name=name,
                status=TestStatus.PASSED,
                duration=duration,
                message="Sync status endpoint accessible",
                details={"job_count": len(data.get("jobs", []))},
            )

        return TestResult(
            name=name,
            status=TestStatus.FAILED,
            duration=duration,
            message=f"Unexpected response: {status}",
        )

    # -------------------------------------------------------------------------
    # Riverside-Specific Tests (require auth)
    # -------------------------------------------------------------------------

    async def test_riverside_mfa_status(self) -> TestResult:
        """Test Riverside MFA status endpoint."""
        name = "Riverside MFA Status"
        start = time.time()

        status, data, _ = await self._make_request(
            "GET",
            "/api/v1/riverside/mfa-status",
            headers=self._auth_headers(),
        )
        duration = time.time() - start

        if status == 401 or status == 403:
            return TestResult(
                name=name,
                status=TestStatus.SKIPPED,
                duration=duration,
                message="Authentication required",
            )

        if status == 200 and isinstance(data, dict):
            return TestResult(
                name=name,
                status=TestStatus.PASSED,
                duration=duration,
                message="MFA status endpoint accessible",
            )

        return TestResult(
            name=name,
            status=TestStatus.FAILED,
            duration=duration,
            message=f"Unexpected response: {status}",
        )

    async def test_riverside_maturity_scores(self) -> TestResult:
        """Test Riverside maturity scores endpoint."""
        name = "Riverside Maturity Scores"
        start = time.time()

        status, data, _ = await self._make_request(
            "GET",
            "/api/v1/riverside/maturity-scores",
            headers=self._auth_headers(),
        )
        duration = time.time() - start

        if status == 401 or status == 403:
            return TestResult(
                name=name,
                status=TestStatus.SKIPPED,
                duration=duration,
                message="Authentication required",
            )

        if status == 200 and isinstance(data, dict):
            return TestResult(
                name=name,
                status=TestStatus.PASSED,
                duration=duration,
                message="Maturity scores endpoint accessible",
            )

        return TestResult(
            name=name,
            status=TestStatus.FAILED,
            duration=duration,
            message=f"Unexpected response: {status}",
        )

    async def test_riverside_gaps(self) -> TestResult:
        """Test Riverside compliance gaps endpoint."""
        name = "Riverside Compliance Gaps"
        start = time.time()

        status, data, _ = await self._make_request(
            "GET",
            "/api/v1/riverside/gaps",
            headers=self._auth_headers(),
        )
        duration = time.time() - start

        if status == 401 or status == 403:
            return TestResult(
                name=name,
                status=TestStatus.SKIPPED,
                duration=duration,
                message="Authentication required",
            )

        if status == 200 and isinstance(data, dict):
            return TestResult(
                name=name,
                status=TestStatus.PASSED,
                duration=duration,
                message="Compliance gaps endpoint accessible",
            )

        return TestResult(
            name=name,
            status=TestStatus.FAILED,
            duration=duration,
            message=f"Unexpected response: {status}",
        )

    # -------------------------------------------------------------------------
    # Main Test Runner
    # -------------------------------------------------------------------------

    async def run(self) -> SmokeTestReport:
        """Run all smoke tests and return report.

        Returns:
            SmokeTestReport with all test results.
        """
        print(f"🔄 Smoke testing Azure Governance Platform at {self.base_url}\n")

        # -------------------------------------------------------------------
        # API Health Tests (no auth required)
        # -------------------------------------------------------------------
        print("📊 Running API Health Tests...")
        self.report.add_result(await self.test_basic_health())
        self.report.add_result(await self.test_detailed_health())
        self.report.add_result(await self.test_metrics())
        self.report.add_result(await self.test_auth_health())
        self.report.add_result(await self.test_api_docs())

        # -------------------------------------------------------------------
        # Authentication Tests (no auth required)
        # -------------------------------------------------------------------
        print("🔐 Running Authentication Tests...")
        self.report.add_result(await self.test_protected_endpoints_require_auth())
        self.report.add_result(await self.test_invalid_token_rejected())

        # -------------------------------------------------------------------
        # Try to authenticate for protected tests
        # -------------------------------------------------------------------
        if self.username and self.password:
            print("🔑 Authenticating...")
            auth_success = await self._authenticate()
            if auth_success:
                print("✅ Authenticated successfully\n")
            else:
                print("⚠️ Authentication failed - skipping authenticated tests\n")
        else:
            print("ℹ️ No credentials provided - skipping authenticated tests\n")

        # -------------------------------------------------------------------
        # Azure Connectivity Tests (require auth + Azure creds)
        # -------------------------------------------------------------------
        if not self.skip_azure:
            print("☁️ Running Azure Connectivity Tests...")
            self.report.add_result(await self.test_azure_preflight_status())
            self.report.add_result(await self.test_riverside_summary())
            self.report.add_result(await self.test_sync_status())

            print("🏢 Running Riverside-Specific Tests...")
            self.report.add_result(await self.test_riverside_mfa_status())
            self.report.add_result(await self.test_riverside_maturity_scores())
            self.report.add_result(await self.test_riverside_gaps())
        else:
            print("⏭️ Skipping Azure Connectivity Tests (--skip-azure)")

        self.report.end_time = time.time()
        return self.report


# ============================================================================
# Main Entry Point
# ============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Smoke test script for Azure Governance Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/smoke_test.py
  python scripts/smoke_test.py --url https://api.example.com --verbose
  python scripts/smoke_test.py --username test@example.com --password test
  python scripts/smoke_test.py --skip-azure
        """,
    )

    parser.add_argument(
        "--url",
        default=os.environ.get("BASE_URL", "http://localhost:8000"),
        help="Base URL of the API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--skip-azure",
        action="store_true",
        help="Skip Azure connectivity tests",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("TEST_USERNAME"),
        help="Username for authentication",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("TEST_PASSWORD"),
        help="Password for authentication",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    args = parse_args()

    tester = SmokeTester(
        base_url=args.url,
        verbose=args.verbose,
        skip_azure=args.skip_azure,
        username=args.username,
        password=args.password,
    )

    try:
        report = asyncio.run(tester.run())
        report.print_summary(verbose=args.verbose)

        return 0 if report.failed_count == 0 else 1
    except KeyboardInterrupt:
        print("\n\n⚠️ Smoke tests interrupted by user")
        return 2
    except Exception as exc:
        print(f"\n❌ Smoke tests failed with error: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
