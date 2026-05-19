# Staging Environment Variable Contract

**Status:** Authoritative
**Last Updated:** 2026-05-19
**Owner:** Platform
**Related issues:** ct-czv (AC #4)

This document is the single source of truth for which environment variables
the application reads, which ones are required in which environments, and —
critically — **which omissions are intentional in non-production**.

If a setting is *intentionally* omitted in staging, it is listed here with the
reason. Operators reading `/api/v1/health/detailed` against staging should see
fields like `azure_configured: "not_required"` for those settings and **must
not treat that as a fault**. The detailed-health endpoint was hardened in
PR #41 to surface this distinction (ct-czv AC #2).

## Quick reference

| Variable | Required in prod | Required in staging | Default | Notes |
| --- | --- | --- | --- | --- |
| `ENVIRONMENT` | ✅ | ✅ | `development` | Must be `production` or `staging`. Drives all the tri-state checks below. |
| `DATABASE_URL` | ✅ | ✅ | — | Postgres connection string. No fallback. |
| `JWT_SECRET_KEY` | ✅ | ✅ | random per-process | In prod, `Settings.validate_jwt_secret_production` refuses to boot without an explicit value. Random fallback is dev-only. |
| `JWT_ISSUER` | optional | optional | `azure-governance-platform` | Override for the in-flight issuer transition (ct-vgf). |
| `JWT_AUDIENCE` | optional | optional | `azure-governance-api` | Override for the in-flight issuer transition (ct-vgf). |
| `REDIS_URL` | ❎ optional | ❎ optional | in-memory cache | App falls back to `InMemoryCache` if unset. Health endpoint reports `cache.backend: "memory"`. |
| `CACHE_ENABLED` | optional | optional | `true` | Setting to `false` reports `cache.status: "disabled"` (not `degraded`) via `CacheManager.check_health` (PR #41). |
| `AZURE_AD_TENANT_ID` | ✅ | ❎ **intentionally omitted** | — | See [Azure AD section](#azure-ad-credentials-tri-state) below. |
| `AZURE_AD_CLIENT_ID` | ✅ | ❎ **intentionally omitted** | — | See [Azure AD section](#azure-ad-credentials-tri-state) below. |
| `AZURE_AD_CLIENT_SECRET` | ✅ | ❎ **intentionally omitted** | — | See [Azure AD section](#azure-ad-credentials-tri-state) below. |
| `KEY_VAULT_URL` | ✅ | optional | — | Required in prod for secret pull-through. Staging can use plaintext App Service settings. |
| `CORS_ORIGINS` | ✅ | ✅ | `*` | Comma-separated allowlist. |
| `APP_INSIGHTS_CONNECTION_STRING` | ✅ recommended | optional | — | Telemetry pipeline. Missing in staging is fine; you just lose telemetry. |

## Azure AD credentials (tri-state)

Three settings — `AZURE_AD_TENANT_ID`, `AZURE_AD_CLIENT_ID`, and
`AZURE_AD_CLIENT_SECRET` — together control whether the platform can perform
Azure-data syncs (cost, compliance, resources, identity) and whether the
detailed-health rollup considers the deployment "fully configured".

After PR #41, `/api/v1/health/detailed` reports one of three states:

| Reported `azure_configured` | Conditions | Overall status impact |
| --- | --- | --- |
| `"configured"` | All three creds present (any environment) | None — healthy contributor. |
| `"not_required"` | At least one cred missing **AND** `is_production == False` | **None.** Intentional staging configuration. Overall status NOT degraded. |
| `"missing"` | At least one cred missing **AND** `is_production == True` | Promotes overall status to `degraded`. Real fault. |

### Why staging intentionally omits Azure AD creds

Staging is a thin-slice environment intended to validate code paths,
migrations, and UI changes against a Postgres + Redis topology. We
deliberately do **not** wire production Azure AD app registrations into
staging because:

1. **Blast radius.** A staging bug that triggers a real Graph API call
   against the production tenant would write to real audit logs.
2. **Cost.** Many Azure data calls are billable per request.
3. **Permissions surface.** Granting staging an app registration with
   directory-wide read pulls real PII into a less-trusted environment.

If a staging-specific test of the Azure code paths is needed, use a dedicated
*sandbox* Azure AD tenant — never the production one — and document its
existence here.

## Operator-script credentials (`scripts/manual_sync.py`)

After ct-51g (PR #42), `scripts/manual_sync.py` no longer contains any
hardcoded secret. Operators supply one of:

| Variable | Purpose |
| --- | --- |
| `MANUAL_SYNC_TOKEN` | **Preferred.** Pre-minted operator bearer token. Used verbatim. |
| `JWT_SECRET_KEY` | Raw HS256 signing secret. The script mints a 30-minute admin token in-process. |
| `JWT_ISSUER` *(optional)* | Override issuer for the ct-vgf transition. |
| `JWT_AUDIENCE` *(optional)* | Override audience for the ct-vgf transition. |
| `MANUAL_SYNC_OPERATOR_EMAIL` *(optional)* | Identity stamped into the `email` claim. |
| `MANUAL_SYNC_BASE_URL` *(optional)* | Override target URL. Defaults to production. |

With neither `MANUAL_SYNC_TOKEN` nor `JWT_SECRET_KEY` set, the script
**fails closed** with exit code 2 and a clear error message — it will
**never** make an unsigned HTTP request.

## How to verify staging is configured correctly

```bash
# Sanity check: detailed health should be `healthy` even without Azure creds
curl -s https://governance-staging.yourdomain.com/api/v1/health/detailed \
  | jq '{status, azure: .checks.azure_configured, cache: .checks.cache.status}'
```

Expected (correctly-configured staging without Azure creds):

```json
{
  "status": "healthy",
  "azure": { "status": "not_required", "environment": "staging" },
  "cache": "healthy"
}
```

If `azure.status` is `"missing"` instead of `"not_required"` in staging,
either:

* the `ENVIRONMENT` variable is wrong (probably set to `production`), or
* `Settings.is_production` is computing differently than expected — check
  `app/core/config.py`.

## Related documents

* [`docs/STAGING_DEPLOYMENT_CHECKLIST.md`](./STAGING_DEPLOYMENT_CHECKLIST.md) — step-by-step provisioning
* [`docs/DEPLOYMENT.md`](./DEPLOYMENT.md) — production deployment runbook
* [`docs/GITHUB_SECRETS_SETUP.md`](./GITHUB_SECRETS_SETUP.md) — CI secret wiring
* `app/core/config.py` — authoritative `Settings` model and validators
