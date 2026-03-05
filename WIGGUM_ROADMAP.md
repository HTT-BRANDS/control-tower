# 🔄 WIGGUM ROADMAP — Azure Governance Platform

> **Purpose**: Single source of truth for `/wiggum ralph` autonomous execution loop.
> The loop reads this file, picks the next `- [ ]` task, executes it, marks it `- [x]`, and continues until all tasks are complete.

---

## 📊 LOOP METADATA

```yaml
project: azure-governance-platform
version: 0.2.0
created: 2025-03-06
last_updated: 2026-03-05
loop_status: IN_PROGRESS  # NOT_STARTED | IN_PROGRESS | COMPLETED | BLOCKED
current_phase: 7
total_phases: 7
completed_tasks: 70
total_tasks: 89
stop_condition: "All checkboxes marked [x] AND all quality gates pass"
```

---

## 🏁 STOP CONDITION

The `/wiggum ralph` loop should call `/wiggum_stop` when ALL of the following are true:
1. Every `- [ ]` in this file is changed to `- [x]`
2. `uv run pytest tests/unit/ -q` exits 0 with 0 failures
3. `uv run pytest tests/integration/ -q` exits 0 with 0 failures
4. `uv run ruff check app/ tests/` exits 0
5. All changes are committed and pushed to remote

---

## 🔄 LOOP PROTOCOL (For /wiggum ralph)

> **Purpose**: Eliminate redundant re-verification by making the roadmap the single source of truth.

### Trust Model
- **TRUST** roadmap `[x]` markings - they are the source of truth
- **VERIFY** roadmap `[ ]` tasks by running their validation commands
- **NEVER** re-verify completed tasks unless discrepancy detected
- **ALWAYS** update roadmap immediately after task completion

### Before Each Task (Entry Point)
```bash
# Verify roadmap state and get next task
python scripts/sync_roadmap.py --verify --json
```

Expected output:
```json
{
  "status": "ok",
  "metadata": {
    "completed_tasks": 64,
    "total_tasks": 89,
    "completion_percentage": 71.9
  },
  "next_task": {
    "id": "6.2.1",
    "phase": 6,
    "title": "Run full security audit on auth...",
    "ready_to_execute": true
  }
}
```

### After Task Completion (Exit Point)
```bash
# 1. Run the task's validation command (must pass)
#    (Validation command is defined in the task itself)

# 2. Mark task complete in roadmap
python scripts/sync_roadmap.py --update --task 6.2.1 --reason "validation passed"

# 3. Commit the roadmap change IMMEDIATELY
git add WIGGUM_ROADMAP.md
git commit -m "ralph: complete task 6.2.1 - security audit"
git push
```

### Quick Commands
```bash
# Check current status (human readable)
python scripts/sync_roadmap.py --report

# Mark specific task complete
python scripts/sync_roadmap.py --update --task 7.1 --reason "fixed bicep template"

# Get JSON for programmatic use
python scripts/sync_roadmap.py --verify --json | jq '.next_task.id'
```

---

## ✅ PHASE 0: ALREADY COMPLETED (Pre-existing Work)

> These items are already done. Listed for context — DO NOT re-execute.

- [x] Core FastAPI application structure (`app/main.py`, routers, services)
- [x] SQLAlchemy models for all domains (cost, compliance, resource, identity, riverside, dmarc)
- [x] Azure SDK integration (Cost Management, Policy, Resource Manager, Graph API)
- [x] HTMX + Tailwind frontend with dashboards
- [x] OAuth2/JWT authentication framework (`app/core/auth.py`)
- [x] Tenant authorization framework (`app/core/authorization.py`)
- [x] Security audit — 5/5 findings fixed (C-1, C-2, H-1, H-2, H-3)
- [x] Security headers middleware (HSTS, CSP, X-Frame-Options, etc.)
- [x] Preflight check system with 24 checks
- [x] Riverside compliance dashboard (MFA tracking, maturity scores, deadline countdown)
- [x] Azure Lighthouse integration with LighthouseAzureClient
- [x] Data backfill service (resumable, parallel multi-tenant)
- [x] Sync modules: costs, compliance, resources, identity
- [x] Rate limiting middleware
- [x] Circuit breaker pattern
- [x] Cache system (Redis + in-memory fallback)
- [x] Notification system (email, Teams webhook)
- [x] Application Insights telemetry
- [x] Prometheus /metrics endpoint
- [x] Docker + docker-compose configuration
- [x] Bicep IaC (App Service, ACR, Key Vault, Storage, App Insights)
- [x] Dev environment deployed and healthy (app-governance-dev-001)
- [x] Key Vault references working for Azure credentials
- [x] CI/CD OIDC federation (passwordless GitHub → Azure)
- [x] Graph API preflight fix (60s timeout → 1s)
- [x] WCAG 2.2 AA accessibility
- [x] Dark mode with system preference detection
- [x] Alembic migration for backfill_job table
- [x] 741 unit tests passing (27 test files)
- [x] 47 E2E tests (Playwright + httpx)
- [x] 3 integration tests (health endpoints)
- [x] Unit tests: sync modules (compliance, costs, identity, resources)
- [x] Unit tests: Graph client (admin_roles, async_token, mfa)
- [x] Unit tests: Preflight checks (admin_risk, mfa, riverside)
- [x] Unit tests: Alerts (deadline, mfa)
- [x] Unit tests: Services (backfill, lighthouse, parallel_processor, riverside_sync, riverside_service, retention)
- [x] Unit tests: Core (rate_limit, notifications, tenants_config, app_insights)
- [x] Unit tests: Other (onboarding, tenants, brand_config, theme_service, health, version, riverside_scheduler, azure_ad_admin)

---

## 🔧 PHASE 1: CORE MODULE UNIT TESTS [Priority: P0]

