# Riverside Preflight Checks

This document describes the Riverside-specific preflight checks implemented for validating the Riverside Company compliance tracking system.

## Overview

The Riverside preflight checks ensure that all components required for Riverside compliance tracking are properly configured and operational before attempting data synchronization or reporting.

## Checks Implemented

### 1. RiversideDatabaseCheck
**Check ID:** `riverside_database_connectivity`

Validates connectivity to all Riverside database tables:
- `riverside_compliance` - Main compliance tracking table
- `riverside_mfa` - MFA enrollment tracking table
- `riverside_requirements` - Individual requirement tracking table

**Severity Levels:**
- **Critical:** If any table is inaccessible (database migration issue)
- **Info:** If all tables are accessible

**Returns:**
- Table accessibility status for each table
- Record counts per table
- Recent data availability (when tenant_id provided)

---

### 2. RiversideAPIEndpointCheck
**Check ID:** `riverside_api_endpoints`

Tests availability of all Riverside API endpoints:
- `GET /api/v1/riverside/summary` - Executive summary
- `GET /api/v1/riverside/mfa-status` - MFA status
- `GET /api/v1/riverside/maturity-scores` - Maturity scores
- `GET /api/v1/riverside/requirements` - Requirements list
- `GET /api/v1/riverside/gaps` - Critical gaps analysis

**Severity Levels:**
- **Critical:** If no endpoints are accessible
- **Warning:** If some endpoints are accessible but others fail
- **Info:** If all endpoints are accessible

**Returns:**
- Endpoint accessibility status
- HTTP status codes
- Response times

---

### 3. RiversideSchedulerCheck
**Check ID:** `riverside_scheduler`

Verifies that the Riverside sync job is properly registered in the background scheduler:
- Checks scheduler is initialized
- Verifies `sync_riverside` job exists
- Confirms scheduler is running
- Validates job configuration (interval: 4 hours)

**Severity Levels:**
- **Critical:** If Riverside job is not registered
- **Warning:** If scheduler not initialized or not running
- **Info:** If job registered and scheduler running

**Returns:**
- Job registration status
- Job details (ID, name, trigger, next run time)
- Scheduler running status
- Total number of registered jobs

---

### 4. RiversideAzureADPermissionsCheck
**Check ID:** `riverside_azure_ad_permissions`

Validates Azure AD permissions required for Riverside data access:
- `User.Read.All` - Read user data
- `Group.Read.All` - Read group information
- `Directory.Read.All` - Read directory data
- `AuditLog.Read.All` - Read audit logs
- `Reports.Read.All` - Read reports

**Severity Levels:**
- **Critical:** If no permissions are granted
- **Warning:** If partial permissions (some but not all)
- **Info:** If all required permissions are granted

**Returns:**
- Permission test results for each required permission
- Tenant ID being checked
- Recommendations for granting missing permissions

---

### 5. RiversideMFADataSourceCheck
**Check ID:** `riverside_mfa_data_source`

Tests connectivity to MFA data sources via Microsoft Graph API:
- User endpoint accessibility
- Authentication methods endpoint (optional, requires `UserAuthenticationMethod.Read.All`)

**Severity Levels:**
- **Critical:** If user data cannot be retrieved
- **Warning:** If user data accessible but authentication methods limited
- **Info:** If full MFA data source connectivity available

**Returns:**
- Data source accessibility status
- User count from test query
- Authentication methods count (if available)

---

## Usage

### Running Individual Checks

```python
from app.preflight.riverside_checks import (
    RiversideDatabaseCheck,
    RiversideAPIEndpointCheck,
)

# Run single check
check = RiversideDatabaseCheck()
result = await check.run(tenant_id="12345678-1234-1234-1234-123456789012")

print(f"Status: {result.status}")
print(f"Message: {result.message}")
print(f"Details: {result.details}")
```

### Running All Riverside Checks

```python
from app.preflight.riverside_checks import run_all_riverside_checks

# Run all Riverside checks
results = await run_all_riverside_checks()

for result in results:
    print(f"{result.name}: {result.status}")
```

### Using with PreflightRunner

```python
from app.preflight.runner import PreflightRunner
from app.preflight.models import CheckCategory

# Run all checks including Riverside
runner = PreflightRunner(categories=[CheckCategory.RIVERSIDE])
report = await runner.run_checks()

# Get Riverside-specific results
riverside_results = report.get_results_by_category(CheckCategory.RIVERSIDE)
```

### Using Convenience Functions

```python
from app.preflight import (
    check_riverside_database,
    check_riverside_api_endpoints,
    check_riverside_scheduler,
    check_riverside_azure_ad_permissions,
    check_riverside_mfa_data_source,
)

# Run specific checks
result = await check_riverside_database(tenant_id="...")
result = await check_riverside_api_endpoints()
result = await check_riverside_scheduler()
result = await check_riverside_azure_ad_permissions(tenant_id="...")
result = await check_riverside_mfa_data_source(tenant_id="...")
```

---

## Integration Instructions

### 1. Automatic Registration

Riverside checks are automatically registered with the preflight system through the `get_all_checks()` function in `app/preflight/checks.py`.

### 2. Category Integration

The `RIVERSIDE` category has been added to `CheckCategory` enum in `app/preflight/models.py`:

