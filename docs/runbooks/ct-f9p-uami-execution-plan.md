# ct-f9p — UAMI zero-secret migration: execution plan

> **Type:** execution plan for bd `ct-f9p` (P2). This is the *sequencing +
> current-state* layer on top of the detailed command runbook
> [`phase-c-zero-secrets.md`](./phase-c-zero-secrets.md). It does not duplicate
> those commands — it tells you, for *our* environment, what exists today, what
> to create, in what order, and how to roll back.
>
> **Prepared:** 2026-06-02 by Richard (`code-puppy-1725d8`) using a live `az`
> session (HTT-CORE, `tyler.granlund-admin`). All "current state" rows below
> were verified live, not assumed.

## Goal

Replace per-tenant **client secrets** (Phase A) with a **User-Assigned Managed
Identity (UAMI) + Federated Identity Credential (FIC)** so cross-tenant Graph
auth carries **zero secrets** — eliminating the ~10 hrs/year secret-rotation
overhead (`AUTH_TRANSITION_ROADMAP.md`).

## Current state (live-verified 2026-06-02)

| Thing | State | Source |
|---|---|---|
| Prod app | `app-governance-prod` (rg-governance-production), Running | `az webapp list` |
| Prod identity | **SystemAssigned only** (principalId `8ff7caa7-566b-428f-b76e-b122ebd43365`); no UAMI | `az webapp identity show` |
| Staging app | `app-governance-staging-xnczpwyv` (rg-governance-staging) | `az webapp list` |
| Multi-tenant app reg | `Riverside-Capital-PE-Governance-Platform` = `1e3e8417-49f1-4d08-b7be-47045d8a12e9` | `az ad app list` |
| FICs on that app reg | 6, **all GitHub-Actions** (`token.actions.githubusercontent.com`); **no UAMI FIC** | `az ad app federated-credential list` |
| Prod auth mode | `USE_OIDC_FEDERATION=false`, `USE_UAMI_AUTH` unset, `USE_MULTI_TENANT_APP` unset -> **Phase A** | `az webapp config appsettings list` |
| Per-tenant secrets | 5 in `kv-gov-prod`: `{tenant-guid}-client-secret` (HTT/BCC/FN/TLL/DCE) + `jwt-secret-key` | `az keyvault secret list` |
| Code support | `app/core/oidc_credential.py` already implements ManagedIdentity/WorkloadIdentity/Dev paths; config flags `USE_UAMI_AUTH`,`UAMI_CLIENT_ID`,`UAMI_PRINCIPAL_ID`,`FEDERATED_IDENTITY_CREDENTIAL_ID` exist | repo |
| HTT-CORE tenant id | `0c0e35dc-188a-4eb3-b8ba-61752154b407` | `az account show` |

### Proven in-org template

`groups-hub` **already runs this exact pattern**: UAMI `uami-prod-groupshub-graph`
(clientId `06760cef-2339-49de-a439-5356fcc1b304`) in `rg-groups-hub`, plus a
staging twin. Mirror its naming/role/FIC setup — it's a working reference, not a
greenfield design.

## Acceptance criteria -> status (from bd ct-f9p)