> These core modules have zero unit test coverage. Each task creates a dedicated test file.

### 1.1 Authentication & Authorization Tests

- [x] **Task 1.1.1**: Create `tests/unit/test_auth.py` — Unit tests for `app/core/auth.py`
  - **Files**: `tests/unit/test_auth.py` (create), `app/core/auth.py` (read-only)
  - **Agent**: `code-puppy` (write tests), `python-reviewer` (review)
  - **Test Coverage Required**:
    - `TokenData` model creation and validation
    - `User` model role checking (`has_role`, `is_admin`, `has_tenant_access`)
    - `JWTTokenManager.create_access_token()` — valid token generation
    - `JWTTokenManager.create_refresh_token()` — refresh token with correct expiry
    - `JWTTokenManager.validate_token()` — valid token decode
    - `JWTTokenManager.validate_token()` — expired token raises error
    - `JWTTokenManager.validate_token()` — invalid signature raises error
    - `AzureADTokenValidator` — JWKS key caching
    - `get_current_user()` — extracts user from valid bearer token
    - `get_current_user()` — returns None/raises on missing token
    - `require_roles()` — allows matching role
    - `require_roles()` — rejects non-matching role (403)
  - **Minimum Tests**: 15
  - **Validation**: `uv run pytest tests/unit/test_auth.py -v`

- [x] **Task 1.1.2**: Create `tests/unit/test_authorization.py` — Unit tests for `app/core/authorization.py`
  - **Files**: `tests/unit/test_authorization.py` (create), `app/core/authorization.py` (read-only)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - `TenantAccessError` exception creation and message
    - `get_user_tenants()` — returns correct tenants for user
    - `get_user_tenants()` — admin gets all tenants
    - `get_user_tenant_ids()` — returns ID list
    - `validate_tenant_access()` — allows valid access
    - `validate_tenant_access()` — raises 403 for unauthorized
    - `validate_tenants_access()` — filters multiple tenants
    - `TenantAuthorization.filter_tenant_ids()` — filters correctly
    - `TenantAuthorization.ensure_at_least_one_tenant()` — raises when empty
    - `filter_query_by_tenants()` — SQLAlchemy query filtering
  - **Minimum Tests**: 12
  - **Validation**: `uv run pytest tests/unit/test_authorization.py -v`

### 1.2 Core Infrastructure Tests

- [x] **Task 1.2.1**: Create `tests/unit/test_cache.py` — Unit tests for `app/core/cache.py`
  - **Files**: `tests/unit/test_cache.py` (create), `app/core/cache.py` (read-only)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - `CacheMetrics` dataclass defaults
    - `CacheManager.get()` — cache miss returns None
    - `CacheManager.set()` / `get()` — cache hit returns stored value
    - `CacheManager.set()` with TTL — expired entry returns None
    - `CacheManager.delete()` — removes entry
    - `CacheManager.clear()` — empties all entries
    - `CacheManager.get_metrics()` — returns correct hit/miss counts
    - Cache decorator — caches function results
    - Cache decorator — respects TTL
    - Tenant-isolated cache keys don't collide
  - **Minimum Tests**: 12
  - **Validation**: `uv run pytest tests/unit/test_cache.py -v`

- [x] **Task 1.2.2**: Create `tests/unit/test_circuit_breaker.py` — Unit tests for `app/core/circuit_breaker.py`
  - **Files**: `tests/unit/test_circuit_breaker.py` (create), `app/core/circuit_breaker.py` (read-only)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - Circuit starts in CLOSED state
    - Transitions to OPEN after failure threshold
    - OPEN state rejects calls immediately
    - Transitions to HALF_OPEN after timeout
    - HALF_OPEN → CLOSED on success
    - HALF_OPEN → OPEN on failure
    - `circuit_breaker_registry.reset_all()` resets all breakers
    - Metrics tracking (success_count, failure_count)
  - **Minimum Tests**: 10
  - **Validation**: `uv run pytest tests/unit/test_circuit_breaker.py -v`

- [x] **Task 1.2.3**: Create `tests/unit/test_config.py` — Unit tests for `app/core/config.py`
  - **Files**: `tests/unit/test_config.py` (create), `app/core/config.py` (read-only)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - Settings loads with defaults
    - Settings validates environment values
    - `get_settings()` caching (singleton pattern)
    - JWT secret auto-generation when not set
    - Database URL construction
    - Azure AD endpoint derivation from tenant ID
  - **Minimum Tests**: 8
  - **Validation**: `uv run pytest tests/unit/test_config.py -v`

- [x] **Task 1.2.4**: Create `tests/unit/test_database.py` — Unit tests for `app/core/database.py`
  - **Files**: `tests/unit/test_database.py` (create), `app/core/database.py` (read-only)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - `init_db()` creates tables
    - `get_db()` yields a session
    - `SessionLocal` configuration (WAL mode for SQLite)
    - `Base` metadata is properly configured
  - **Minimum Tests**: 5
  - **Validation**: `uv run pytest tests/unit/test_database.py -v`

- [x] **Task 1.2.5**: Create `tests/unit/test_resilience.py` — Unit tests for `app/core/resilience.py`
  - **Files**: `tests/unit/test_resilience.py` (create), `app/core/resilience.py` (read-only)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - Retry decorator retries on failure
    - Retry decorator succeeds after transient failure
    - Retry decorator gives up after max retries
    - Exponential backoff timing
    - Fallback value returned on exhaustion
  - **Minimum Tests**: 8
  - **Validation**: `uv run pytest tests/unit/test_resilience.py -v`

