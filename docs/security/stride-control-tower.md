# STRIDE Threat Analysis — HTT Control Tower

| Field | Value |
|---|---|
| **Analysis ID** | STRIDE-CT-2026-Q3 |
| **Analyst** | Richard (code-puppy-1725d8) |
| **Date** | 2026-06-08 |
| **Scope** | Control Tower governance platform — app, API, infrastructure, integrations |
| **Methodology** | Microsoft STRIDE + OWASP ASVS v4 |
| **Next review** | 2026-09-08 (quarterly) |

---

## System Boundary

The Control Tower is a multi-tenant Flask application hosted on Azure App Service (Linux container) that:

1. **Syncs** Azure resource, compliance, cost, and identity data from 5 brand tenants via Graph API + ARM API
2. **Serves** a branded dashboard (DaisyUI + HTMX) for franchise operators, managers, and executives
3. **Stores** synced data in Azure SQL Basic, secrets in Key Vault
4. **Runs** a background scheduler (APScheduler) for periodic sync
5. **Authenticates** via Entra ID (OIDC), authorizes via a 5-role RBAC model
6. **Exposes** health/metrics endpoints and a REST API

### Trust Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (user)                                            │
│  └── Entra ID auth → session cookie → API calls + pages    │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTPS
┌───────────────────────▼─────────────────────────────────────┐
│  Azure App Service (container)                              │
│  ├── Flask app (non-root appuser)                           │
│  ├── APScheduler (in-process)                              │
│  ├── Security middleware (CSP, HSTS, rate-limit)           │
│  └── Managed identity → Key Vault + Graph API               │
└───────┬──────────────────────┬──────────────────────────────┘
        │                      │
┌───────▼────────┐  ┌─────────▼──────────┐
│  Azure SQL     │  │  Azure Key Vault    │
│  (Basic tier)  │  │  (purge-protected)  │
└────────────────┘  └─────────────────────┘
        │