| # | Criterion | Status |
|---|---|---|
| 1 | UAMI created + assigned to app-governance-prod | TODO (this plan, step 1-2) |
| 2 | FIC configured on multi-tenant app reg | TODO (step 3) |
| 3 | OIDCCredentialProvider tested in **staging** with UAMI | TODO (step 5) |
| 4 | `/healthz/data` all tenants fresh on UAMI path | TODO (step 6) |
| 5 | Client secrets removed from `kv-gov-prod` (or deprecated) | TODO (step 8, last) |
| 6 | Runbook reflects UAMI pattern | DONE (PR #72) |

## Execution sequence

> **Staging first, always.** Prove the whole chain in staging before touching
> prod app settings. The `USE_UAMI_AUTH` flag makes cutover a reversible toggle.

1. **Create the UAMI** (ct-f9p.1) — `uami-prod-governance-graph` in
   `rg-governance-production`, and `uami-stg-governance-graph` in
   `rg-governance-staging`. Capture each `clientId` + `principalId`.
   Ref: phase-c-zero-secrets.md Step 1.
2. **Assign the UAMI to the App Services** (ct-f9p.2) — add user-assigned
   identity to `app-governance-prod` and `app-governance-staging-xnczpwyv`
   (coexists with the existing SystemAssigned).
3. **Create the UAMI FIC on app reg `1e3e8417-`** (ct-f9p.3) — issuer
   `https://login.microsoftonline.com/0c0e35dc-188a-4eb3-b8ba-61752154b407/v2.0`,
   subject = the **UAMI principalId**, audience `api://AzureADTokenExchange`.
   One FIC per environment (prod UAMI, staging UAMI). Ref: phase-c Step 2
   ("For Azure App Service").
4. **Grant the UAMI the Graph app-permissions / KV roles it needs** (ct-f9p.4) —
   the multi-tenant app's Graph permissions are already consented (verified for
   the device-sync work); confirm the UAMI can mint app tokens via the FIC, and
   grant `Key Vault Secrets User` on `kv-gov-prod` if the bootstrap still reads
   any KV value. Ref: phase-c Step 3.
5. **Stage the cutover (staging app settings)** (ct-f9p.5) — on
   `app-governance-staging-xnczpwyv` set `USE_UAMI_AUTH=true`,
   `UAMI_CLIENT_ID=<staging uami clientId>`,
   `UAMI_PRINCIPAL_ID=<staging uami principalId>`,
   `AZURE_MULTI_TENANT_APP_ID=1e3e8417-49f1-4d08-b7be-47045d8a12e9`,
   `USE_MULTI_TENANT_APP=true`. Restart. Watch logs for the
   `OIDCCredentialProvider` ManagedIdentity path.
6. **Verify staging** (ct-f9p.6) — `/api/v1/health/data` shows all tenants
   fresh on the UAMI path; no `ClientSecretCredential` in logs. This satisfies
   acceptance #3 + #4 for staging.
7. **Promote to prod** (ct-f9p.7) — repeat step 5's app settings on
   `app-governance-prod` with the prod UAMI ids. Restart. Re-verify
   `/healthz/data`. **Keep the secrets in place** during this step (rollback =
   flip `USE_UAMI_AUTH=false`).
8. **Decommission the secrets** (ct-f9p.8) — only after prod has run clean on
   UAMI for one full sync cycle: delete (or tag `deprecated-`) the 5
   `{tenant-guid}-client-secret` entries in `kv-gov-prod`. `jwt-secret-key`
   stays. Satisfies acceptance #5.

## Risk + rollback

- **Reversible cutover:** every env-flag step is a toggle. If a tenant goes
  stale on the UAMI path, set `USE_UAMI_AUTH=false` and restart — instantly back
  on secrets (which is why step 8 is last and gated on a clean cycle).
- **Don't delete secrets early.** Steps 1-7 add capability without removing the
  fallback. Only step 8 is destructive, and it's recoverable from `kv-gov-prod`
  soft-delete.
- **HTT/DCE shared app reg:** HTT and DCE share `1e3e8417-` (ct-1m0). One UAMI +
  one FIC covers both — no per-tenant FIC needed for the shared pair.
- **Per-tenant secret semantics:** confirm during step 1 whether the 5
  `{tenant-guid}-client-secret` values are 5 distinct app-reg secrets or the
  same secret stored per tenant; it changes nothing in the UAMI path (which
  uses none of them) but matters for the step-8 cleanup audit.

## Ownership

Steps 1-8 are **Azure-admin operations** — Tyler-owned (creating identities,
FICs, app-settings on prod). A code-agent can: prep/verify current state (done),
draft the per-step commands from phase-c-zero-secrets.md, and validate
`/healthz/data` after each cutover. The actual identity/FIC/app-setting
mutations should be run by Tyler (or pair-driven with explicit confirmation),
since they alter production authentication.

See bd sub-issues `ct-f9p.1` .. `ct-f9p.8` for per-step tracking.