- [x] **Task 1.2.6**: Create `tests/unit/test_retry.py` — Unit tests for `app/core/retry.py`
  - **Files**: `tests/unit/test_retry.py` (create), `app/core/retry.py` (read-only)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - `retry_with_backoff` decorator retries correct number of times
    - Respects max_retries parameter
    - Calculates backoff delay correctly
    - Handles success on retry
    - Raises final exception on exhaustion
  - **Minimum Tests**: 6
  - **Validation**: `uv run pytest tests/unit/test_retry.py -v`

- [x] **Task 1.2.7**: Create `tests/unit/test_monitoring.py` — Unit tests for `app/core/monitoring.py`
  - **Files**: `tests/unit/test_monitoring.py` (create), `app/core/monitoring.py` (read-only)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - Metrics collection and retrieval
    - Performance tracking helpers
    - Request timing middleware behavior
  - **Minimum Tests**: 6
  - **Validation**: `uv run pytest tests/unit/test_monitoring.py -v`

- [x] **Task 1.2.8**: Create `tests/unit/test_tenant_context.py` — Unit tests for `app/core/tenant_context.py`
  - **Files**: `tests/unit/test_tenant_context.py` (create), `app/core/tenant_context.py` (read-only)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - Template filter registration
    - Tenant context resolution
    - Brand config loading per tenant
  - **Minimum Tests**: 6
  - **Validation**: `uv run pytest tests/unit/test_tenant_context.py -v`

---

## 🔌 PHASE 2: API SERVICE UNIT TESTS [Priority: P0]

> All API service classes lack unit tests. These are the business logic layer.

- [x] **Task 2.1**: Create cost service unit tests — Unit tests for `app/api/services/cost_service.py`
  - **Files**: `tests/unit/test_cost_service_anomalies.py`, `tests/unit/test_cost_service_summaries.py` (split for maintainability)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - `CostService` initialization
    - `get_cost_summary()` — aggregates costs across tenants
    - `get_cost_trends()` — returns daily/weekly/monthly trends
    - `get_anomalies()` — filters by acknowledged status
    - `get_anomalies_by_service()` — groups correctly
    - `get_top_anomalies()` — returns top N by impact
    - `acknowledge_anomaly()` — updates status
    - `bulk_acknowledge()` — batch operation
    - `get_cost_forecast()` — linear projection
    - `get_cost_by_tenant()` — per-tenant breakdown
  - **Minimum Tests**: 12 (split across both files)
  - **Validation**: `uv run pytest tests/unit/test_cost_service_*.py -v`

- [x] **Task 2.2**: Create `tests/unit/test_compliance_service.py` — Unit tests for `app/api/services/compliance_service.py`
  - **Files**: `tests/unit/test_compliance_service.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - `ComplianceService` initialization
    - `get_compliance_summary()` — aggregates scores
    - `get_compliance_scores()` — per-policy scores
    - `get_non_compliant_resources()` — filters by severity
    - `get_compliance_trends()` — historical data
    - `get_secure_scores()` — Security Center integration
  - **Minimum Tests**: 8
  - **Validation**: `uv run pytest tests/unit/test_compliance_service.py -v`

- [x] **Task 2.3**: Create `tests/unit/test_resource_service.py` — Unit tests for `app/api/services/resource_service.py`
  - **Files**: `tests/unit/test_resource_service.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - `ResourceService` initialization
    - `get_resources()` — pagination and filtering
    - `get_orphaned_resources()` — detection logic
    - `get_idle_resources()` — idle type filtering
    - `get_idle_summary()` — aggregation
    - `get_tagging_compliance()` — tag audit
    - `mark_idle_reviewed()` — status update
  - **Minimum Tests**: 10
  - **Validation**: `uv run pytest tests/unit/test_resource_service.py -v`

- [x] **Task 2.4**: Create `tests/unit/test_identity_service.py` — Unit tests for `app/api/services/identity_service.py`
  - **Files**: `tests/unit/test_identity_service.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - `IdentityService` initialization
    - `get_identity_summary()` — user/guest/admin counts
    - `get_privileged_users()` — filters by risk level and MFA
    - `get_guest_users()` — stale detection
    - `get_stale_accounts()` — inactivity threshold
    - `get_identity_trends()` — MFA adoption over time
  - **Minimum Tests**: 8
  - **Validation**: `uv run pytest tests/unit/test_identity_service.py -v`

- [x] **Task 2.5**: Create `tests/unit/test_dmarc_service.py` — Unit tests for `app/api/services/dmarc_service.py`
  - **Files**: `tests/unit/test_dmarc_service.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - `DMARCService` initialization
    - DMARC record parsing
    - DKIM validation
    - SPF record analysis
    - Domain status aggregation
    - Report generation
  - **Minimum Tests**: 10
  - **Validation**: `uv run pytest tests/unit/test_dmarc_service.py -v`

- [x] **Task 2.6**: Create `tests/unit/test_bulk_service.py` — Unit tests for `app/api/services/bulk_service.py`
  - **Files**: `tests/unit/test_bulk_service.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - `BulkService` initialization
    - Bulk anomaly acknowledgement
    - Bulk recommendation dismissal
    - Bulk resource tagging
    - Error handling for partial failures
    - Validation of input IDs
  - **Minimum Tests**: 8
  - **Validation**: `uv run pytest tests/unit/test_bulk_service.py -v`

- [x] **Task 2.7**: Create `tests/unit/test_recommendation_service.py` — Unit tests for `app/api/services/recommendation_service.py`
  - **Files**: `tests/unit/test_recommendation_service.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - `RecommendationService` initialization
    - `get_recommendations()` — filtering by category, impact
    - `get_by_category()` — grouping
    - `get_by_tenant()` — tenant breakdown
    - `get_savings_potential()` — financial calculations
    - `dismiss_recommendation()` — status update
  - **Minimum Tests**: 8
  - **Validation**: `uv run pytest tests/unit/test_recommendation_service.py -v`

