# Authentication Transition Roadmap

**Created:** 2026-03-31
**Status:** Decision made — see [docs/decisions/adr-0012-ci-cd-oidc-identity-model.md](decisions/adr-0012-ci-cd-oidc-identity-model.md).
**Goal:** Move from per-tenant client secrets to a sustainable, low-maintenance
authentication pattern for cross-tenant Graph API + ARM access.

> **ct-9x9 historical note (2026-05-19):** This document still describes
> **Option 4 (Azure Lighthouse + Per-Tenant SP for Graph)** as a candidate.
> That option was retired in `ct-59n` (April 2026) — Azure Lighthouse
> delegation was never wired up in production (zero delegations across all
> 5 tenants) and the `LighthouseAzureClient` code path plus the
> `tenants.use_lighthouse` column were removed in `ct-59n` and migration
> `011_drop_tenant_use_lighthouse.py`. The selected direction is **OIDC
> Workload Identity Federation** (`USE_OIDC_FEDERATION=true`) with
> per-tenant federated SPs. The Lighthouse comparison below is preserved
> verbatim for decision-record traceability — do **not** treat it as a
> live recommendation.

---

## Current State

| Aspect | Value |
|--------|-------|
| **Current mode** | `USE_OIDC_FEDERATION=false` (client secrets via Key Vault) |
| **Tenants** | 5 (HTT, BCC, FN, TLL, DCE) |
| **APIs accessed** | Microsoft Graph (MFA, users, roles) + Azure ARM (resources, costs) |
| **Secret rotation** | Manual, ~2 year expiry per tenant |
| **Maintenance burden** | ~10 hours/year for secret rotation |

### Why OIDC Federation Failed

The per-tenant OIDC Workload Identity Federation approach hit `AADSTS700236`:
Microsoft explicitly prohibits using Entra ID-issued tokens (from App Service
Managed Identity) as assertions in federated identity credential flows across
tenants. This is a **platform limitation**, not a configuration error.

---

## Option Analysis

### Option 1: Per-Tenant Client Secrets via Key Vault *(CURRENT)*

```
Production App Service
    │
    ▼
Key Vault (kv-gov-prod-001)
    ├── htt-client-secret
    ├── bcc-client-secret
    ├── fn-client-secret
    ├── tll-client-secret
    └── dce-client-secret
    │
    ▼ ClientSecretCredential(tenant_id, client_id, secret)
    │
    ▼ Graph API + ARM API
```

| Pros | Cons |
|------|------|
| ✅ Already working | ❌ Secret rotation every 1-2 years |
| ✅ Battle-tested pattern | ❌ 5 secrets to manage |
| ✅ Simple to understand | ❌ Outage risk if secret expires unnoticed |
| ✅ No cross-tenant admin needed after setup | ❌ Secrets stored at rest (encrypted in KV) |

**Maintenance:** ~2 hours/year per tenant for rotation = ~10 hours/year
**Complexity:** Low
**Risk:** Medium (expiration-based outages)

---

### Option 2: Multi-Tenant App Registration + Client Secret

```
HTT Tenant (home)
    │
    └── App Registration (multi-tenant, signInAudience: AzureADMultipleOrgs)
        ├── client_id: single ID for all tenants
        └── client_secret: single secret in Key Vault
    │
    ▼ Admin consent granted in BCC, FN, TLL, DCE
    │
    ▼ ClientSecretCredential(target_tenant_id, multi_tenant_client_id, secret)
    │
    ▼ Graph API + ARM API
```

| Pros | Cons |
|------|------|
| ✅ Single secret to manage (1 instead of 5) | ❌ Still requires a secret |
| ✅ Admin consent is one-time per tenant | ❌ Requires Global Admin consent in each foreign tenant |
| ✅ Simpler rotation (1 secret) | ❌ Single point of failure |
| ✅ Standard Microsoft pattern | ❌ Permission scope is same across all tenants |

**Maintenance:** ~2 hours/year (single secret rotation)
**Complexity:** Low-Medium
**Risk:** Low-Medium

