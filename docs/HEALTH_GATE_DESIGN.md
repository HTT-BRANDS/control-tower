# Deployment Health Gate Design

> Status: **active design doc**.
> Owner: control-tower platform.
> Last updated: 2026-05-19 (ct-czv AC #3).
>
> If you are about to change which endpoint a deployment workflow or Azure App
> Service health probe targets, **read this first**.

## TL;DR

| Gate | Endpoint | Why |
| --- | --- | --- |
| Azure App Service `healthCheckPath` (Bicep) | `/health` | Basic 200 liveness. Survives intentional staging config omissions. |
| `deploy-staging.yml` → "Health gate readiness loop" | `/health` | Same reason. Gates only on HTTP 200. |
| `deploy-production.yml` → probe helper | `/health` (gating) + `/health/detailed`, `/healthz/data` (advisory only) | Deeper endpoints may legitimately 503 during cold-start. |
| `tests/staging/test_deployment.py` → `health_data` fixture | `/health` | Asserts `status: "healthy"`, which the basic endpoint always returns when the app process is up. |

**Rule:** *deployment-gating* code must hit `/health` (or accept HTTP 200 only).
The detailed endpoints are **observability**, not **gates**.

## Why this matters

Each environment has different "fully configured" semantics:

| Environment | Azure AD creds | DB | Cache | `azure_configured` rollup | `/health/detailed` overall |
| --- | --- | --- | --- | --- | --- |
| **production** | required | required | required | `configured` or `missing` | `healthy` only when everything present |
| **staging** | **intentionally omitted** | required | optional | `not_required` | `healthy` even without Azure creds |
| **development** | optional | required | optional | `not_required` if missing | `healthy` if app process is up |

The tri-state `azure_configured` rollup was introduced in PR #41 (ct-czv AC #2)
precisely so that detailed health stops reporting `degraded` when staging
legitimately omits Azure credentials. The contract is documented in
[`STAGING_ENV_VARS.md`](./STAGING_ENV_VARS.md#azure-ad-credentials-tri-state).

### The trap

Before PR #41, `/health/detailed` reported `degraded` whenever any Azure AD
credential was missing — including in staging, where that omission is
*intentional* (blast radius, cost, PII surface). Two anti-patterns then
threaten the deploy pipeline:

1. **Gating on `/health/detailed`** — fails every staging deploy on expected
   configuration. The staging workflow correctly avoids this by gating only on
   `/health`.
2. **Gating on `/health/detailed` HTTP code** — `/health/detailed` returns HTTP
   200 with body `{"status": "degraded", ...}`, so `curl -f` doesn't
   automatically catch it. A naive "if body contains `degraded`, fail" check
   would re-introduce trap #1.

PR #41 makes the *content* correct (staging without creds is `healthy` again),
but the deployment gates should still target `/health` regardless, because:

- `/health` is the canonical "process is up and answering" signal.
- `/health/detailed` is an *operator-facing* observability surface — it can
  report `degraded` even when the service is healthy for the gate's purposes
  (e.g., cache backend slow, cost-sync stale).

## When SHOULD a gate hit `/health/detailed`?

When you are *deliberately gating on a richer signal than liveness*. Examples:

- **Promotion gates** in CI/CD pipelines that block staging → production until
  a sync has run successfully. These should hit `/healthz/data` or
  `/api/v1/health/data` (sync-freshness endpoints), not `/health/detailed`.
- **Synthetic monitors** that need an early warning of degradation. These are
  alerting paths, not deployment paths.

In all cases, the gate must understand the **tri-state Azure rollup**:

| `azure_configured` | Treat as fault? |
| --- | --- |
| `configured` | No. |
| `not_required` | **No.** Intentional staging configuration. |
| `missing` | Yes — but only in production. |

## How to verify the staging gate accounts for staging config

```bash
# Staging /health must always return 200 + healthy, regardless of Azure creds.
curl -sf https://${STAGING_HOST}/health -w '%{http_code}\n' -o /dev/null
# expected: 200

# Staging /health/detailed reports `azure_configured: not_required`, overall healthy.
curl -s https://${STAGING_HOST}/api/v1/health/detailed \
  | jq '{status, azure: .checks.azure_configured.status}'
# expected: {"status": "healthy", "azure": "not_required"}
```

Both must be true after a deploy. If either fails, the deploy gate has
correctly caught a real problem — investigate before bypassing.

## Anti-patterns to avoid

| Anti-pattern | Why it's wrong | What to do instead |
| --- | --- | --- |
| `curl -f /health/detailed` as a deploy gate | Surfaces transient cold-start degradation as a hard fail; surfaces intentional staging config as a hard fail. | Gate on `/health`. Log `/health/detailed` advisorily. |
| `if [[ "$body" == *"degraded"* ]]; then fail; fi` | Re-introduces the trap PR #41 fixed. | Parse `azure_configured.status` explicitly with `jq` and ignore `not_required`. |
| Changing `healthCheckPath` in Bicep without consulting this doc | Bypasses 6+ months of accumulated context. | Read this doc. If the change still seems right, update this doc in the same PR. |
| Adding `/health/detailed` assertions to `tests/staging/` | These run against live staging and will flap on cold-start cache probes. | Add to `tests/integration/` instead, against a controlled test fixture. |

## Related issues and PRs

- **ct-czv AC #3** — this design doc.
- **PR #41** — `CacheManager.check_health` + tri-state `azure_configured`.
- **PR #42** — `docs/STAGING_ENV_VARS.md` (env-var contract).
- **ct-l2j** — separate concern (sync alert dedup); see PR #43.

## Change protocol

When you change anything that gates on a health endpoint:

1. Read this doc.
2. Identify which environment the gate runs in (prod, staging, dev, CI).
3. Identify the failure mode you're trying to catch.
4. Pick the *narrowest* endpoint that catches it. Prefer `/health` unless you
   have a specific reason to read deeper state.
5. If you must parse `/health/detailed`, parse it as structured JSON via `jq`
   and explicitly allow `azure_configured.status == "not_required"` in
   non-production environments.
6. Update this doc in the same PR.