- [x] **Task 2.8**: Create `tests/unit/test_monitoring_service.py` — Unit tests for `app/api/services/monitoring_service.py`
  - **Files**: `tests/unit/test_monitoring_service.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - `MonitoringService` initialization
    - Alert creation and retrieval
    - Alert severity filtering
    - Alert acknowledgement
    - Sync job status tracking
    - Performance metrics aggregation
  - **Minimum Tests**: 8
  - **Validation**: `uv run pytest tests/unit/test_monitoring_service.py -v`

- [x] **Task 2.9**: Create `tests/unit/test_azure_client.py` — Unit tests for `app/api/services/azure_client.py`
  - **Files**: `tests/unit/test_azure_client.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - `AzureClientManager` initialization
    - Client creation per tenant
    - Credential management
    - Connection pooling behavior
    - Error handling for invalid tenant configs
  - **Minimum Tests**: 8
  - **Validation**: `uv run pytest tests/unit/test_azure_client.py -v`

- [x] **Task 2.10**: Create `tests/unit/test_riverside_analytics.py` — Unit tests for `app/api/services/riverside_analytics.py`
  - **Files**: `tests/unit/test_riverside_analytics.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - Analytics calculations (maturity scores, trends)
    - Financial risk quantification
    - Gap analysis
    - Progress tracking against deadline
  - **Minimum Tests**: 8
  - **Validation**: `uv run pytest tests/unit/test_riverside_analytics.py -v`

- [x] **Task 2.11**: Create `tests/unit/test_riverside_compliance_service.py` — Unit tests for `app/api/services/riverside_compliance.py`
  - **Files**: `tests/unit/test_riverside_compliance_service.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - Compliance status calculations
    - Requirement completion tracking
    - Evidence validation
    - Domain maturity scoring
  - **Minimum Tests**: 6
  - **Validation**: `uv run pytest tests/unit/test_riverside_compliance_service.py -v`

---

## 🛤️ PHASE 3: API ROUTE UNIT TESTS [Priority: P1]

> All 14 route files lack dedicated tests. Test request/response shapes, status codes, auth enforcement.

- [x] **Task 3.1**: Create `tests/unit/test_routes_auth.py` — Route tests for `app/api/routes/auth.py`
  - **Files**: `tests/unit/test_routes_auth.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - `POST /api/v1/auth/login` — valid credentials → 200 + token
    - `POST /api/v1/auth/login` — invalid credentials → 401
    - `POST /api/v1/auth/login` — production rejects direct login → 403
    - `POST /api/v1/auth/token` — authorization_code grant
    - `POST /api/v1/auth/token` — refresh_token grant
    - `POST /api/v1/auth/refresh` — valid refresh → new access token
    - `POST /api/v1/auth/refresh` — expired refresh → 401
    - `GET /api/v1/auth/me` — returns current user info
    - `GET /api/v1/auth/me` — unauthenticated → 401
    - `POST /api/v1/auth/logout` — invalidates token
    - `GET /api/v1/auth/health` — returns auth system health
  - **Minimum Tests**: 12
  - **Validation**: `uv run pytest tests/unit/test_routes_auth.py -v`

- [x] **Task 3.2**: Create `tests/unit/test_routes_costs.py` — Route tests for `app/api/routes/costs.py`
  - **Files**: `tests/unit/test_routes_costs.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - All GET endpoints return correct status codes
    - Authentication enforcement (401 without token)
    - Tenant filtering applied correctly
    - Pagination parameters respected
    - POST acknowledge/bulk-acknowledge operations
  - **Minimum Tests**: 10
  - **Validation**: `uv run pytest tests/unit/test_routes_costs.py -v`

- [x] **Task 3.3**: Create `tests/unit/test_routes_compliance.py` — Route tests for `app/api/routes/compliance.py`
  - **Files**: `tests/unit/test_routes_compliance.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Minimum Tests**: 8
  - **Validation**: `uv run pytest tests/unit/test_routes_compliance.py -v`

- [x] **Task 3.4**: Create `tests/unit/test_routes_resources.py` — Route tests for `app/api/routes/resources.py`
  - **Files**: `tests/unit/test_routes_resources.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Minimum Tests**: 10
  - **Validation**: `uv run pytest tests/unit/test_routes_resources.py -v`

- [x] **Task 3.5**: Create `tests/unit/test_routes_identity.py` — Route tests for `app/api/routes/identity.py`
  - **Files**: `tests/unit/test_routes_identity.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Minimum Tests**: 8
  - **Validation**: `uv run pytest tests/unit/test_routes_identity.py -v`

- [x] **Task 3.6**: Create `tests/unit/test_routes_riverside.py` — Route tests for `app/api/routes/riverside.py`
  - **Files**: `tests/unit/test_routes_riverside.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Minimum Tests**: 8
  - **Validation**: `uv run pytest tests/unit/test_routes_riverside.py -v`

- [x] **Task 3.7**: Create `tests/unit/test_routes_dmarc.py` — Route tests for `app/api/routes/dmarc.py`
  - **Files**: `tests/unit/test_routes_dmarc.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Minimum Tests**: 8
  - **Validation**: `uv run pytest tests/unit/test_routes_dmarc.py -v`

- [x] **Task 3.8**: Create `tests/unit/test_routes_sync.py` — Route tests for `app/api/routes/sync.py`
  - **Files**: `tests/unit/test_routes_sync.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Minimum Tests**: 8
  - **Validation**: `uv run pytest tests/unit/test_routes_sync.py -v`

- [x] **Task 3.9**: Create `tests/unit/test_routes_dashboard.py` — Route tests for `app/api/routes/dashboard.py`
  - **Files**: `tests/unit/test_routes_dashboard.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Minimum Tests**: 6
  - **Validation**: `uv run pytest tests/unit/test_routes_dashboard.py -v`

- [x] **Task 3.10**: Create `tests/unit/test_routes_exports.py` — Route tests for `app/api/routes/exports.py`
  - **Files**: `tests/unit/test_routes_exports.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Minimum Tests**: 6
  - **Validation**: `uv run pytest tests/unit/test_routes_exports.py -v`

