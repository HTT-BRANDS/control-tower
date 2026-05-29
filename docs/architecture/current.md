# Current Architecture (as of 2026-05-29)

**Companion to:** [`overview.md`](./overview.md) — the **target / aspirational**
architecture. This file describes what **actually exists** in production today,
so new contributors aren't hunting for nonexistent infrastructure.

> ⚠️ **Why this file exists** — see [bd ct-lw2](../../README.md). The Miro
> architecture diagram (and large parts of `overview.md`) describes the
> **target** Q3 2026+ architecture, not what's deployed now. This document is
> the ground truth.

---

## TL;DR — What we actually run

**One FastAPI monolith on one Azure App Service Plan, with APScheduler
running background jobs in-process, talking to a single Azure SQL database.**

That's it. Everything else listed in the target diagram is either:

- A library inside the same process (e.g. cache, auth, audit log)
- An optional adapter that's not currently provisioned (e.g. Redis)
- Future work tracked in a bd issue (e.g. ct-f9p UAMI migration)

---

## System Context (current reality)

```
┌─────────────────────────────────────────────────────────┐
│                    EXTERNAL USERS                       │
│         (Admins, End Users, API Clients)                │
└────────────────────────┬────────────────────────────────┘
                         │ HTTPS (direct, no CDN/Front Door)
                         ▼
┌─────────────────────────────────────────────────────────┐
│        AZURE APP SERVICE — Linux Python 3.12            │
│        (single plan, two slots: prod + staging)         │
│ ┌─────────────────────────────────────────────────────┐ │
│ │            FastAPI Monolith (app/)                  │ │
│ │                                                     │ │
│ │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │ │
│ │  │ API      │  │ Services │  │ APScheduler      │ │ │
│ │  │ Routes   │→ │ Layer    │← │ (in-process)     │ │ │
│ │  │ (HTTP)   │  │          │  │ Costs/Compliance │ │ │
│ │  └──────────┘  └─────┬────┘  │ /Identity/etc.   │ │ │
│ │                      │       └──────────────────┘ │ │
│ │  ┌──────────┐        │                            │ │
│ │  │ Auth     │        │                            │ │
│ │  │ (in-proc │        │                            │ │
│ │  │  JWT +   │        │                            │ │
│ │  │  Entra)  │        │                            │ │
│ │  └──────────┘        │                            │ │
│ │                      │                            │ │
│ │  ┌──────────────────┴──────────────────┐         │ │
│ │  │  In-Memory Cache (InMemoryCache)    │         │ │
│ │  │  (Redis adapter exists but unused)  │         │ │
│ │  └─────────────────────────────────────┘         │ │
│ └──────────────────────┬──────────────────────────────┘ │
└─────────────────────────┼──────────────────────────────┘
                          ▼
        ┌─────────────────────────────────────┐
        │  AZURE SQL DATABASE (mssql+pyodbc)  │
        │  - All app data                     │
        │  - All audit/sync logs              │
        │  - All cache fallback persistence   │
        └─────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────────┐
        ▼                 ▼                     ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
│  KEY VAULT   │  │ APP INSIGHTS │  │ STORAGE ACCOUNT  │
│  - secrets   │  │ - traces     │  │ - blob backups   │
│  - SP creds  │  │ - metrics    │  │ - file shares    │
└──────────────┘  └──────────────┘  └──────────────────┘
```

---

## What IS deployed (verified against `infrastructure/*.bicep`)

| Component | Azure Resource | Purpose |
|---|---|---|
| Web app | `Microsoft.Web/sites` (App Service) | The FastAPI monolith |
| Plan | `Microsoft.Web/serverfarms` | Single plan, prod + staging slots |
| Database | `Microsoft.Sql/servers/databases` | Single Azure SQL DB per environment |
| Secrets | `Microsoft.KeyVault/vaults` | App secrets, SP credentials |
| Observability | `Microsoft.Insights/components` | App Insights traces + metrics |
| Storage | `Microsoft.Storage/storageAccounts` | Blob (backups) + File shares |
| Identity | `Microsoft.ManagedIdentity/userAssignedIdentities` | UAMI federated to GitHub OIDC |
| Cost cleanup | `Microsoft.Logic/workflows` | Logic App for tagged-resource cleanup |
| One-shot jobs | `Microsoft.ContainerInstance/containerGroups` | Ad-hoc admin tasks |

## What IS NOT deployed (despite appearing in target diagrams)

| Component | Status | Notes |
|---|---|---|
| Azure Front Door / CDN | ❌ Not deployed | App Service serves HTTPS directly |
| Separate Auth service | ❌ In-process | `app/core/auth.py` — JWT + Entra ID in the FastAPI app |
| Redis Cache | ❌ Bicep module exists but unprovisioned | `infrastructure/modules/redis.bicep`; cache falls back to `InMemoryCache` |
| Service Bus / message queue | ❌ Not deployed | Background work is APScheduler in-process |
| Separate File storage service | ⚠️ Partial | Storage Account exists but app uses DB for state, not blob |
| Separate Audit log service | ❌ In-process | Audit events go to the same Azure SQL DB |
| API Gateway | ❌ Not deployed | FastAPI is the gateway |
| Container orchestration (AKS) | ❌ Not deployed | App Service handles scaling |

---

## Current scaling model

- **Vertical**: change App Service Plan SKU (manual)
- **Horizontal**: App Service auto-scale rules (CPU > 70% → +1 instance), but
  in-process scheduler means **only one instance runs background jobs** — the
  others would duplicate sync work. Effectively single-instance for writes.
- **Multi-tenant**: single codebase, tenant_id column on every table.
  Row-level isolation, not schema or DB isolation.

## Current resilience model

- **Circuit breakers**: in-process, per-external-API (`app/core/circuit_breaker.py`)
- **Retry**: in-process, exponential backoff (`app/core/retry.py`)
- **Graceful degradation**: per-domain health checks return 200 even when one
  data source is stale (see `app/api/routes/health.py`)
- **Backup**: Azure SQL automated backups (PITR) + blob snapshots
- **DR**: not yet — single region (East US 2)

---

## Honest gap list (vs `overview.md` target)

| Target capability | Current state | bd issue |
|---|---|---|
| Multi-tier cache (L1 memory → L2 Redis → L3 CDN) | L1 only | None — YAGNI until traffic justifies |
| Service Bus event-driven workflows | APScheduler cron | None — YAGNI |
| Blue/green slot deploys | ✅ Implemented (staging + prod slots) | — |
| Separate audit microservice | In-process audit table | None — appropriate for current scale |
| Managed Identity for SP auth | Mixed (some UAMI, some SP secrets) | ct-f9p |
| API Gateway with rate limiting | In-process `app/core/rate_limit.py` | None |
| Multi-region active-active | Single region | Deferred to post-Riverside deadline |

---

## When this document needs updating

Update whenever **any of these changes**:

1. A new top-level Azure resource is added to `infrastructure/*.bicep`
2. A "not deployed" item from the table above gets provisioned
3. The single-instance scheduler assumption changes (e.g. moves to Azure Functions)
4. Database tier or count changes (e.g. read replicas, sharding)

Owner: whoever lands the infra change. Reviewer: Tyler.

---

## See also

- [`overview.md`](./overview.md) — target / aspirational architecture
- [`authentication.md`](./authentication.md) — auth flow detail
- [`data-flow.md`](./data-flow.md) — sync pipelines
- [bd ct-f9p](../../README.md) — UAMI migration
- [bd ct-lw2](../../README.md) — this file's origin issue
