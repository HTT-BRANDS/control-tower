"""Load tests for Azure Governance Platform (NF-P03).

Validates that the platform can handle 50+ concurrent users
with API response times under 500ms (cached).

Usage:
    # Interactive mode (opens web UI at http://localhost:8089)
    uv run locust -f tests/load/locustfile.py --host http://localhost:8000

    # Headless mode (CI-friendly)
    uv run locust -f tests/load/locustfile.py \
        --host http://localhost:8000 \
        --headless \
        --users 60 \
        --spawn-rate 10 \
        --run-time 60s \
        --csv tests/load/results

    # Quick smoke (30 seconds, 50 users)
    uv run locust -f tests/load/locustfile.py \
        --host http://localhost:8000 \
        --headless \
        --users 50 \
        --spawn-rate 10 \
        --run-time 30s

Traces: NF-P03 (Support 50+ concurrent users)
"""

import os

from locust import HttpUser, between, events, task


class GovernanceAPIUser(HttpUser):
    """Simulates a typical governance platform user.

    Mixes read-heavy API calls that reflect real usage patterns:
    - Health check (lightweight, frequent)
    - Cost endpoints (dashboard-heavy)
    - Compliance endpoints (regular checks)
    - Resource endpoints (inventory browsing)
    - Identity endpoints (occasional lookups)
    """

    # Wait between 1-3 seconds between tasks (realistic user behavior)
    wait_time = between(1, 3)

    def on_start(self):
        """Authenticate and store token for subsequent requests."""
        # Use staging token endpoint if available, otherwise skip auth
        staging_token_url = "/api/v1/auth/staging-token"
        try:
            resp = self.client.post(
                staging_token_url,
                json={"purpose": "load-test"},
                timeout=10,
            )
            if resp.status_code == 200:
                token = resp.json().get("access_token", "")
                self.client.headers.update({"Authorization": f"Bearer {token}"})
                return
        except Exception:
            pass

        # Fallback: use env var token
        token = os.environ.get("LOAD_TEST_TOKEN", "")
        if token:
            self.client.headers.update({"Authorization": f"Bearer {token}"})

    # ---- Health (10% of traffic) ----

    @task(2)
    def health_check(self):
        """GET /health — lightweight liveness probe."""
        self.client.get("/health", name="/health")

    @task(1)
    def metrics(self):
        """GET /metrics — Prometheus metrics endpoint."""
        self.client.get("/metrics", name="/metrics")

    # ---- Cost Management (30% of traffic) ----

    @task(4)
    def cost_summary(self):
        """GET /api/v1/costs/summary — main dashboard widget."""
        self.client.get("/api/v1/costs/summary", name="/api/v1/costs/summary")

    @task(3)
    def cost_trends(self):
        """GET /api/v1/costs/trends — cost trending chart."""
        self.client.get("/api/v1/costs/trends", name="/api/v1/costs/trends")

    @task(2)
    def cost_anomalies(self):
        """GET /api/v1/costs/anomalies — anomaly detection."""
        self.client.get("/api/v1/costs/anomalies", name="/api/v1/costs/anomalies")

    # ---- Compliance (25% of traffic) ----

    @task(3)
    def compliance_summary(self):
        """GET /api/v1/compliance/summary — compliance dashboard."""
        self.client.get(
            "/api/v1/compliance/summary", name="/api/v1/compliance/summary"
        )

    @task(2)
    def compliance_frameworks(self):
        """GET /api/v1/compliance/frameworks — framework listing."""
        self.client.get(
            "/api/v1/compliance/frameworks", name="/api/v1/compliance/frameworks"
        )

    # ---- Resources (20% of traffic) ----

    @task(3)
    def resource_inventory(self):
        """GET /api/v1/resources/inventory — resource listing."""
        self.client.get(
            "/api/v1/resources/inventory", name="/api/v1/resources/inventory"
        )

    @task(1)
    def resource_quotas(self):
        """GET /api/v1/resources/quotas/summary — quota monitoring."""
        self.client.get(
            "/api/v1/resources/quotas/summary",
            name="/api/v1/resources/quotas/summary",
        )

    # ---- Identity (10% of traffic) ----

    @task(2)
    def identity_summary(self):
        """GET /api/v1/identity/summary — identity dashboard."""
        self.client.get(
            "/api/v1/identity/summary", name="/api/v1/identity/summary"
        )

    # ---- Recommendations (5% of traffic) ----

    @task(1)
    def recommendations(self):
        """GET /api/v1/recommendations — optimization suggestions."""
        self.client.get(
            "/api/v1/recommendations", name="/api/v1/recommendations"
        )


# ---- Event Hooks for CI Assertions ----


@events.quitting.add_listener
def assert_response_times(environment, **_kwargs):
    """Fail the load test if response times exceed SLA thresholds.

    NF-P02: API response time < 500ms (cached)
    NF-P03: Support 50+ concurrent users
    """
    stats = environment.stats
    total = stats.total

    if total.num_requests == 0:
        environment.process_exit_code = 1
        print("❌ LOAD TEST FAILED: No requests were made")
        return

    p50 = total.get_response_time_percentile(0.5)
    p95 = total.get_response_time_percentile(0.95)
    error_rate = (total.num_failures / total.num_requests) * 100 if total.num_requests > 0 else 0

    # Check median response time (p50 < 500ms)
    if p50 and p50 > 500:
        environment.process_exit_code = 1
        print(f"❌ LOAD TEST FAILED: Median response time {p50:.0f}ms > 500ms SLA")
        return

    # Check 95th percentile (p95 < 2000ms — allows for cold cache)
    if p95 and p95 > 2000:
        environment.process_exit_code = 1
        print(f"❌ LOAD TEST FAILED: P95 response time {p95:.0f}ms > 2000ms SLA")
        return

    # Check error rate (< 5%)
    if error_rate > 5:
        environment.process_exit_code = 1
        print(f"❌ LOAD TEST FAILED: Error rate {error_rate:.1f}% > 5% threshold")
        return

    print(
        f"✅ LOAD TEST PASSED: {total.num_requests} requests, "
        f"p50={p50:.0f}ms, p95={p95:.0f}ms, errors={error_rate:.1f}%"
    )