- [x] **Task 3.11**: Create `tests/unit/test_routes_bulk.py` — Route tests for `app/api/routes/bulk.py`
  - **Files**: `tests/unit/test_routes_bulk.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Minimum Tests**: 6
  - **Validation**: `uv run pytest tests/unit/test_routes_bulk.py -v`

- [x] **Task 3.12**: Create `tests/unit/test_routes_recommendations.py` — Route tests for `app/api/routes/recommendations.py`
  - **Files**: `tests/unit/test_routes_recommendations.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Minimum Tests**: 6
  - **Validation**: `uv run pytest tests/unit/test_routes_recommendations.py -v`

- [x] **Task 3.13**: Create `tests/unit/test_routes_preflight.py` — Route tests for `app/api/routes/preflight.py`
  - **Files**: `tests/unit/test_routes_preflight.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Minimum Tests**: 6
  - **Validation**: `uv run pytest tests/unit/test_routes_preflight.py -v`

- [x] **Task 3.14**: Create `tests/unit/test_routes_monitoring.py` — Route tests for `app/api/routes/monitoring.py`
  - **Files**: `tests/unit/test_routes_monitoring.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Minimum Tests**: 4
  - **Validation**: `uv run pytest tests/unit/test_routes_monitoring.py -v`

---

## 🔗 PHASE 4: REMAINING MODULE TESTS [Priority: P1]

> Misc modules that need test coverage.

- [x] **Task 4.1**: Create `tests/unit/test_email_service.py` — Unit tests for `app/services/email_service.py`
  - **Files**: `tests/unit/test_email_service.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - `EmailService` initialization
    - Email composition (subject, body, recipients)
    - SMTP connection handling (mock)
    - Error handling for send failures
    - Template rendering for alert emails
  - **Minimum Tests**: 8
  - **Validation**: `uv run pytest tests/unit/test_email_service.py -v`

- [x] **Task 4.2**: Create `tests/unit/test_teams_webhook.py` — Unit tests for `app/services/teams_webhook.py`
  - **Files**: `tests/unit/test_teams_webhook.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - `TeamsWebhookClient` initialization
    - Message card construction
    - Webhook POST (mock httpx)
    - Retry on failure
    - Rate limit handling
  - **Minimum Tests**: 8
  - **Validation**: `uv run pytest tests/unit/test_teams_webhook.py -v`

- [x] **Task 4.3**: Create `tests/unit/test_preflight_runner.py` — Unit tests for `app/preflight/runner.py`
  - **Files**: `tests/unit/test_preflight_runner.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - Runner executes all registered checks
    - Check timeout enforcement
    - Result aggregation (pass/fail/warn/skip counts)
    - Parallel check execution
    - Report generation trigger
  - **Minimum Tests**: 8
  - **Validation**: `uv run pytest tests/unit/test_preflight_runner.py -v`

- [x] **Task 4.4**: Create `tests/unit/test_preflight_reports.py` — Unit tests for `app/preflight/reports.py`
  - **Files**: `tests/unit/test_preflight_reports.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - JSON report generation
    - Markdown report generation
    - Summary statistics calculation
    - Empty results handling
  - **Minimum Tests**: 6
  - **Validation**: `uv run pytest tests/unit/test_preflight_reports.py -v`

- [x] **Task 4.5**: Create `tests/unit/test_preflight_tenant_checks.py` — Unit tests for `app/preflight/tenant_checks.py`
  - **Files**: `tests/unit/test_preflight_tenant_checks.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Minimum Tests**: 6
  - **Validation**: `uv run pytest tests/unit/test_preflight_tenant_checks.py -v`

- [x] **Task 4.6**: Create `tests/unit/sync/test_riverside.py` — Unit tests for `app/core/sync/riverside.py`
  - **Files**: `tests/unit/sync/test_riverside.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Minimum Tests**: 6
  - **Validation**: `uv run pytest tests/unit/sync/test_riverside.py -v`

- [x] **Task 4.7**: Create `tests/unit/sync/test_dmarc.py` — Unit tests for `app/core/sync/dmarc.py`
  - **Files**: `tests/unit/sync/test_dmarc.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Minimum Tests**: 6
  - **Validation**: `uv run pytest tests/unit/sync/test_dmarc.py -v`

---

## 🧪 PHASE 5: INTEGRATION TESTS [Priority: P0]

> Currently only 1 integration test file exists. Need comprehensive API integration tests using FastAPI TestClient.

> ⚠️ **PRE-CHECK REQUIRED**: Before executing ANY Phase 5 task, run this verification FIRST:
> ```bash
> ls -la tests/integration/test_*.py 2>/dev/null | wc -l
> ```
> If result is >= 8, integration tests likely already exist. Proceed to "Skip Logic" below.

### Phase 5 Skip Logic
**BEFORE creating any file, verify existing content:**
1. Check if file exists: `test -f tests/integration/test_<name>.py`
2. Check if file has content: `wc -l tests/integration/test_<name>.py` should be >50
3. Check for test functions: `grep -cE "(^def test_|^    def test_|^async def test_)" tests/integration/test_<name>.py` should be >= 5
4. If ALL checks pass → Mark task `[x]` without recreation
5. If ANY check fails → Proceed with creation

### Task Completion Criteria
A task is considered complete if ANY of the following are true:
- File exists with >50 lines AND contains >= 5 test functions
- Task is already marked `[x]` in this document
- File was created in a previous loop iteration

---

- [x] **Task 5.1**: Create `tests/integration/test_cost_api.py` — Cost API integration tests
  
  **Pre-execution Verification** (run FIRST):
  ```bash
  if test -f tests/integration/test_cost_api.py && \
     [ $(wc -l < tests/integration/test_cost_api.py) -gt 50 ] && \
     [ $(grep -cE "(^def test_|^    def test_|^async def test_)" tests/integration/test_cost_api.py 2>/dev/null || echo "0") -ge 5 ]; then
    echo "SKIP: File already exists with content"
  fi
  ```
  - **Files**: `tests/integration/test_cost_api.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - Full request/response cycle with seeded database
    - GET /api/v1/costs/summary — returns aggregated data
    - GET /api/v1/costs/trends — returns trend data
    - GET /api/v1/costs/anomalies — pagination works
    - POST /api/v1/costs/anomalies/{id}/acknowledge — updates DB
    - GET /api/v1/exports/costs — returns CSV
    - Auth enforcement on all endpoints
  - **Minimum Tests**: 10
  - **Validation**: `uv run pytest tests/integration/test_cost_api.py -v`

