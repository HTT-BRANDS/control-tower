# Monitoring Stack Audit — Current Dependencies

## Installed Packages (from pyproject.toml)

### Active / In Use
| Package | Version | Purpose | Status |
|---------|---------|---------|--------|
| `app/core/app_insights.py` | Custom | Request duration logging middleware | ✅ Active |
| `app/core/monitoring.py` | Custom | SyncJobMetrics, QueryMetrics, cache metrics | ✅ Active |

### Installed But Not Active
| Package | Version | Purpose | Status |
|---------|---------|---------|--------|
| `prometheus-fastapi-instrumentator` | >=7.1.0 | FastAPI Prometheus `/metrics` endpoint | ⚠️ Endpoint exposed, no scraper |
| `opentelemetry-api` | >=1.40.0 | OTel API | ⚠️ Imported but ENABLE_TRACING=false |
| `opentelemetry-sdk` | >=1.40.0 | OTel SDK | ⚠️ Disabled by default |
| `opentelemetry-instrumentation-fastapi` | >=0.61b0 | Auto-instrument FastAPI | ⚠️ Disabled by default |
| `opentelemetry-exporter-otlp` | >=1.40.0 | OTLP exporter | ⚠️ No endpoint configured |

### Optional (import-guarded)
| Package | Version | Purpose | Status |
|---------|---------|---------|--------|
| `opencensus-ext-azure` | Optional | Azure App Insights exporter | ⚠️ Guarded by try/except ImportError |

## Azure Monitor Pricing (relevant tiers for this scale)

### Log Analytics (Analytics Logs)
- Pay-As-You-Go: $2.30/GB ingested
- Free tier: 5 GB/month per billing account
- Retention: 31 days free (analytics logs), up to 730 days paid ($0.10/GB/month)

### Application Insights
- Ingestion: Billed through Log Analytics
- Free allowance: 5 GB/month (shared with Log Analytics)
- Classic pricing: $2.30/GB (still available for pre-2018 resources)

### Prometheus Managed Service (Azure Monitor Workspace)
- Ingestion: $0.16 per 10 million samples
- Queries: $0.001 per 10 million samples processed
- Retention: 18 months included

### Estimated Monthly Monitoring Costs for This Platform

| Component | Estimated Data Volume | Cost |
|-----------|---------------------|------|
| Log Analytics (App Service logs) | ~0.5-1 GB/mo | $0 (within 5GB free tier) |
| App Insights (request telemetry) | ~0.2-0.5 GB/mo | $0 (within 5GB free tier) |
| Prometheus (if deployed) | ~100k samples/mo | $0.0016/mo |
| Platform metrics | Unlimited | Free |
| **Total** | | **~$0/mo** |

## Redundancy Map

```
HTTP Request
  │
  ├── AppInsightsMiddleware → structured log line (method, path, status, duration)
  │     └── If opencensus installed: Azure App Insights exporter
  │
  ├── Prometheus instrumentator → /metrics endpoint (histograms, counters)
  │     └── No scraper deployed → data goes nowhere
  │
  ├── OpenTelemetry → OTLP exporter (spans, traces)
  │     └── ENABLE_TRACING=false → disabled at runtime
  │
  └── PerformanceMonitor → in-memory metrics (sync jobs, queries, cache)
        └── Exposed via /api/v1/monitoring/dashboard
```

## Transitive Dependency Count

```
prometheus-fastapi-instrumentator: ~8 transitive deps
opentelemetry-api:                 ~5 transitive deps
opentelemetry-sdk:                 ~12 transitive deps
opentelemetry-instrumentation-fastapi: ~6 transitive deps
opentelemetry-exporter-otlp:       ~15 transitive deps
─────────────────────────────────────────────────────
Total unnecessary transitive deps:  ~46 packages
Estimated Docker image savings:     ~50 MB
```