```python
class CheckCategory(str, Enum):
    # ... other categories ...
    RIVERSIDE = "riverside"
```

### 3. Runner Integration

The `PreflightRunner` in `app/preflight/runner.py` has been updated to:
- Include `RIVERSIDE` in tenant-specific check categories
- Add "Riverside Compliance" display name for category summaries

### 4. Module Exports

All Riverside checks are exported from `app/preflight/__init__.py`:

```python
from app.preflight import (
    # Class-based checks
    RiversideDatabaseCheck,
    RiversideAPIEndpointCheck,
    RiversideSchedulerCheck,
    RiversideAzureADPermissionsCheck,
    RiversideMFADataSourceCheck,
    # Function-based API
    check_riverside_database,
    check_riverside_api_endpoints,
    check_riverside_scheduler,
    check_riverside_azure_ad_permissions,
    check_riverside_mfa_data_source,
    run_all_riverside_checks,
    get_riverside_checks,
)
```

---

## Check Result Structure

All Riverside checks return a `CheckResult` with the following structure:

```python
{
    "check_id": str,           # Unique identifier
    "name": str,               # Human-readable name
    "category": "riverside",   # Check category
    "status": CheckStatus,     # pass, warning, fail, skipped
    "message": str,            # Human-readable result message
    "details": {
        "severity": str,       # critical, warning, or info
        # ... check-specific details ...
    },
    "duration_ms": float,      # Execution time
    "timestamp": datetime,     # When check was run
    "recommendations": [str],  # Fix recommendations
    "tenant_id": str | None,   # Optional tenant ID
}
```

---

## Severity Levels

| Level | Description | When Used |
|-------|-------------|-----------|
| `critical` | System cannot function without this | Database inaccessible, no Azure AD permissions |
| `warning` | System can function but with limitations | Partial permissions, scheduler not running |
| `info` | Everything is working correctly | All checks pass |

---

## Troubleshooting

### Database Connectivity Failures

**Symptoms:** Check fails with database connection errors

**Recommendations:**
1. Verify database migrations: `alembic upgrade head`
2. Check database file permissions
3. Verify disk space availability
4. Review SQLAlchemy model definitions

### API Endpoint Failures

**Symptoms:** Endpoints return 500 errors or are unreachable

**Recommendations:**
1. Verify application is running
2. Check FastAPI route registration
3. Review reverse proxy configuration
4. Check authentication middleware settings

### Scheduler Not Found

**Symptoms:** `Riverside sync job not found in scheduler`

**Recommendations:**
1. Verify `init_scheduler()` is called at startup
2. Check `app/core/scheduler.py` for Riverside job registration
3. Ensure APScheduler is installed: `pip install apscheduler`
4. Check job ID matches `sync_riverside`

### Azure AD Permission Denied

**Symptoms:** 403 Forbidden or permission errors

**Recommendations:**
1. Navigate to Azure Portal > App Registrations
2. Add required API permissions
3. Click "Grant admin consent for [Tenant]"
4. Wait 5-10 minutes for propagation

### MFA Data Source Unavailable

**Symptoms:** Cannot retrieve user MFA status

**Recommendations:**
1. Verify Azure AD authentication is configured
2. Check service principal credentials
3. Ensure User.Read.All permission is granted
4. Review Graph API client configuration

---

## Testing

Run the Riverside preflight tests:

```bash
# Run all Riverside preflight tests
pytest tests/unit/test_riverside_preflight.py -v

# Run with coverage
pytest tests/unit/test_riverside_preflight.py --cov=app.preflight.riverside_checks
```

---

## Implementation Details

### File Structure

```
app/preflight/
├── __init__.py              # Module exports
├── models.py                # CheckCategory enum (updated)
├── base.py                  # BasePreflightCheck class
├── checks.py                # get_all_checks() (updated)
├── runner.py                # PreflightRunner (updated)
└── riverside_checks.py      # Riverside-specific checks (new)

tests/unit/
└── test_riverside_preflight.py  # Unit tests (new)

docs/
└── RIVERSIDE_PREFLIGHT_CHECKS.md  # This document
```

### Design Patterns

1. **Inheritance**: All checks inherit from `BasePreflightCheck`
2. **Caching**: Check results are cached using the base class cache mechanism
3. **Async**: All checks are async for non-blocking I/O
4. **Structured Results**: Consistent `CheckResult` format across all checks
5. **Severity Levels**: Three-tier severity system for prioritization
6. **Recommendations**: Each check provides actionable remediation steps

### Timeout Configuration

| Check | Timeout |
|-------|---------|
| Database | 15s |
| API Endpoints | 20s |
| Scheduler | 10s |
| Azure AD Permissions | 30s |
| MFA Data Source | 30s |

---

## Future Enhancements

Potential additions to Riverside preflight checks:

1. **Device Compliance Data Source Check** - Validate Intune/Endpoint Manager connectivity
2. **Riverside Sync Health Check** - Verify last sync was successful
3. **Riverside Data Quality Check** - Validate data integrity and freshness
4. **Riverside Deadline Alert Check** - Verify deadline tracking is configured
5. **Multi-Tenant Riverside Check** - Validate all Riverside tenants in one check