- [x] **Task 5.2**: Create `tests/integration/test_compliance_api.py` — Compliance API integration tests
  
  **Pre-execution Verification** (run FIRST):
  ```bash
  if test -f tests/integration/test_compliance_api.py && \
     [ $(wc -l < tests/integration/test_compliance_api.py) -gt 50 ] && \
     [ $(grep -cE "(^def test_|^    def test_|^async def test_)" tests/integration/test_compliance_api.py 2>/dev/null || echo "0") -ge 5 ]; then
    echo "SKIP: File already exists with content"
  fi
  ```
  
  - **Files**: `tests/integration/test_compliance_api.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Minimum Tests**: 8
  - **Validation**: `uv run pytest tests/integration/test_compliance_api.py -v`

- [x] **Task 5.3**: Create `tests/integration/test_resource_api.py` — Resource API integration tests
  
  **Pre-execution Verification** (run FIRST):
  ```bash
  if test -f tests/integration/test_resource_api.py && \
     [ $(wc -l < tests/integration/test_resource_api.py) -gt 50 ] && \
     [ $(grep -cE "(^def test_|^    def test_|^async def test_)" tests/integration/test_resource_api.py 2>/dev/null || echo "0") -ge 5 ]; then
    echo "SKIP: File already exists with content"
  fi
  ```
  
  - **Files**: `tests/integration/test_resource_api.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Minimum Tests**: 8
  - **Validation**: `uv run pytest tests/integration/test_resource_api.py -v`

- [x] **Task 5.4**: Create `tests/integration/test_identity_api.py` — Identity API integration tests
  
  **Pre-execution Verification** (run FIRST):
  ```bash
  if test -f tests/integration/test_identity_api.py && \
     [ $(wc -l < tests/integration/test_identity_api.py) -gt 50 ] && \
     [ $(grep -cE "(^def test_|^    def test_|^async def test_)" tests/integration/test_identity_api.py 2>/dev/null || echo "0") -ge 5 ]; then
    echo "SKIP: File already exists with content"
  fi
  ```
  
  - **Files**: `tests/integration/test_identity_api.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Minimum Tests**: 8
  - **Validation**: `uv run pytest tests/integration/test_identity_api.py -v`

- [x] **Task 5.5**: Create `tests/integration/test_riverside_api.py` — Riverside API integration tests
  
  **Pre-execution Verification** (run FIRST):
  ```bash
  if test -f tests/integration/test_riverside_api.py && \
     [ $(wc -l < tests/integration/test_riverside_api.py) -gt 50 ] && \
     [ $(grep -cE "(^def test_|^    def test_|^async def test_)" tests/integration/test_riverside_api.py 2>/dev/null || echo "0") -ge 5 ]; then
    echo "SKIP: File already exists with content"
  fi
  ```
  
  - **Files**: `tests/integration/test_riverside_api.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Minimum Tests**: 10
  - **Validation**: `uv run pytest tests/integration/test_riverside_api.py -v`

- [x] **Task 5.6**: Create `tests/integration/auth_flow/` package — Auth flow integration tests
  
  **Pre-execution Verification** (run FIRST):
  ```bash
  if test -d tests/integration/auth_flow && \
     [ $(ls -1 tests/integration/auth_flow/test_*.py 2>/dev/null | wc -l) -ge 4 ]; then
    echo "SKIP: auth_flow/ package already exists with test files"
  fi
  ```
  
  - **Files**: `tests/integration/auth_flow/` package (create) containing:
    - `test_auth_endpoints.py` — Auth endpoint tests
    - `test_login.py` — Login flow tests
    - `test_logout.py` — Logout flow tests
    - `test_tenant_access.py` — Tenant access control tests
    - `test_token_refresh.py` — Token refresh flow tests
    - `test_token_validation.py` — Token validation tests
    - `conftest.py` — Shared fixtures for auth flow tests
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Test Coverage Required**:
    - Login → get token → access protected endpoint → success
    - Login → expired token → access protected endpoint → 401
    - Login → access wrong tenant → 403
    - Refresh token flow
    - Logout invalidation
  - **Minimum Tests**: 8
  - **Validation**: `uv run pytest tests/integration/auth_flow/ -v`

- [x] **Task 5.7**: Create `tests/integration/test_sync_api.py` — Sync API integration tests
  
  **Pre-execution Verification** (run FIRST):
  ```bash
  if test -f tests/integration/test_sync_api.py && \
     [ $(wc -l < tests/integration/test_sync_api.py) -gt 50 ] && \
     [ $(grep -cE "(^def test_|^    def test_|^async def test_)" tests/integration/test_sync_api.py 2>/dev/null || echo "0") -ge 5 ]; then
    echo "SKIP: File already exists with content"
  fi
  ```
  
  - **Files**: `tests/integration/test_sync_api.py` (create)
  - **Agent**: `code-puppy`, `python-reviewer`
  - **Minimum Tests**: 6
  - **Validation**: `uv run pytest tests/integration/test_sync_api.py -v`