---

### Option 3: Multi-Tenant App + User-Assigned Managed Identity (UAMI)

```
HTT Tenant (home)
    │
    ├── User-Assigned Managed Identity (mi-governance-platform)
    │   └── Federated Identity Credential → multi-tenant app
    │
    └── App Registration (multi-tenant)
        ├── client_id: single ID
        └── NO client secret needed
    │
    ▼ ManagedIdentityCredential → get assertion token
    ▼ ClientAssertionCredential(target_tenant_id, client_id, assertion_func)
    │
    ▼ Admin consent granted in BCC, FN, TLL, DCE
    │
    ▼ Graph API + ARM API
```

| Pros | Cons |
|------|------|
| ✅ Zero secrets | ❌ Complex setup |
| ✅ No rotation ever | ❌ Requires UAMI in home tenant |
| ✅ Microsoft's recommended GA pattern | ❌ Requires Global Admin consent in each foreign tenant |
| ✅ Works for both Graph + ARM | ❌ FIC must be on the multi-tenant app, NOT per-tenant apps |
| ✅ No expiration risk | ❌ Debugging auth failures is harder |

**Maintenance:** ~0 hours/year
**Complexity:** High (initial), Low (ongoing)
**Risk:** Low (no expiration-based failures)

---

### Option 4: Azure Lighthouse + Per-Tenant SP for Graph

```
ARM Access (costs, resources, compliance):
    └── Azure Lighthouse delegation from each tenant
        └── Single managing-tenant SP with Reader role
        └── Works today ✅

Graph Access (MFA, users, identity):
    └── Per-tenant app registrations (existing)
        └── Client secrets in Key Vault (Option 1)
        OR
        └── Multi-tenant app (Option 2 or 3)
```

| Pros | Cons |
|------|------|
| ✅ Lighthouse already partially set up | ❌ Hybrid approach — two auth patterns |
| ✅ ARM access is zero-secret (Lighthouse) | ❌ Graph still needs secrets or multi-tenant app |
| ✅ Least-privilege for ARM | ❌ More code complexity |
| ✅ Can mix approaches | ❌ Harder to reason about |

**Maintenance:** ~5 hours/year (only Graph secrets)
**Complexity:** Medium
**Risk:** Low

---

## Recommendation

### Short-Term (Now → 3 months): Option 1 — Per-Tenant Client Secrets

**Why:** It works today. The code is written and tested. Get data flowing NOW.

**Actions:**
1. ✅ Set `USE_OIDC_FEDERATION=false` in production
2. ✅ Store client secrets in Key Vault
3. Set calendar reminders for secret rotation (2-year expiry)
4. Monitor via App Insights for auth failures

### Medium-Term (3-6 months): Option 2 — Multi-Tenant App + Single Secret

**Why:** Reduces 5 secrets to 1. Simpler rotation. Standard pattern.

**Actions:**
1. Create multi-tenant app registration in HTT tenant
2. Grant admin consent in BCC, FN, TLL, DCE
3. Update `config/tenants.yaml` — all tenants use same `app_id`
4. Update credential resolution code (minimal changes)
5. Store single secret in Key Vault
6. Remove per-tenant app registrations (after soak period)

### Long-Term (6-12 months): Option 3 — Multi-Tenant App + UAMI

**Why:** Zero secrets forever. No rotation. Microsoft's recommended pattern.

**Actions:**
1. Create User-Assigned Managed Identity in `rg-governance-production`
2. Assign UAMI to App Service
3. Add Federated Identity Credential on the multi-tenant app
4. Update `oidc_credential.py` for the new pattern
5. Test on staging for 2+ weeks
6. Deploy to production
7. Remove client secrets from Key Vault
8. Update `USE_OIDC_FEDERATION=true` with the fixed pattern

---

## Implementation Tasks by Phase

### Phase A: Immediate Fix (Client Secrets) — DONE when runbook is executed

