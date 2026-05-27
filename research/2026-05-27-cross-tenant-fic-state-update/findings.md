# Cross-Tenant FIC State Update — 2026-05-27

**Research date:** 2026-05-27
**Prior baseline:** `research/aadsts700236-cross-tenant-federation/` (~April 2026)
**Linked issue:** `bd ct-f9p` — long-term UAMI migration plan
**Researcher:** web-puppy-e0d21e

---

## TL;DR

**Nothing material has changed since the April 2026 research.** The platform limitations that drove the UAMI migration plan (`ct-f9p`) still hold in May 2026. The one win is in the Python SDK: `AZURE_TOKEN_CREDENTIALS=ManagedIdentityCredential` is now officially supported and shortens App Service token-acquisition latency by skipping the IMDS probe — that's a free improvement we should bake into the migration. **Proceed with `ct-f9p` as planned.**

---

## Findings by Question

### Q1 — Has Microsoft relaxed the cross-tenant FIC / Entra-issued-token limitation?

**Answer: NO.** No change since April 2026. — **Confidence: HIGH**

The canonical statement remains on the live docs page (verified 2026-05-27):

> *"Microsoft Entra ID issued tokens may not be used for federated identity flows. The federated identity credentials flow does not support tokens issued by Microsoft Entra ID."*