- [x] **Task 5.8**: Create `tests/integration/test_tenant_isolation.py` — Tenant isolation integration tests
  
  **Pre-execution Verification** (run FIRST):
  ```bash
  if test -f tests/integration/test_tenant_isolation.py && \
     [ $(wc -l < tests/integration/test_tenant_isolation.py) -gt 50 ] && \
     [ $(grep -cE "(^def test_|^    def test_|^async def test_)" tests/integration/test_tenant_isolation.py 2>/dev/null || echo "0") -ge 5 ]; then
    echo "SKIP: File already exists with content"
  fi
  ```
  
  - **Files**: `tests/integration/test_tenant_isolation.py` (create)
  - **Agent**: `code-puppy`, `security-auditor`
  - **Test Coverage Required**:
    - User A cannot see User B's tenant data
    - Admin can see all tenants
    - Tenant filter injection prevention
    - Cross-tenant write prevention
  - **Minimum Tests**: 10
  - **Validation**: `uv run pytest tests/integration/test_tenant_isolation.py -v`

- [x] **Task 5.9**: Create `tests/integration/conftest.py` — Shared integration test fixtures
  
  **Pre-execution Verification** (run FIRST):
  ```bash
  if test -f tests/integration/conftest.py && \
     [ $(wc -l < tests/integration/conftest.py) -gt 50 ] && \
     [ $(grep -c "^def " tests/integration/conftest.py) -ge 4 ]; then
    echo "SKIP: File already exists with content"
  fi
  ```
  
  - **Files**: `tests/integration/conftest.py` (update)
  - **Agent**: `code-puppy`
  - **Required Fixtures**:
    - `authenticated_client` — TestClient with valid JWT
    - `admin_client` — TestClient with admin role
    - `seeded_db` — Database with realistic test data
    - `multi_tenant_users` — Users with different tenant access
  - **Validation**: `uv run pytest tests/integration/ -v`

---

## 🔍 PHASE 6: CODE REVIEW & QA [Priority: P1]

> Fix TODO items, run security audit, code quality review.

### 6.1 TODO Item Resolution

- [x] **Task 6.1.1**: Fix tenant filtering TODOs in `app/api/routes/costs.py`
  - **Files**: `app/api/routes/costs.py` (modify)
  - **Agent**: `code-puppy`, `security-auditor`
  - **Details**: Replace 7 TODO comments with actual `authz.filter_tenant_ids()` calls
  - **Validation**: `grep -c "TODO" app/api/routes/costs.py` should return 0

- [x] **Task 6.1.2**: Fix tenant filtering TODOs in `app/api/routes/compliance.py`
  - **Files**: `app/api/routes/compliance.py` (modify)
  - **Agent**: `code-puppy`
  - **Validation**: `grep -c "TODO" app/api/routes/compliance.py` should return 0

- [x] **Task 6.1.3**: Fix tenant filtering TODOs in `app/api/routes/recommendations.py`
  - **Files**: `app/api/routes/recommendations.py` (modify)
  - **Agent**: `code-puppy`
  - **Validation**: `grep -c "TODO" app/api/routes/recommendations.py` should return 0

- [x] **Task 6.1.4**: Fix tenant filtering TODOs in `app/api/routes/bulk.py`
  - **Files**: `app/api/routes/bulk.py` (modify)
  - **Agent**: `code-puppy`
  - **Validation**: `grep -c "TODO" app/api/routes/bulk.py` should return 0

- [x] **Task 6.1.5**: Fix tenant filtering TODOs in `app/api/routes/identity.py`
  - **Files**: `app/api/routes/identity.py` (modify)
  - **Agent**: `code-puppy`
  - **Validation**: `grep -c "TODO" app/api/routes/identity.py` should return 0

- [x] **Task 6.1.6**: Fix tenant filtering TODOs in `app/api/routes/resources.py`
  - **Files**: `app/api/routes/resources.py` (modify)
  - **Agent**: `code-puppy`
  - **Validation**: `grep -c "TODO" app/api/routes/resources.py` should return 0

- [x] **Task 6.1.7**: Implement token blacklist in `app/api/routes/auth.py`
  - **Files**: `app/api/routes/auth.py` (modify)
  - **Agent**: `code-puppy`, `security-auditor`
  - **Details**: Replace TODO at line 593 with in-memory (or SQLite-backed) token blacklist
  - **Validation**: `grep -c "TODO" app/api/routes/auth.py` should return 0

### 6.2 Security Review

- [x] **Task 6.2.1**: Run full security audit on auth and authorization modules
  - **Agent**: `security-auditor`
  - **Scope**: `app/core/auth.py`, `app/core/authorization.py`, `app/api/routes/auth.py`
  - **Validation**: Security audit report with 0 critical/high findings

- [x] **Task 6.2.2**: Add `detect-secrets` pre-commit hook (BD issue `fp0`)
  - **Files**: `.pre-commit-config.yaml` (create/modify), `pyproject.toml` (modify)
  - **Agent**: `code-puppy`
  - **Validation**: `pre-commit run detect-secrets --all-files` exits 0

### 6.3 Code Quality Review

- [x] **Task 6.3.1**: Run `ruff check` on entire codebase and fix issues
  - **Agent**: `code-puppy`
  - **Validation**: `uv run ruff check app/ tests/` exits 0 with 0 errors

- [x] **Task 6.3.2**: Run `mypy` type checking on core modules
  - **Agent**: `code-puppy`
  - **Validation**: `uv run mypy app/core/ --ignore-missing-imports` exits 0

