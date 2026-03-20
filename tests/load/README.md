# Load Tests — Azure Governance Platform

Validates **NF-P03** (50+ concurrent users) and **NF-P02** (API response < 500ms cached).

## Quick Start

```bash
# Start the app
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# Run load test (headless, CI-friendly)
uv run locust -f tests/load/locustfile.py \
    --host http://localhost:8000 \
    --headless \
    --users 50 \
    --spawn-rate 10 \
    --run-time 60s
```

## SLA Thresholds

| Metric | Threshold | Requirement |
|--------|-----------|-------------|
| Median response time (p50) | < 500ms | NF-P02 |
| P95 response time | < 2000ms | NF-P02 (cold cache) |
| Error rate | < 5% | NF-A01 |
| Concurrent users | 50+ | NF-P03 |

## Traffic Distribution

Simulates realistic user behavior:

| Category | Weight | Endpoints |
|----------|--------|-----------|
| Health | 10% | /health, /metrics |
| Cost Management | 30% | summary, trends, anomalies |
| Compliance | 25% | summary, frameworks |
| Resources | 20% | inventory, quotas |
| Identity | 10% | summary |
| Recommendations | 5% | recommendations |
