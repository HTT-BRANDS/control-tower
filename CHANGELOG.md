# Changelog

All notable changes to the Azure Governance Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Automated remediation suggestions for cost anomalies
- Azure Policy compliance reporting enhancements
- Machine learning-based cost forecasting
- Multi-factor authentication for platform access
- Riverside School District integration modules

---

## [0.1.1] - 2025-07-21

### Added
- **Dev Environment Deployment**
  - Azure App Service deployment with Docker containers
  - Azure Container Registry (ACR) integration
  - PostgreSQL database connectivity
  - In-memory caching with metrics tracking
  - Comprehensive health check endpoints
  - Detailed health reporting with component status

- **Infrastructure**
  - Complete Azure infrastructure in `rg-governance-dev` resource group
  - Container-based deployment with `governance-platform:dev` image
  - App Service running Linux Docker containers
  - Health monitoring with `/health` and `/health/detailed` endpoints

### Changed
- Updated STATUS_REPORT.md with live deployment metrics
- Verified all 98 unit tests passing at 100%
- Confirmed database connectivity to PostgreSQL
- Validated container startup and runtime performance

### Deployment Details
**Resource Group:** `rg-governance-dev`  
**Location:** Canada Central  
**Status:** ✅ Fully Operational

| Component | Resource Name | Status |
|-----------|---------------|--------|
| Web App | `app-governance-dev-001` | 🟢 Running |
| App Service Plan | `plan-governance-dev` | 🟢 Active |
| Container Registry | `acrgov10188` | 🟢 Available |
| Key Vault | `kv-governance-dev-001` | 🟢 Available |
| VNet | `vnet-governance-dev` | 🟢 Configured |
| Storage | `stgovdev001` | 🟢 Ready |

**Access URLs:**
- Dashboard: `https://app-governance-dev-001.azurewebsites.net`
- Health: `https://app-governance-dev-001.azurewebsites.net/health`
- Detailed Health: `https://app-governance-dev-001.azurewebsites.net/health/detailed`

**Health Check Results:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "components": {
    "database": "healthy",
    "scheduler": "running",
    "cache": "memory",
    "azure_configured": false
  },
  "cache_metrics": {
    "backend": "memory",
    "hits": 0,
    "misses": 0,
    "sets": 0,
    "deletes": 0,
    "errors": 0,
    "hit_rate_percent": 0.0,
    "avg_get_time_ms": 0.0
  }
}
```

---

## [0.1.0] - 2025-02-25

### Added
- **Core Platform**
  - FastAPI-based REST API with automatic OpenAPI documentation
  - HTMX-powered dashboard with real-time updates
  - SQLAlchemy ORM with SQLite database
  - APScheduler for background job management
  - Comprehensive error handling and logging

- **Cost Management**
  - Cross-tenant cost aggregation and visibility
  - Cost anomaly detection with configurable thresholds
  - Daily cost trends and forecasting
  - Cost breakdown by tenant, service, and resource
  - Anomaly acknowledgment workflow
  - Bulk anomaly operations

- **Compliance Monitoring**
  - Azure Policy compliance tracking
  - Secure score aggregation across tenants
  - Non-compliant policy reporting
  - Compliance trends over time
  - Drift detection for compliance scores

- **Resource Management**
  - Cross-tenant resource inventory
  - Resource tagging compliance reporting
  - Orphaned resource detection
  - Idle resource identification (low CPU, no connections)
  - Resource review workflow
  - Bulk tagging operations

- **Identity Governance**
  - Privileged account reporting
  - Guest user management
  - MFA compliance tracking
  - Stale account detection
  - Identity trends analysis

- **Sync Management**
  - Automated background sync for costs (24h), compliance (4h), resources (1h), identity (24h)
  - Manual sync triggering via API
  - Sync job monitoring and alerting
  - Sync failure handling with retry logic
  - Comprehensive sync metrics and history

- **Preflight Checks**
  - Azure connectivity validation
  - Permission verification
  - Tenant accessibility checks
  - GitHub Actions integration
  - Detailed reporting in JSON and Markdown

- **Riverside Compliance**
  - Specialized dashboard for Riverside Company requirements
  - MFA enrollment tracking
  - Maturity score monitoring
  - Requirements compliance tracking
  - Critical gaps analysis
  - Deadline countdown (July 8, 2026)

- **Bulk Operations**
  - Bulk tag application/removal
  - Bulk anomaly acknowledgment
  - Bulk recommendation dismissal
  - Bulk idle resource review

- **Data Exports**
  - CSV export for costs
  - CSV export for resources
  - CSV export for compliance data

- **Performance & Monitoring**
  - In-memory caching with metrics
  - Circuit breaker pattern for resilience
  - Query performance monitoring
  - Sync job performance tracking
  - Health check endpoints

- **Documentation**
  - Complete API reference
  - Deployment guide
  - Operations runbook
  - Developer guide
  - Implementation guide
  - Common pitfalls guide

### Technical Details

#### Dependencies
- FastAPI 0.109.0+
- SQLAlchemy 2.0.0+
- Pydantic 2.5.0+
- APScheduler 3.10.0+
- Azure SDKs (Identity, Resource, Cost Management, Policy Insights, Security)
- MSGraph SDK 1.55.0+

#### Architecture
- Layered architecture (API → Services → Models)
- Repository pattern for data access
- Service layer for business logic
- Background job processing with APScheduler
- Caching layer for performance

#### Testing
- pytest for testing framework
- Unit tests for services
- Integration tests for sync jobs
- Test fixtures for mock data

### Known Issues
- SQLite database can lock with concurrent access (mitigated with WAL mode)
- Cost data has 24-48 hour delay from Azure
- Large tenants may require pagination optimization

---

## Version History

| Version | Date | Status |
|---------|------|--------|
| 0.1.0 | 2025-02-25 | Current Release |

---

## Contributing to Changelog

When making changes:

1. Add new entries under `[Unreleased]`
2. Use categories: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`
3. Include issue/PR references when applicable
4. Keep entries concise but descriptive

Example:
```markdown
### Added
- New feature description (#123)

### Fixed
- Bug fix description (#124)
```