- Page: <https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation>
- **"Last updated on 04/09/2025"** — identical to the date cited in our April 2026 research. No edits.
- Considerations page (<https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-considerations>) still dated **02/28/2024**.
- Identity-platform breaking-changes page (<https://learn.microsoft.com/en-us/entra/identity-platform/reference-breaking-changes>) — no 2026 entries touching FIC behavior beyond the case-sensitivity change shipped previously (AADSTS700213, not 700236).
- Entra "What's new" through April 2026 (<https://learn.microsoft.com/en-us/entra/fundamentals/whats-new>) — surveyed all 2026 monthly sections (Jan–Apr). Zero entries relaxing cross-tenant FIC with Entra-issued tokens. The only 2026 FIC-adjacent entry is the SAP SuccessFactors provisioning shift to WIF (May 2026), which is SAP-specific and uses Entra-issued tokens going *outbound* to SAP, not the inbound-to-Entra path that breaks for us.

**Implication:** AADSTS700236 will still fire if we try cross-tenant FIC with an MI token as assertion. No new escape hatch.

---

### Q2 — "Configure app to trust a managed identity": SAMI support / 2026 GA changes?

**Answer: Still UAMI-only, still same-tenant. No SAMI support added.** — **Confidence: HIGH**

- Page: <https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-config-app-trust-managed-identity>
- **"Last updated on 06/06/2025"** — unchanged since prior research.
- Verified text (2026-05-27):
  - *"You can only use User-Assigned Managed Identities as a credential."*
  - *"Both the Microsoft Entra app and managed identity must belong to the same tenant."*
  - *"The managed identity must be in the same tenant as the app registration, even if the target resource is in a different cloud."*
  - *"Accessing resources in another tenant is supported"* (i.e., the app can call across tenants, but the trust binding is intra-tenant).

No GA announcement in 2026 for SAMI support on this feature. Our prior research's two hard constraints (UAMI-only, same-tenant trust) are both intact.

---

### Q3 — New Microsoft-recommended patterns for single-tenant App Service → Graph + ARM across 4–5 customer tenants without per-tenant secrets?

**Answer: No new pattern. The canonical answer is still: multi-tenant app + UAMI in home tenant + same-tenant FIC + admin consent in each customer tenant.** — **Confidence: MED-HIGH**

What I checked (2026-05-27):

| Surface | Result |
|---|---|
| Entra What's New (Jan–Apr 2026) | No new cross-tenant Graph access pattern |
| Azure Lighthouse concepts (last updated 2026-01-21) | Still **ARM-only**. Explicit: *"Azure Lighthouse supports requests handled by Azure Resource Manager… Azure Lighthouse doesn't support requests that are handled by an instance of a resource type."* Graph remains out of scope. |
| "Cross-tenant security group sync" (Apr 2026 preview) | Different problem space (Entra-to-Entra object sync), not app-to-Graph access |
| SAP SuccessFactors WIF (May 2026) | Scoped to that connector |
| Azure Files Entra-only identities (May 2026 GA) | Storage-plane only |
| "Customer-Owned Keys" / new multi-tenant MI concept | **Searched, found nothing.** No such feature has shipped. Multi-tenant managed identities are not a thing in 2026. |

The architecture decision in our April 2026 research stands: a UAMI in HTT + one multi-tenant app reg in HTT + FIC binding the UAMI to that app + admin consent per customer tenant is still Microsoft's intended pattern for exactly this scenario. (Lighthouse remains useful as a *complement* for ARM-only ops but cannot replace Graph access.)

---

### Q4 — `azure-identity` Python SDK: `AZURE_CLIENT_ID` vs explicit `ManagedIdentityCredential()`; new `AZURE_TOKEN_CREDENTIALS` env var?

**Answer: YES — `AZURE_TOKEN_CREDENTIALS` is now officially supported AND it has a concrete App Service performance benefit we should adopt.** — **Confidence: HIGH**

Source: `azure-identity` CHANGELOG.md on `main` (verified 2026-05-27): <https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/identity/azure-identity/CHANGELOG.md>

Relevant releases (newest first):

| Version | Date | Relevant change |
|---|---|---|
| 1.26.0b3 | Unreleased | HTTP pipeline policy overrides on credentials (not relevant for us) |
| 1.25.3 | 2026-03-12 | **Bugfix**: expired token could skip refresh when a recent token request was made. Relevant for long-running App Service workers. |
| 1.26.0b2 | 2026-02-11 | `WorkloadIdentityCredential` gained `enable_azure_proxy` (AKS-specific, ignore) |
| 1.25.2 | 2026-02-10 | Bug fixes around `claims` bypassing token cache |
| 1.26.0b1 | 2025-11-07 | AKS-specific FIC binding mode (ignore for App Service) |
| **1.25.1** | **2025-10-06** | **When `AZURE_TOKEN_CREDENTIALS=ManagedIdentityCredential`, `DefaultAzureCredential` skips the IMDS probe and goes straight to token acquisition with full retry logic.** This is the one we want. |
| 1.25.0 | 2025-09-11 | Added `require_envvar=True` kwarg on `DefaultAzureCredential` — refuses to start unless `AZURE_TOKEN_CREDENTIALS` is set. Good for production hygiene. |
| 1.24.0b1 | 2025-07-17 | **Expanded `AZURE_TOKEN_CREDENTIALS` to accept specific credential names**: `EnvironmentCredential`, `WorkloadIdentityCredential`, `ManagedIdentityCredential`, `VisualStudioCodeCredential`, `AzureCliCredential`, `AzurePowershellCredential`, `AzureDeveloperCliCredential`, `InteractiveBrowserCredential` |
| 1.23.0 | 2025-05-13 | **Introduced `AZURE_TOKEN_CREDENTIALS`** with group values `prod` (Env + WIF + MI) and `dev` (CLI creds) |

**`AZURE_CLIENT_ID` behavior — unchanged.** Per the live `DefaultAzureCredential` reference page (<https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.defaultazurecredential>):

> *"The client ID of a user-assigned managed identity. Defaults to the value of the environment variable `AZURE_CLIENT_ID`, if any. If not specified, a system-assigned identity will be used."*

So the established rule still applies: if `AZURE_CLIENT_ID` is set, DAC's MI path uses that UAMI; if unset, it falls through to SAMI. **This is exactly the toggle we need post-UAMI-migration.**

**Recommended SDK configuration after migration (for the App Service):**

```env
# Pin the credential to MI only — skips IMDS probe, faster cold start, deterministic failure modes
AZURE_TOKEN_CREDENTIALS=ManagedIdentityCredential
# Bind DAC's MI path to our UAMI rather than SAMI
AZURE_CLIENT_ID=<uami-client-id>
```

```toml
# pyproject.toml / requirements
azure-identity>=1.25.1,<2  # 1.25.1 introduces the IMDS-probe skip when AZURE_TOKEN_CREDENTIALS=ManagedIdentityCredential
```

Equivalent explicit form (if we prefer not to rely on DAC at all in production — recommended for `oidc_credential.py`):

```python
from azure.identity import ManagedIdentityCredential, ClientAssertionCredential

mi = ManagedIdentityCredential(client_id=settings.uami_client_id)

def get_credential_for_tenant(tenant_id: str) -> TokenCredential:
    return ClientAssertionCredential(
        tenant_id=tenant_id,
        client_id=settings.multitenant_app_id,
        func=lambda: mi.get_token("api://AzureADTokenExchange").token,
    )
```

The explicit `ManagedIdentityCredential(client_id=...)` form remains the safest production pattern — no chain, no IMDS probing surprises, no dev fallback. Use `AZURE_TOKEN_CREDENTIALS` only where we keep DAC (e.g., shared utility code or local dev parity).

---

### Q5 — Active known issues / outages affecting FIC, App Service MI, or Entra cross-tenant token acquisition (May 2026)?

**Answer: No widespread incidents reported.** — **Confidence: MED**

- <https://azure.status.microsoft/en-us/status> on 2026-05-27 shows **"Good"** across all service indicators including Identity, Compute, and App Service. Page is for widespread incidents only.
- Tenant-scoped incidents (Service Health) require sign-in — I cannot verify those from outside. **Recommend running `az rest --method get --uri 'https://management.azure.com/providers/Microsoft.ResourceHealth/events?api-version=2022-10-01'` from the home tenant before cutover.**
- No 2026 entries in the identity-platform breaking-changes log relate to active regressions in FIC, MI, or cross-tenant token acquisition.

Note: the `azure-identity` 1.25.3 (2026-03-12) bugfix for expired-token-skipping-refresh is worth knowing — if we are pinned below 1.25.3 we could see intermittent 401s on long-lived workers. Verify our current pin.

---

## Sources & Credibility (Tier 1 unless noted)

| Source | URL | Last updated | Used for |
|---|---|---|---|
| WIF concepts | https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation | 2025-04-09 | Q1 root statement |
| App trust MI | https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-config-app-trust-managed-identity | 2025-06-06 | Q2 UAMI-only constraint |
| WIF considerations | https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-considerations | 2024-02-28 | Q1 constraints |
| Identity-platform breaking changes | https://learn.microsoft.com/en-us/entra/identity-platform/reference-breaking-changes | live | Q1/Q5 regression check |
| Entra What's new | https://learn.microsoft.com/en-us/entra/fundamentals/whats-new | live (Jan–Apr 2026 visible) | Q1/Q3 new-feature scan |
| Azure Lighthouse cross-tenant | https://learn.microsoft.com/en-us/azure/lighthouse/concepts/cross-tenant-management-experience | 2026-01-21 | Q3 Lighthouse ARM-only confirmation |
| azure-identity CHANGELOG | https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/identity/azure-identity/CHANGELOG.md | live (commits through May 2026) | Q4 SDK changes |
| DefaultAzureCredential ref | https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.defaultazurecredential | live | Q4 AZURE_CLIENT_ID behavior |
| Azure status | https://azure.status.microsoft/en-us/status | live (2026-05-27) | Q5 incidents |
| Azure updates feed | https://azure.microsoft.com/en-us/updates/ | live | Q3 new patterns scan |

All sources are Tier 1 (official Microsoft documentation / SDK source-of-truth). Cross-validated: WIF restriction confirmed across three independent Microsoft pages (concepts, considerations, app-trust-MI). SDK changelog cross-validated against the public `DefaultAzureCredential` reference docs.

---

## Recommendation

**PROCEED with `bd ct-f9p` (UAMI migration) as designed in `research/aadsts700236-cross-tenant-federation/recommendations.md`.** Confidence: **HIGH**.

Justification:
1. Q1/Q2 confirm Microsoft has shipped nothing that obviates the migration. The architectural constraints driving `ct-f9p` are intact.
2. Q3 confirms no new pattern has emerged that would replace the UAMI + multi-tenant app design.
3. The existing fallback (per-tenant client secrets in Key Vault) remains supported but carries the same ~10 hr/year rotation cost flagged in `AUTH_TRANSITION_ROADMAP`.
4. **Free wins from Q4 — fold these into `ct-f9p` acceptance criteria:**
   - Pin `azure-identity>=1.25.1` in `requirements.txt` / `pyproject.toml`.
   - After UAMI is assigned, set on the App Service: `AZURE_TOKEN_CREDENTIALS=ManagedIdentityCredential` and `AZURE_CLIENT_ID=<uami-client-id>`. Skips IMDS probe → faster cold start, more deterministic auth failures.
   - Consider `require_envvar=True` on any `DefaultAzureCredential()` construction in production code paths to prevent silent fallback to dev creds.
   - In `oidc_credential.py`, prefer explicit `ManagedIdentityCredential(client_id=...)` over `DefaultAzureCredential()` for the assertion source — eliminates chain ambiguity entirely.
5. Q5 shows no current platform issues that would make today a bad day to migrate.

**Suggested addendum to `ct-f9p` acceptance criteria** (in addition to the existing 6 items):

- [ ] 7. `requirements.txt` pins `azure-identity>=1.25.1`
- [ ] 8. App Service has `AZURE_TOKEN_CREDENTIALS=ManagedIdentityCredential` and `AZURE_CLIENT_ID=<uami-client-id>` set
- [ ] 9. `oidc_credential.py` uses explicit `ManagedIdentityCredential(client_id=...)` rather than `DefaultAzureCredential()` for the assertion source

No need to delay or reconsider the plan. Microsoft has not made anything better available.
