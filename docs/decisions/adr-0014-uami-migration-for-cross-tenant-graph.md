---
status: proposed
date: 2026-05-27
decision-makers: Solutions Architect 🏛️ (solutions-architect-7f4042), Tyler Granlund
consulted: Security Auditor (co-sign pending on STRIDE table), code-puppy (implementation feasibility)
informed: Pack Leader, Planning Agent, Release Gate Arbiter, Engineering, Azure subscription admins for HTT/BCC/FN/TLL/DCE
relates-to: bd ct-f9p, bd ct-y47, bd ct-59n, bd ct-90r, bd ct-jxe, PR #63, ADR-0007 (auth evolution), ADR-0012 (CI/CD OIDC identity model)
supersedes: none (extends ADR-0007 and the OIDC sections of ADR-0012)
---

# ADR-0014: UAMI + Multi-Tenant App for Cross-Tenant Graph Access

## Status

**Proposed** — awaiting Security Auditor co-sign on STRIDE table and Tyler's go/no-go on the staging cut-over window.

## Context and Problem Statement

The Control Tower production app (`app-governance-prod`, Linux B1, West US 2) needs to read Microsoft Graph data (MFA state, users, sign-in logs, security alerts) from five Entra ID tenants:

| Tenant | ID |
|---|---|
| **HTT-CORE** (home) | `0c0e35dc-188a-4eb3-b8ba-61752154b407` |
| BCC | `b5380912-79ec-452d-a6ca-6d897b19b294` |
| FN | `98723287-044b-4bbb-9294-19857d4128a0` |
| TLL | `3c7d2bf3-b597-4766-b5cb-2b489c2904d6` |
| DCE | `ce62e17d-2feb-4e67-a115-8ea4af68da30` |

Two prior auth attempts have failed or proven unsustainable:

1. **Per-tenant client secrets in Key Vault** (currently restored via PR #63 as the operational fallback). Works, but: (a) 5 secrets to rotate every 2 years, (b) ct-jxe burned us — the production secret expired 2026-04-29 and was undetected for 20 days, causing a silent data outage, (c) any future onboarded tenant adds another rotating secret.
2. **System-Assigned MI + per-tenant Federated Identity Credentials** (`USE_OIDC_FEDERATION=true`). Fails with **AADSTS700236**. Root cause: Microsoft's Workload Identity Federation explicitly prohibits using Entra-ID-issued tokens (which SAMI tokens are) as FIC assertions against an app in a different tenant. This is a hard platform limitation, not a config bug. See `research/aadsts700236-cross-tenant-federation/README.md`.

What **changed in June 2025**: Microsoft GA'd the ["Configure an application to trust a managed identity"](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-config-app-trust-managed-identity) pattern, which permits **same-tenant** UAMI → app FIC. Combined with a **multi-tenant** app registration (`signInAudience: AzureADMultipleOrgs`) that has been admin-consented into each foreign tenant, this gives us secretless cross-tenant Graph access through the supported envelope.

A pre-existing multi-tenant app registration in the HTT home tenant (`1e3e8417-49f1-4d08-b7be-47045d8a12e9`) is already admin-consented in HTT/BCC/FN/TLL and is the holder of the current shared client secret (PR #63). DCE consent is the only outstanding tenant (per the enable-secret-fallback runbook). The UAMI Bicep module (`infrastructure/modules/uami.bicep`) is already authored; `app/core/uami_credential.py` and the `use_uami_auth` config flag are already wired in `app/api/services/azure_client.py`. **This ADR is an execution/cut-over decision, not a greenfield design.**

## Decision Drivers

- **Eliminate rotation toil and rotation-induced outages** (driver from ct-jxe).
- **Zero secrets at runtime** for the cross-tenant Graph path (security posture, GDPR/SOC2 narrative).
- **Stay inside Microsoft's supported envelope** — no clever cross-tenant tricks; AADSTS700236 was the bill for ignoring this.
- **Reuse what already exists** — UAMI Bicep module, `UAMICredentialProvider`, `use_uami_auth` flag, and the multi-tenant app `1e3e8417-…` are all in place.
- **Preserve the secret fallback** for at least 30 days post-cut-over (rollback in <2 min via `USE_UAMI_AUTH=false`).
- **Auditability** — `/health/detailed` must surface `auth_mode: "uami"` (or equivalent) so a silent regression to secret mode is visible at a glance (extends the ct-jxe credential probe).
- **No second multi-tenant app sprawl** — one app reg per *purpose*, per ADR-0012; this is the Graph/runtime app and is distinct from the CI/CD deployment app registrations.

## Considered Options

1. **UAMI + multi-tenant app `1e3e8417-…` + same-tenant FIC** (recommended)
2. **Stay on client secrets indefinitely** (current PR #63 state)
3. **Certificate-based credential on the multi-tenant app** (cert in Key Vault, auto-renewed)
4. **Azure Lighthouse for ARM + per-tenant SP for Graph** (already evaluated and rejected in ct-59n)
5. **GitHub Actions OIDC at sync-time** (run Graph syncs as scheduled GHA workflows instead of from App Service)

## Decision Outcome

**Chosen: Option 1 — UAMI + multi-tenant app `1e3e8417-…` + same-tenant FIC.**

Rationale: it is the only option that simultaneously (a) eliminates all runtime client secrets for the Graph path, (b) stays inside Microsoft's documented and GA'd envelope, (c) reuses the multi-tenant app that already has admin consent in 4 of 5 tenants, and (d) requires zero new application code (the Phase-C scaffolding is already merged — this is wiring + provisioning).

The two non-recommended options that deserve explicit notes:

- **Option 5 (GHA OIDC at sync-time)** is architecturally clean but trades a real production capability for a hypothetical one: it forces all sync to run in CI, breaks ad-hoc/on-demand refresh from the running app, and adds GHA as a runtime dependency for what is currently an App Service workload. Worth revisiting if/when we move sync to a Container Apps job model, but not now.
- **Option 4** stays rejected (ct-59n closure): Lighthouse is ARM-only — it cannot authorize Microsoft Graph calls — so it does not solve the problem under decision.

### Consequences

**Good**
- Zero client secrets in the runtime credential chain for cross-tenant Graph calls.
- No rotation calendar for the Graph path (UAMI tokens are minted per-call from IMDS; FIC has no expiry).
- ct-jxe class of incident becomes impossible for this path (no secret to expire silently).
- Single audit surface: one multi-tenant app reg, one UAMI, one FIC.
- Onboarding a 6th tenant is now a 1-step operation (admin consent URL), not "provision a new app reg + secret + KV entry."

**Bad**
- Initial cut-over requires Global Admin in DCE (still outstanding from PR #63 runbook step) — coordination cost.
- Blast radius if FIC is misconfigured: a wrong `subject` value on the FIC silently breaks all 5 tenants at once. Mitigated by staged rollout + secret fallback retention.
- UAMI is in a single resource group (`rg-governance-production`); accidental deletion = total auth outage. Mitigated by Azure resource lock (`CanNotDelete`) on the UAMI resource — see acceptance criteria.
- Multi-tenant app reg `1e3e8417-…` becomes a high-value target: compromise grants Graph access to all 5 tenants. Same blast radius as today's shared secret, but the credential is now non-exfiltrable from runtime memory (no static secret to steal).

**Neutral**
- Existing per-tenant app registrations (BCC/FN/TLL/DCE) become dead code after cut-over + 30-day soak. Cleanup is a follow-up bd issue, not a blocker.

### Confirmation

The decision is confirmed working when **all** of the following hold for 7 consecutive days in production:

1. `GET /health/detailed` returns `azure_credential_probe.auth_mode: "uami"` (or `"oidc"` if the existing probe doesn't yet distinguish) and `status: "configured"` for at least one probed tenant.
2. `GET /healthz/data` shows `fresh` (green) for `mfa`, `costs`, `identity` snapshots for all 5 tenants.
3. The credential probe in `app/core/azure_credential_probe.py` has flipped from `auth_mode: "secret"` to `auth_mode: "uami"`.
4. `az keyvault secret show --vault-name kv-gov-prod --name <shared-mt-app-secret>` shows the secret value has NOT been read since cut-over (Key Vault diagnostic logs, `SecretGet` event count = 0 over the soak window).
5. The architecture fitness tests in `tests/architecture/test_uami_auth.py` (to be added — see Fitness Functions below) pass in CI.

## STRIDE Security Analysis

> **Security Auditor co-sign required before status flips from Proposed → Accepted.**

| Threat Category | Risk Level | Mitigation |
|-----------------|-----------|------------|
| **Spoofing** | **Low** | UAMI principal ID is the FIC `subject`; only the IMDS endpoint inside `app-governance-prod` can mint a token with that subject. No static credential exists to phish or replay. Token audience is pinned to `api://AzureADTokenExchange`. |
| **Tampering** | **Low** | Assertion JWTs are signed by Microsoft's IMDS token service (not by us); they're short-lived (≤1h) and audience-bound. The app's Graph permissions are admin-consented per tenant — adding scopes requires re-consent and is auditable in each tenant's Entra logs. UAMI resource has `CanNotDelete` resource lock. |
| **Repudiation** | **Low** | Every token exchange is logged in the home tenant's Entra sign-in logs (`Workload identities → Service principal sign-ins`) AND each target tenant's logs for the resulting Graph access. UAMI diagnostic settings stream `AuditEvent` to Log Analytics (enabled in `uami.bicep`). |
| **Information Disclosure** | **Medium → Low post-mitigation** | Removes the largest disclosure surface (no client secrets in env vars, KV, app memory, or process dumps). Residual risk: the multi-tenant app's Graph permissions (`Directory.Read.All`, `Reports.Read.All`, `SecurityEvents.Read.All`, `Domain.Read.All`) are broad — compromise of the App Service host = full Graph read in 5 tenants. Mitigation: least-privilege review of Graph perms during cut-over; consider scoping `Directory.Read.All` → `User.Read.All` if usage analysis confirms. |
| **Denial of Service** | **Medium** | Single UAMI = single point of failure for all cross-tenant auth. If the UAMI is deleted, deactivated, or IMDS becomes unreachable, all 5 tenants' Graph access fails simultaneously (vs. today's per-tenant secret model where one bad secret breaks one tenant). Mitigations: (a) `CanNotDelete` resource lock on UAMI, (b) retain secret fallback for 30 days post-cut-over with `USE_UAMI_AUTH=false` rollback, (c) circuit breaker already exists in `app/core/circuit_breaker.py` and will degrade per-tenant rather than crash. |
| **Elevation of Privilege** | **Low** | FIC `subject` is the UAMI's principal (object) ID — a 36-char GUID that cannot be forged; the issuer must be `https://login.microsoftonline.com/0c0e35dc-188a-4eb3-b8ba-61752154b407/v2.0` (HTT tenant exactly). An attacker would need to (a) compromise HTT tenant Entra admin AND (b) the UAMI resource to forge a valid assertion. Cross-tenant escalation is bounded by the admin-consented scopes in each foreign tenant, which are auditable and revocable per-tenant. |

**Overall Security Posture:** Net improvement. Eliminates the single largest live risk (silent secret expiry → outage) and the largest static disclosure surface (secrets at rest). Introduces one new concentrated DoS surface (the UAMI itself), which is mitigated by resource locks + retained fallback path. **Recommend Accepted pending Security Auditor sign-off on the Graph permission scope review (the `Directory.Read.All` line item above).**

## Implementation Plan

### Phase 1 — Pre-flight (Day 0, ~30 min, can be done now)

1. Verify DCE admin consent is complete on `1e3e8417-…`:
   ```bash
   # The PR #63 runbook lists this as the only outstanding item
   open "https://login.microsoftonline.com/ce62e17d-2feb-4e67-a115-8ea4af68da30/adminconsent?client_id=1e3e8417-49f1-4d08-b7be-47045d8a12e9"
   ```
2. Confirm secret fallback is healthy (must work before we replace it):
   ```bash
   curl -s https://app-governance-prod.azurewebsites.net/health/detailed | jq '.azure_credential_probe'
   # Expect: { "status": "configured", "auth_mode": "secret", ... }
   ```

### Phase 2 — Bicep deployment of UAMI (Day 1, ~15 min)

The `infrastructure/modules/uami.bicep` module exists. Wire it into `main.bicep` (or `deploy-governance-infrastructure.bicep`) and deploy to **staging first**:

```bash
# Staging
az deployment group create \
  --resource-group rg-governance-staging \
  --template-file infrastructure/main.bicep \
  --parameters @infrastructure/parameters.staging.json \
  --parameters deployUami=true

# Capture outputs
UAMI_CLIENT_ID=$(az identity show -n mi-control-tower -g rg-governance-staging --query clientId -o tsv)
UAMI_PRINCIPAL_ID=$(az identity show -n mi-control-tower -g rg-governance-staging --query principalId -o tsv)
UAMI_RESOURCE_ID=$(az identity show -n mi-control-tower -g rg-governance-staging --query id -o tsv)

# Apply resource lock (DoS mitigation from STRIDE table)
az lock create --name uami-no-delete --lock-type CanNotDelete \
  --resource-group rg-governance-staging \
  --resource-name mi-control-tower \
  --resource-type Microsoft.ManagedIdentity/userAssignedIdentities
```

### Phase 3 — Assign UAMI to App Service (Day 1, ~5 min)

```bash
az webapp identity assign \
  --name app-governance-staging \
  --resource-group rg-governance-staging \
  --identities "$UAMI_RESOURCE_ID"

# Verify both SAMI + UAMI are present (do NOT remove SAMI yet — Key Vault MI still binds to it)
az webapp identity show -n app-governance-staging -g rg-governance-staging
```

### Phase 4 — Create the same-tenant FIC on `1e3e8417-…` (Day 1, ~5 min) — **CRITICAL STEP**

```bash
MT_APP_ID="1e3e8417-49f1-4d08-b7be-47045d8a12e9"
MT_APP_OBJECT_ID=$(az ad app show --id $MT_APP_ID --query id -o tsv)

# Issuer = HTT home tenant. Subject = UAMI principal ID. Audience pinned.
az ad app federated-credential create \
  --id "$MT_APP_OBJECT_ID" \
  --parameters "{
    \"name\": \"control-tower-uami-staging\",
    \"issuer\": \"https://login.microsoftonline.com/0c0e35dc-188a-4eb3-b8ba-61752154b407/v2.0\",
    \"subject\": \"$UAMI_PRINCIPAL_ID\",
    \"description\": \"Trust Control Tower staging UAMI for cross-tenant Graph access (ADR-0014)\",
    \"audiences\": [\"api://AzureADTokenExchange\"]
  }"

# Verify
az ad app federated-credential list --id "$MT_APP_OBJECT_ID" \
  --query "[?name=='control-tower-uami-staging']" -o table
```

**Exact required values** (no substitutions):
- **issuer**: `https://login.microsoftonline.com/0c0e35dc-188a-4eb3-b8ba-61752154b407/v2.0`
- **subject**: the UAMI's `principalId` (object ID) — a GUID; **NOT** the clientId
- **audiences**: `["api://AzureADTokenExchange"]` — exact string, single entry

### Phase 5 — Flip the app setting on staging (Day 1, ~2 min)

```bash
az webapp config appsettings set \
  --name app-governance-staging \
  --resource-group rg-governance-staging \
  --settings \
    USE_UAMI_AUTH=true \
    USE_OIDC_FEDERATION=false \
    UAMI_CLIENT_ID=$UAMI_CLIENT_ID \
    AZURE_MANAGED_IDENTITY_CLIENT_ID=$UAMI_CLIENT_ID

az webapp restart -n app-governance-staging -g rg-governance-staging
```

### Phase 6 — Staging soak (Days 1–8)

For 7 days, monitor:
- `/health/detailed` → `auth_mode` field
- `/healthz/data` → per-tenant freshness
- Application Insights traces for `ClientAssertionCredential` errors
- Key Vault diagnostic logs: `SecretGet` event count for the shared MT secret should drop to **0** in staging

Acceptance to proceed to production: all 5 tenants returning data, no auth errors in App Insights, zero KV secret reads for the shared MT secret.

### Phase 7 — Production cut-over (Day 8, ~30 min)

Repeat Phases 2–5 against `rg-governance-production` / `app-governance-prod`. Use a **separate FIC** named `control-tower-uami-prod` (do NOT reuse the staging FIC — different UAMI principal).

### Phase 8 — Production soak + cleanup (Days 8–38)

After 30 days clean in prod:
- Delete the staging FIC (`control-tower-uami-staging`)
- Disable (do not delete) the shared multi-tenant client secret in Key Vault
- File bd cleanup issue for per-tenant app registrations (BCC/FN/TLL/DCE) — separate decision

### Rollback Plan

Single setting, <2 min RTO:

```bash
az webapp config appsettings set \
  --name app-governance-prod \
  --resource-group rg-governance-production \
  --settings USE_UAMI_AUTH=false USE_OIDC_FEDERATION=false

az webapp restart -n app-governance-prod -g rg-governance-production
```

This restores PR #63 secret-mode. The secret remains live in Key Vault for the entire 30-day soak — do **not** disable it until Phase 8.

## Acceptance Criteria (Per-Step Verification)

| Step | Verification command | Expected result |
|------|---------------------|-----------------|
| UAMI exists | `az identity show -n mi-control-tower -g rg-governance-production` | Returns JSON with `clientId`, `principalId` |
| Resource lock applied | `az lock list --resource-group rg-governance-production --query "[?name=='uami-no-delete']"` | One entry, `level=CanNotDelete` |
| UAMI assigned to App Service | `az webapp identity show -n app-governance-prod -g rg-governance-production --query "userAssignedIdentities"` | Contains UAMI resource ID |
| FIC created on multi-tenant app | `az ad app federated-credential list --id $MT_APP_OBJECT_ID --query "[?subject=='$UAMI_PRINCIPAL_ID']"` | One entry, issuer = HTT v2.0 endpoint |
| App setting flipped | `az webapp config appsettings list -n app-governance-prod -g rg-governance-production --query "[?name=='USE_UAMI_AUTH'].value" -o tsv` | `true` |
| Probe reports UAMI | `curl -s https://app-governance-prod.azurewebsites.net/health/detailed \| jq '.azure_credential_probe.auth_mode'` | `"uami"` (or `"oidc"` if probe label unchanged) |
| Data fresh, all tenants | `curl -s https://app-governance-prod.azurewebsites.net/healthz/data \| jq '.tenants[] \| {tenant, status}'` | All 5 tenants `status: "fresh"` |
| No secret reads | Azure Portal → Key Vault → `kv-gov-prod` → Diagnostic logs → filter `OperationName == "SecretGet"` AND `SecretName == "<mt-app-secret>"` over last 7 days | Count = 0 |
| Sign-in audit shows UAMI | Entra ID → Sign-in logs → Service principal sign-ins → filter `appId == "1e3e8417-…"` AND `authenticationProtocol == "Federated"` | Recent successful entries |

## Fitness Functions

To be added by code-puppy in `tests/architecture/test_uami_auth.py`:

```python
"""Architecture fitness tests for ADR-0014 (UAMI migration)."""
import os
import re
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parents[2]

def test_uami_bicep_module_exists():
    """ADR-0014 requires the UAMI Bicep module to be checked in."""
    assert (REPO / "infrastructure/modules/uami.bicep").is_file()

def test_uami_credential_provider_exists():
    """ADR-0014 requires the UAMI credential provider to be importable."""
    from app.core.uami_credential import UAMICredentialProvider  # noqa
    assert UAMICredentialProvider is not None

def test_use_uami_auth_flag_in_config():
    """ADR-0014 introduces USE_UAMI_AUTH; config must expose it."""
    cfg = (REPO / "app/core/config.py").read_text()
    assert "use_uami_auth" in cfg
    assert "USE_UAMI_AUTH" in cfg

def test_azure_client_routes_to_uami_when_flag_set():
    """When use_uami_auth=True, AzureClientManager must dispatch to UAMI path."""
    src = (REPO / "app/api/services/azure_client.py").read_text()
    assert "use_uami_auth" in src
    assert "get_uami_provider" in src

def test_no_client_secret_in_uami_path():
    """The UAMI credential code must not import or use ClientSecretCredential."""
    src = (REPO / "app/core/uami_credential.py").read_text()
    assert "ClientSecretCredential" not in src, (
        "UAMI path must not use ClientSecretCredential — that defeats the purpose"
    )

def test_fic_subject_is_principal_id_not_client_id():
    """Documentation must warn that FIC subject is the principalId, not clientId."""
    adr = (REPO / "docs/decisions/adr-0014-uami-migration-for-cross-tenant-graph.md").read_text()
    # Both must be mentioned and the distinction called out
    assert "principalId" in adr or "principal ID" in adr
    assert "NOT" in adr and "clientId" in adr

@pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_AZURE_TESTS"),
    reason="Live test — requires az login + WEBSITE_SITE_NAME or staging",
)
def test_no_secret_get_on_mt_app_secret_post_cutover():
    """Post-cutover, the shared multi-tenant client secret must not be read.
    Read Key Vault diagnostic logs and assert SecretGet count is 0 for the
    last 24h on the named secret. Implementation deferred to code-puppy.
    """
    pytest.skip("Implement against Log Analytics KQL after cut-over")
```

## Pros and Cons of the Options

### Option 1: UAMI + multi-tenant app `1e3e8417-…` + same-tenant FIC ✅ chosen

- **Good**, because zero secrets in the runtime credential chain.
- **Good**, because it's the only option inside Microsoft's documented & GA'd supported envelope for this use case.
- **Good**, because all the application code already exists (`UAMICredentialProvider`, `use_uami_auth` flag, routing in `AzureClientManager`, `uami.bicep` module).
- **Good**, because 4 of 5 tenants already have admin consent on `1e3e8417-…`.
- **Good**, because rollback is a single env-var flip (<2 min RTO).
- **Bad**, because one misconfigured FIC subject silently breaks all 5 tenants. Mitigated by staged rollout + 30-day fallback retention.
- **Bad**, because the UAMI becomes a concentrated DoS surface. Mitigated by `CanNotDelete` resource lock.

### Option 2: Stay on client secrets indefinitely

- **Good**, because it works today (PR #63).
- **Bad**, because ct-jxe will recur — secret expiry is a when-not-if outage.
- **Bad**, because ~10h/year rotation toil and one Global-Admin-required step per rotation.
- **Bad**, because secrets at rest in KV + cached in app memory = real disclosure surface.
- **Bad**, because every new tenant onboarding adds another rotating secret.

### Option 3: Certificate on the multi-tenant app (cert in Key Vault, auto-renewed)

- **Good**, because KV can auto-rotate certs (true zero-touch).
- **Good**, because same support envelope as secrets — no new platform risk.
- **Neutral**, because cert rotation is operationally smoother than secret rotation but still has a rotation event.
- **Bad**, because cert material still exists at rest in KV → still a static credential to protect.
- **Bad**, because more setup complexity than Option 1 (KV cert lifecycle policy, app reg cert upload automation) for a strictly weaker security outcome.
- **Bad**, because Option 1 dominates this option on every axis except "familiarity."

### Option 4: Azure Lighthouse for ARM + per-tenant SP for Graph

- **Good**, because Lighthouse is zero-secret for ARM access.
- **Bad** (disqualifying), because **Lighthouse does not authorize Microsoft Graph API calls** — this is an ARM-only delegation. The problem under decision is Graph access. Lighthouse cannot solve it.
- **Bad**, because already evaluated and retired in ct-59n (April 2026) — zero delegations were ever wired up across 5 tenants, code path and `tenants.use_lighthouse` column removed in migration `011_drop_tenant_use_lighthouse.py`.
- **Verdict**: still rejected. Lighthouse remains a valid future option for ARM-only operations (cost, resource inventory) but is orthogonal to this decision.

### Option 5: GitHub Actions OIDC at sync-time

- **Good**, because GHA OIDC → multi-tenant app is the same secretless pattern using a different identity source. ADR-0012 already uses this for CI/CD deploys.
- **Good**, because it removes UAMI/IMDS as a runtime dependency.
- **Bad**, because it forces every Graph sync to run inside a GHA workflow — breaks the App Service scheduler (`app/core/riverside_scheduler.py`) and ad-hoc admin-triggered refresh.
- **Bad**, because adds GHA as a hard runtime dependency for production data freshness (GHA outages → stale data).
- **Bad**, because GHA workflow latency (~30–60s cold start per run) is poor UX for on-demand sync.
- **Neutral**, because worth revisiting if/when sync moves to a Container Apps Jobs model — but that's a separate architectural decision, not this one.

## More Information

### Why this ADR exists separately from ADR-0012

ADR-0012 governs the **CI/CD** identity model (GHA → Azure for deploys, with per-environment app registrations). This ADR governs the **runtime cross-tenant Graph** identity model. These are deliberately separate apps, separate FICs, separate blast radii — per the "no second multi-tenant app sprawl" driver above. The CI/CD apps must not be reused for runtime Graph access (different audience, different consent surface, different rotation cadence).

### When to revisit

- If Microsoft deprecates same-tenant UAMI→app FIC (low probability — June 2025 GA).
- If we onboard a 6th+ tenant and the admin-consent friction proves prohibitive (consider switching to per-tenant app reg model only for that outlier).
- If we move sync to Container Apps Jobs (re-evaluate Option 5).
- If Graph permission audit (the STRIDE Information Disclosure line item) reveals we can drop `Directory.Read.All` for narrower scopes.

### References

- **bd**: ct-f9p (this ADR), ct-y47 (UAMI infrastructure prep), ct-59n (Lighthouse retirement), ct-90r (CI/CD OIDC), ct-jxe (silent secret expiry incident)
- **PR**: #63 (secret fallback restoration)
- **Research**: `research/aadsts700236-cross-tenant-federation/` (README.md, recommendations.md, analysis.md)
- **Roadmap**: `docs/AUTH_TRANSITION_ROADMAP.md` (Phase C = this ADR)
- **Runbook**: `docs/runbooks/enable-secret-fallback.md` (current fallback / rollback target)
- **Prior ADRs**: ADR-0007 (auth evolution), ADR-0012 (CI/CD OIDC identity model)
- **Microsoft docs** (cited transitively via research/):
  - [Workload Identity Federation concepts](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation) (rev. 2025-04-09) — source of the AADSTS700236 rule
  - [Configure an application to trust a managed identity](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-config-app-trust-managed-identity) (June 2025 GA) — the supported envelope this ADR depends on
- **Code under test**: `app/core/uami_credential.py`, `app/core/oidc_credential.py` (legacy), `app/api/services/azure_client.py`, `app/core/azure_credential_probe.py`, `infrastructure/modules/uami.bicep`

---

**Template Version:** MADR 4.0 (September 2024) with STRIDE Security Analysis
**Last Updated:** 2026-05-27
**Maintained By:** Solutions Architect 🏛️ (solutions-architect-7f4042)