- [x] **Task 6.3.3**: Full code review of all service modules
  - **Agent**: `python-reviewer`
  - **Scope**: All files in `app/api/services/`
  - **Validation**: Review report with 0 critical issues

- [x] **Task 6.3.4**: Full code review of all route modules
  - **Agent**: `python-reviewer`
  - **Scope**: All files in `app/api/routes/`
  - **Validation**: Review report with 0 critical issues

---

## 🚀 PHASE 7: STAGING & UAT READINESS [Priority: P0]

> Unblock staging deployment and prepare for UAT.

- [x] **Task 7.1**: Fix Log Analytics retention parameter in Bicep (BD issue `uh2`)
  - **Files**: `infrastructure/modules/log-analytics.bicep` (modify or create), `infrastructure/main.bicep` (modify)
  - **Agent**: `code-puppy`
  - **Details**: Either remove `retentionInDays` or add SKU parameter for pay-per-GB tier
  - **Validation**: `az deployment sub validate --location eastus --template-file infrastructure/main.bicep --parameters @infrastructure/parameters.staging.json` exits 0

- [x] **Task 7.2**: Replace backfill `fetch_data()` placeholders with real Azure API calls (BD issue `0p7`)
  - **Files**: `app/services/backfill_service.py` (modify)
  - **Agent**: `code-puppy`
  - **Validation**: Backfill service fetches real data from Azure APIs

- [x] **Task 7.3**: Clean up orphan ACR `acrgov10188` (BD issue `wv5`)
  - **Agent**: `code-puppy`
  - **Validation**: `az acr show --name acrgov10188` returns "not found"

- [x] **Task 7.4**: Flesh out `deploy-staging.yml` GitHub Actions workflow
  - **Files**: `.github/workflows/deploy-staging.yml` (modify)
  - **Agent**: `code-puppy`
  - **Details**: Add proper QA gate (run tests), Docker build, Trivy scan, deploy steps
  - **Validation**: Workflow runs successfully on staging branch push

- [x] **Task 7.5**: Create UAT test script for staging environment
  - **Files**: `scripts/uat_staging.py` (create)
  - **Agent**: `code-puppy`, `qa-expert`
  - **Test Coverage Required**:
    - Health endpoints (/, /health, /health/detailed)
    - Auth flow (login, token, refresh)
    - All dashboard pages load (200 status)
    - API endpoints return data
    - Preflight checks pass
    - Sync triggers work
    - Riverside dashboard loads with data
  - **Validation**: `uv run python scripts/uat_staging.py --url https://app-governance-staging-001.azurewebsites.net` exits 0

- [x] **Task 7.6**: Update `docs/PRE_STAGING_QA.md` with actual test results
  - **Files**: `docs/PRE_STAGING_QA.md` (modify)
  - **Agent**: `qa-expert`
  - **Validation**: All checklist items marked complete

---

## 📊 QUALITY GATES (Must Pass Before COMPLETED)

Run these after all phases are done:

```bash
# Gate 0: Pre-flight Check - Verify Phase 5 files exist
echo "Checking Phase 5 integration test files..."
ls -la tests/integration/test_*.py 2>/dev/null | wc -l
# Expected: >= 7 files (plus auth_flow/ package)

# Check individual test files
for file in test_cost_api test_compliance_api test_resource_api test_identity_api test_riverside_api test_sync_api test_tenant_isolation; do
  if [ -f "tests/integration/${file}.py" ]; then
    lines=$(wc -l < "tests/integration/${file}.py")
    funcs=$(grep -cE "(^def test_|^    def test_|^async def test_)" "tests/integration/${file}.py" 2>/dev/null || echo "0")
    echo "  ✓ ${file}.py: ${lines} lines, ${funcs} test functions"
  else
    echo "  ✗ ${file}.py: MISSING"
  fi
done

# Check auth_flow package
if [ -d "tests/integration/auth_flow" ]; then
  test_files=$(ls -1 tests/integration/auth_flow/test_*.py 2>/dev/null | wc -l)
  total_funcs=0
  for f in tests/integration/auth_flow/test_*.py; do
    if [ -f "$f" ]; then
      funcs=$(grep -cE "(^def test_|^    def test_|^async def test_)" "$f" 2>/dev/null || echo "0")
      total_funcs=$((total_funcs + funcs))
    fi
  done
  echo "  ✓ auth_flow/ package: ${test_files} test files, ${total_funcs} test functions"
else
  echo "  ✗ auth_flow/ package: MISSING"
fi

# Gate 1: Unit tests
uv run pytest tests/unit/ -q --tb=short
# Expected: 900+ tests, 0 failures

# Gate 2: Integration tests
uv run pytest tests/integration/ -q --tb=short
# Expected: 60+ tests, 0 failures

# Gate 3: Linting
uv run ruff check app/ tests/
# Expected: 0 errors

# Gate 4: All tests combined
uv run pytest tests/ -q --tb=short --ignore=tests/e2e --ignore=tests/smoke
# Expected: 0 failures

# Gate 5: No remaining TODOs in routes
grep -rn "TODO" app/api/routes/ | wc -l
# Expected: 0
```

---

## 📝 COMPLETION CHECKLIST

When all phases are done, verify:

- [ ] All tasks in Phases 1-7 are marked `[x]`
- [ ] `uv run pytest tests/unit/ -q` → 0 failures, 900+ tests
- [ ] `uv run pytest tests/integration/ -q` → 0 failures, 60+ tests
- [ ] `uv run ruff check app/ tests/` → 0 errors
- [ ] `grep -rn "TODO" app/api/routes/ | wc -l` → 0
- [ ] All changes committed and pushed: `git status` shows clean
- [ ] BD issues updated: `bd sync`
- [ ] `loop_status` in METADATA above changed to `COMPLETED`

**When all boxes above are checked → call `/wiggum_stop`**
