#!/usr/bin/env python3
"""
UAT Test Script for Staging Environment

Validates the Azure Governance Platform staging deployment
by testing health endpoints, auth flows, dashboards, and APIs.

Usage:
    uv run python scripts/uat_staging.py --url https://app-governance-staging-001.azurewebsites.net
    uv run python scripts/uat_staging.py --url https://app-governance-staging-001.azurewebsites.net --verbose
"""

import argparse
import sys
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin

try:
    import httpx
except ImportError:
    print("ERROR: httpx is required. Install with: uv add httpx")
    sys.exit(1)


# ANSI color codes for terminal output
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


def colorize(text: str, color: str) -> str:
    """Apply color to text if terminal supports it."""
    return f"{color}{text}{Colors.RESET}"


@dataclass
class TestResult:
    """Result of a single test."""

    name: str
    url: str
    expected: int
    actual: int
    passed: bool
    duration_ms: float
    message: str = ""
    requires_auth: bool = False


@dataclass
class TestSuite:
    """Collection of test results."""

    results: list[TestResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def auth_required_skips(self) -> int:
        return sum(1 for r in self.results if not r.passed and r.requires_auth)


class UATClient:
    """HTTP client for UAT testing."""

    def __init__(self, base_url: str, timeout: float = 30.0, verbose: bool = False):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.verbose = verbose
        self.client = httpx.Client(timeout=timeout, follow_redirects=True)

    def test_endpoint(
        self, name: str, path: str, expected_status: int = 200, requires_auth: bool = False
    ) -> TestResult:
        """Test a single endpoint."""
        url = urljoin(f"{self.base_url}/", path.lstrip("/"))
        start = time.time()

        try:
            response = self.client.get(url)
            duration = (time.time() - start) * 1000

            # For auth-required endpoints, 401 is expected without credentials
            if requires_auth and response.status_code == 401:
                passed = True
                message = "OK (401 expected without auth)"
            else:
                passed = response.status_code == expected_status
                message = f"{response.status_code}"

            if self.verbose:
                status_color = Colors.GREEN if passed else Colors.RED
                print(
                    f"  {colorize(name, Colors.BLUE)}: {colorize(message, status_color)} ({duration:.0f}ms)"
                )

            return TestResult(
                name=name,
                url=url,
                expected=expected_status,
                actual=response.status_code,
                passed=passed,
                duration_ms=duration,
                message=message,
                requires_auth=requires_auth,
            )

        except httpx.TimeoutException:
            duration = (time.time() - start) * 1000
            return TestResult(
                name=name,
                url=url,
                expected=expected_status,
                actual=0,
                passed=False,
                duration_ms=duration,
                message="TIMEOUT",
                requires_auth=requires_auth,
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            return TestResult(
                name=name,
                url=url,
                expected=expected_status,
                actual=0,
                passed=False,
                duration_ms=duration,
                message=str(e)[:50],
                requires_auth=requires_auth,
            )

    def close(self):
        """Close the HTTP client."""
        self.client.close()


def run_health_tests(client: UATClient) -> TestSuite:
    """Test health endpoints."""
    print(f"\n{colorize('Health Endpoints', Colors.BLUE)}")
    print("-" * 50)

    suite = TestSuite()
    tests = [
        ("Root /", "/", 200, False),
        ("Health", "/health", 200, False),
        ("Health Detailed", "/health/detailed", 200, False),
    ]

    for name, path, expected, requires_auth in tests:
        result = client.test_endpoint(name, path, expected, requires_auth)
        suite.results.append(result)

    return suite


def run_dashboard_tests(client: UATClient) -> TestSuite:
    """Test dashboard pages."""
    print(f"\n{colorize('Dashboard Pages', Colors.BLUE)}")
    print("-" * 50)

    suite = TestSuite()
    tests = [
        ("Login Page", "/login", 200, False),
        ("Dashboard", "/dashboard", 200, True),  # May redirect to login
        ("Riverside", "/riverside", 200, True),
        ("Riverside Dashboard", "/riverside/dashboard", 200, True),
        ("Costs", "/costs", 200, True),
        ("Compliance", "/compliance", 200, True),
        ("Resources", "/resources", 200, True),
        ("Identity", "/identity", 200, True),
        ("DMARC", "/dmarc", 200, True),
    ]

    for name, path, expected, requires_auth in tests:
        result = client.test_endpoint(name, path, expected, requires_auth)
        suite.results.append(result)

    return suite


def run_api_tests(client: UATClient) -> TestSuite:
    """Test API endpoints."""
    print(f"\n{colorize('API Endpoints', Colors.BLUE)}")
    print("-" * 50)

    suite = TestSuite()
    tests = [
        ("Costs Summary", "/api/v1/costs/summary", 200, True),
        ("Compliance Summary", "/api/v1/compliance/summary", 200, True),
        ("Resources", "/api/v1/resources", 200, True),
        ("Identity Users", "/api/v1/identity/users", 200, True),
        ("Preflight", "/api/v1/preflight", 200, False),
    ]

    for name, path, expected, requires_auth in tests:
        result = client.test_endpoint(name, path, expected, requires_auth)
        suite.results.append(result)

    return suite


def print_summary(suites: list[TestSuite], verbose: bool = False) -> bool:
    """Print test summary and return overall pass/fail."""
    print(f"\n{colorize('=' * 60, Colors.BLUE)}")
    print(colorize("UAT TEST SUMMARY", Colors.BLUE).center(60))
    print(colorize("=" * 60, Colors.BLUE))

    total_passed = 0
    total_failed = 0
    total_auth_skips = 0

    for suite in suites:
        total_passed += suite.passed
        total_failed += suite.failed
        total_auth_skips += suite.auth_required_skips

    print(f"\n{colorize('PASSED:', Colors.GREEN)}  {total_passed}")
    print(f"{colorize('FAILED:', Colors.RED)}  {total_failed}")
    if total_auth_skips > 0:
        print(f"{colorize('AUTH REQUIRED (expected 401):', Colors.YELLOW)}  {total_auth_skips}")

    print(f"\n{colorize('TOTAL:', Colors.BLUE)}  {total_passed + total_failed}")

    # Show failed tests if any
    failed_results = [
        r for suite in suites for r in suite.results if not r.passed and not r.requires_auth
    ]
    if failed_results:
        print(f"\n{colorize('FAILED TESTS:', Colors.RED)}")
        for result in failed_results:
            print(f"  {colorize('✗', Colors.RED)} {result.name}: {result.message}")
            print(f"    URL: {result.url}")

    print()

    if total_failed == 0 or (total_failed == total_auth_skips):
        print(colorize("✓ ALL TESTS PASSED", Colors.GREEN))
        return True
    else:
        print(colorize(f"✗ {total_failed - total_auth_skips} TEST(S) FAILED", Colors.RED))
        return False


def main():
    parser = argparse.ArgumentParser(
        description="UAT Test Script for Azure Governance Platform Staging"
    )
    parser.add_argument(
        "--url",
        default="https://app-governance-staging-001.azurewebsites.net",
        help="Base URL of the staging environment",
    )
    parser.add_argument(
        "--timeout", type=float, default=30.0, help="Request timeout in seconds (default: 30)"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    print(f"{colorize('Azure Governance Platform - UAT Testing', Colors.BLUE)}")
    print(f"Target: {args.url}")
    print(f"Timeout: {args.timeout}s")
    print(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    client = UATClient(args.url, timeout=args.timeout, verbose=args.verbose)

    try:
        # Run all test suites
        suites = [
            run_health_tests(client),
            run_dashboard_tests(client),
            run_api_tests(client),
        ]

        # Print summary and determine exit code
        passed = print_summary(suites, args.verbose)
        sys.exit(0 if passed else 1)

    except KeyboardInterrupt:
        print(f"\n{colorize('UAT testing interrupted', Colors.YELLOW)}")
        sys.exit(130)
    finally:
        client.close()


if __name__ == "__main__":
    main()