┌───────▼────────────────────────────────────┐
│  Azure Graph API / ARM API (5 tenants)      │
│  Each tenant: Entra ID + optional ARM sub  │
└─────────────────────────────────────────────┘
```

---

## Threat Table

### S — Spoofing

| # | Threat | Risk | Mitigation | Status |
|---|--------|------|------------|--------|
| S1 | User impersonation via stolen session cookie | Medium | Entra ID OIDC with short-lived tokens; session cookie is httpOnly + Secure + SameSite=Lax | Mitigated |
| S2 | Scheduler job spoofing (fake sync runs) | Low | Scheduler runs in-process; no external trigger; scheduler heartbeat monitored via `/healthz/scheduler` | Mitigated |
| S3 | API key theft from Key Vault | Medium | Key Vault purge-protected; managed identity (no stored secrets); soft-delete tested (DR drill 2026-06-08) | Mitigated |
| S4 | Cross-tenant data access | High | Tenant isolation via `tenant_id` FK on all models; RBAC enforces tenant scoping; admin-only cross-tenant access | Mitigated |

### T — Tampering

| # | Threat | Risk | Mitigation | Status |
|---|--------|------|------------|--------|
| T1 | SQL injection via API input | Medium | Parameterized queries via SQLAlchemy ORM; no raw SQL; CSP blocks inline scripts | Mitigated |
| T2 | XSS via dashboard content | Medium | Jinja2 auto-escaping; CSP nonce on scripts; no `innerHTML` in HTMX responses; `text-gray-100` lint in CI | Mitigated |
| T3 | Tampering with compliance/resource data | Medium | Write access restricted to scheduler (system) and admin role; audit log on all writes; `created_at`/`updated_at` timestamps | Mitigated |
| T4 | Container image tampering | Medium | GHCR with digest pinning; Dockerfile runs non-root (USER appuser); security-scan.yml runs Trivy + pip-audit | Partial — no cosign signing (see P6.7) |
| T5 | Template/theme injection | Low | Design tokens are CSS variables (not eval'd); HTMX responses are server-rendered; no user-supplied templates | Mitigated |

### R — Repudiation

| # | Threat | Risk | Mitigation | Status |
|---|--------|------|------------|--------|
| R1 | User denies performing an action | Low | Audit log service records actor, action, target, timestamp; Entra ID OIDC provides verified identity | Mitigated |
| R2 | Scheduler denies running a sync | Low | Sync job logs record `started_at`/`completed_at`; scheduler heartbeat monitored; orphan job check (P3.3) in judge | Mitigated |
| R3 | Admin denies config change | Low | All admin actions logged to audit_log table; cannot be deleted by non-system users | Mitigated |

### I — Information Disclosure

| # | Threat | Risk | Mitigation | Status |
|---|--------|------|------------|--------|
| I1 | API docs leak schema details | Medium | /docs, /redoc, /openapi.json all return 401 for unauthenticated users | Mitigated |
| I2 | Key Vault secret exfiltration | Medium | Managed identity (no stored credentials); Key Vault access logged; purge protection prevents permanent deletion; RBAC on vault | Mitigated |
| I3 | Cross-tenant data leakage | High | Tenant-scoped queries; viewer role has no cross-tenant access; manager role sees aggregated only; admin is audited | Mitigated |
| I4 | Error messages leak internals | Low | Server header sanitized (`Azure-Governance-Platform`); no stack traces in production; DEBUG=false | Mitigated |
| I5 | Cost/compliance data exported by unauthorized user | Medium | Export restricted to analyst+ roles; viewer cannot export; rate limiting on export endpoints | Mitigated |

### D — Denial of Service

| # | Threat | Risk | Mitigation | Status |
|---|--------|------|------------|--------|
| D1 | HTTP flood | Medium | Rate limiting (100 req/min); App Service auto-scaling; Azure DDoS protection on front end | Mitigated |
| D2 | Scheduler starvation | Low | APScheduler runs in-process (not queue-based); sync jobs are short (< 30s per tenant); scheduler heartbeat monitored | Mitigated |
| D3 | SQL connection exhaustion | Low | SQLAlchemy connection pool with overflow limit; Azure SQL Basic tier has connection cap | Mitigated |
| D4 | Key Vault throttling | Low | Managed identity caches tokens; KV calls are infrequent (app startup + scheduler only) | Mitigated |

### E — Elevation of Privilege

| # | Threat | Risk | Mitigation | Status |
|---|--------|------|------------|--------|
| E1 | User promotes themselves to admin | High | Role assignment requires existing admin; `setup_admin.py` is server-side script; no self-service role elevation | Mitigated |
| E2 | Viewer escalates to analyst export | Medium | RBAC enforced server-side on every endpoint; no client-side permission checks; role stored in DB, not cookie | Mitigated |
| E3 | Scheduler runs as elevated context | Low | Scheduler runs as app user (non-root); no admin API access from scheduler; managed identity scoped to KV + Graph | Mitigated |
| E4 | Container escape | Low | App Service isolated environment; Dockerfile runs non-root; no privileged capabilities | Mitigated |

---

## Residual Risks

| # | Risk | Severity | Owner | Tracking |
|---|------|----------|-------|----------|
| R1 | **No SLSA/cosign image signing** — supply chain not verified | Medium | Richard | ct-qd9 |
| R2 | **Single-region Azure** — no geo-failover for SQL or App Service | Low | By design | N/A (internal dashboard) |
| R3 | **Azure SQL Basic tier** — 7-day PITR only, no LTR | Low | Tyler | BACPAC validation (bd cz89) |
| R4 | **External creds not revoked** — Cloudflare + Cloudways tokens from decommissioned DomainIQ | Low | Tyler | ct-18z |
| R5 | **No load testing** — unknown behavior under 100+ concurrent users | Low | Richard | ct-lrw |

---

## Review Cadence

This document must be reviewed quarterly (next: 2026-09-08). Review checklist:

1. Update system boundary if new integrations added
2. Verify mitigations still effective (re-run judge + DR drills)
3. Assess residual risks — promote any that changed severity
4. Check for new OWASP Top 10 items
5. Update the "Next review" date

---

*STRIDE analysis for Control Tower. Authored 2026-06-08 by Richard. Review by 2026-09-08.*