See `docs/runbooks/enable-secret-fallback.md`

No code changes needed. Just Azure configuration.

### Phase B: Multi-Tenant App (Single Secret)

| # | Task | Owner | Effort |
|---|------|-------|--------|
| B.1 | Create multi-tenant app registration in HTT | Tyler (Azure portal) | 30 min |
| B.2 | Grant Graph API permissions + admin consent | Tyler (each tenant) | 1 hour |
| B.3 | Store single client secret in Key Vault | Tyler (Azure CLI) | 15 min |
| B.4 | Update `config/tenants.yaml` — shared app_id | code-puppy | 15 min |
| B.5 | Update `_resolve_credentials()` for multi-tenant app | code-puppy | 1 hour |
| B.6 | Add tests for multi-tenant credential flow | code-puppy | 1 hour |
| B.7 | Deploy to staging, verify for 1 week | Tyler + code-puppy | 1 week |
| B.8 | Deploy to production | Tyler | 30 min |
| B.9 | Remove per-tenant app registrations (after 2-week soak) | Tyler | 1 hour |

### Phase C: UAMI Zero-Secrets (Future)

| # | Task | Owner | Effort |
|---|------|-------|--------|
| C.1 | Create UAMI `mi-governance-platform` | Tyler (Azure CLI) | 15 min |
| C.2 | Assign UAMI to App Service | Tyler (Bicep/CLI) | 15 min |
| C.3 | Add FIC on multi-tenant app (issuer=HTT, subject=UAMI) | Tyler (Azure CLI) | 15 min |
| C.4 | Update `oidc_credential.py` — single client_id from settings | code-puppy | 1 hour |
| C.5 | Update `infrastructure/modules/app-service.bicep` — UAMI | code-puppy | 30 min |
| C.6 | Update `.env.example` — new OIDC settings | code-puppy | 15 min |
| C.7 | Tests for UAMI credential flow | code-puppy | 1 hour |
| C.8 | Deploy to staging, soak for 2 weeks | Tyler | 2 weeks |
| C.9 | Deploy to production, flip `USE_OIDC_FEDERATION=true` | Tyler | 30 min |
| C.10 | Remove client secret from Key Vault | Tyler | 15 min |

---

## Key Differences: Old OIDC vs. New OIDC

| Aspect | Old (Broken) | New (Option 3) |
|--------|-------------|----------------|
| App registrations | 5 per-tenant apps | 1 multi-tenant app |
| FIC location | Each tenant's app | Multi-tenant app in HTT |
| MI token audience | `api://AzureADTokenExchange` | `api://AzureADTokenExchange` |
| MI token issuer | HTT's Entra ID | HTT's Entra ID |
| Why it works | ❌ Entra ID rejects own tokens as FIC assertions | ✅ FIC is on the same-tenant app, assertion exchanges for foreign tenant tokens |

The critical difference: the Federated Identity Credential must be on an app
in the **same tenant** as the Managed Identity. Then `ClientAssertionCredential`
can exchange the MI token for access tokens in **any tenant** where the multi-tenant
app has admin consent.

---

## Calendar Reminders (for Phase A)

The **single** client secret (on the multi-tenant HTT app) expires **2027-03-04**.

| Event | Date | Action |
|-------|------|--------|
| Phase B evaluation | 2026-07-01 | Decide if multi-tenant app migration is worth it |
| Secret rotation warning | 2027-01-04 | Rotate the client secret (60 days before expiry) |
| **Secret expiry** | **2027-03-04** | **HARD DEADLINE — production outage if not rotated** |

> **Better:** Set up Azure Key Vault expiry notifications via Action Group instead of calendar reminders.

---

## Related Documents

- [Enable Secret Fallback Runbook](./runbooks/enable-secret-fallback.md)
- [OIDC Federation Setup (legacy)](./runbooks/oidc-federation-setup.md)
- [Deployment Guide](./DEPLOYMENT.md)
- [Security Implementation](../SECURITY_IMPLEMENTATION.md)
