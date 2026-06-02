# SECRETS OF RECORD — Sanitized Inventory

> **Status:** Skeleton only — Tyler must fill the non-secret details.
> **Owner:** Tyler Granlund
> **Review cadence:** Quarterly and after every credential rotation
> **Filed under:** bd `azure-governance-platform-9lfn`
> **Important:** Do **not** put secret values in this file. Store only pointers,
> owners, access, and rotation metadata.

This document is the canonical non-secret map of where platform credentials
live and who can recover them when Tyler is unavailable.

If a row cannot be safely committed, replace the sensitive value with a pointer
such as `1Password: <vault>/<item>`, `Azure Key Vault: <vault>/<secret>`, or
`GitHub environment secret: <environment>/<secret-name>`.

---

## Completion rules

A credential class is complete when every row has:

1. **Purpose** — what breaks if this credential disappears.
2. **Storage location** — Key Vault path, GitHub secret, 1Password item, portal
   location, or documented manual recovery path.
3. **Primary owner** — usually Tyler until delegated.
4. **Secondary reader/operator** — named human, or `none — risk accepted`.
5. **Last rotation date** and **next rotation due**.
6. **Recovery notes** — how to regenerate or re-grant without exposing values.

---

## Inventory status

| Credential class | Status | Notes |
|---|---|---|
| Azure HTT-CORE subscription access | 🔴 TODO Tyler | Required for deploy/rollback/DR |
| Azure target tenant access x5 | 🔴 TODO Tyler | HTT, BCC, FN, TLL, DCE / Lighthouse / app registrations |
| Azure Key Vault secrets | 🔴 TODO Tyler | `kv-gov-prod`, staging/dev vaults |
| GitHub repository + environment secrets | 🟡 Scaffolded pointers | Actions OIDC, GHCR, Teams webhooks, SQL export; Tyler still must confirm storage/rotation/secondary reader |
| GitHub PAT / GHCR credentials | 🔴 TODO Tyler | GHCR pull/deploy fallback |
| Microsoft 365 / Entra admin access | 🔴 TODO Tyler | Graph, tenant admin, emergency access |
| AWS access | 🔴 TODO Tyler | Only if still required by portfolio ops |
| Pax8 / vendor portals | 🔴 TODO Tyler | Billing/vendor escalation |
| Teams ops webhooks/channels | 🔴 TODO Tyler | Alerting and incident comms |
| Riverside contacts / evidence access | 🔴 TODO Tyler | Compliance consumer/escalation path |

---

## 1. Azure subscriptions and tenant access

| Environment / tenant | Credential or access path | Purpose | Storage location / grant source | Primary owner | Secondary reader/operator | Last rotated/reviewed | Next due | Recovery notes |
|---|---|---|---|---|---|---|---|---|
| HTT-CORE subscription | 🔴 TODO | Host platform resources and emergency rollback | 🔴 TODO | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Include role names needed for rollback |
| HTT tenant | 🔴 TODO | Read governance data | 🔴 TODO | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Include Lighthouse/app-registration path |
| BCC tenant | tenant DB/config + Key Vault secret refs; repo secrets `BCC_CLIENT_ID` / `BCC_TENANT_ID` removed by `ct-90r.13` | Read governance data | App registration / Key Vault, not repo-level GitHub Actions secrets | Tyler | 🔴 TODO / none risk accepted | 2026-05-18 | 🔴 TODO | Do not recreate repo-level BCC ID secrets; use tenant config/DB or environment-scoped config only if needed |
| FN tenant | tenant DB/config + Key Vault secret refs; repo secrets `FN_CLIENT_ID` / `FN_TENANT_ID` removed by `ct-90r.13` | Read governance data | App registration / Key Vault, not repo-level GitHub Actions secrets | Tyler | 🔴 TODO / none risk accepted | 2026-05-18 | 🔴 TODO | Do not recreate repo-level FN ID secrets; use tenant config/DB or environment-scoped config only if needed |
| TLL tenant | tenant DB/config + Key Vault secret refs; repo secrets `TLL_CLIENT_ID` / `TLL_TENANT_ID` removed by `ct-90r.13` | Read governance data | App registration / Key Vault, not repo-level GitHub Actions secrets | Tyler | 🔴 TODO / none risk accepted | 2026-05-18 | 🔴 TODO | Do not recreate repo-level TLL ID secrets; use tenant config/DB or environment-scoped config only if needed |
| DCE tenant | 🔴 TODO | Read governance data | 🔴 TODO | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Include Lighthouse/app-registration path |

---

## 2. Azure Key Vault secrets

| Vault | Secret name | Purpose | Consumed by | Primary owner | Secondary reader/operator | Last rotated | Next due | Recovery notes |
|---|---|---|---|---|---|---|---|---|
| `kv-gov-prod` | 🔴 TODO | Production app/runtime secret | App Service / workflow | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Do not paste value |
| staging vault | `sql-admin-password` | BACPAC staging export fallback | `.github/workflows/bacpac-export.yml` | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Existing workflow probes Key Vault if GitHub secret missing |
| production vault | `sql-admin-password` | BACPAC production export fallback | `.github/workflows/bacpac-export.yml` | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Required before prod schedule is trusted |

---

## 3. GitHub repository and environment secrets

| Scope | Secret / variable | Purpose | Primary owner | Secondary reader/operator | Last rotated | Next due | Recovery notes |
|---|---|---|---|---|---|---|---|
| Repository scope | `AZURE_CLIENT_ID` / `AZURE_TENANT_ID` / `AZURE_SUBSCRIPTION_ID` | Legacy/non-environment GitHub Actions OIDC login | Tyler | 🔴 TODO / none risk accepted | 2026-05-18 | 🔴 TODO | Retained by `ct-90r.11` because `deploy-dev.yml`, drift/topology, and registry-migration workflows still consume repo-level Azure OIDC; remove after those workflows get explicit environment/dedicated identity model |
| Repository scope | `GHCR_PAT` | App Service GHCR pull fallback | Tyler | 🔴 TODO / none risk accepted | 2026-04-10 per RUNBOOK | 🔴 TODO | Retained by `ct-90r.11`; deploy workflows still use it for App Service GHCR pull credentials |
| Repository / environments | `PRODUCTION_TEAMS_WEBHOOK` | Production/deploy/BACPAC alerting | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Rotate in Teams connector if exposed |
| Repository scope | `AZURE_APP_SERVICE_NAME` / `AZURE_RESOURCE_GROUP` secrets and `AZURE_WEBAPP_NAME` / `RESOURCE_GROUP` variables | Removed unused deployment config | Tyler | n/a | 2026-05-18 | n/a | Removed by `ct-90r.11`; active workflows no longer reference these repo-scope names |
| Staging environment | `SQL_ADMIN_PASSWORD` | Staging BACPAC export | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Current stopgap was set from staging app `DATABASE_URL`; document final source |
| Staging environment | `DATABASE_URL` | Scheduled staging database backup (`backup.yml`) | Tyler | GitHub environment secret | 🔴 TODO | 2026-04-30 | Set from staging App Service setting without printing value; validation pending bd `jzpa`. |
| Staging environment | `AZURE_STORAGE_ACCOUNT` | Scheduled staging database backup upload target | Tyler | GitHub environment secret | 🔴 TODO | 2026-04-30 | Set to `stgovstagingxnczpwyv`; validation pending bd `jzpa`. |
| Production environment | `SQL_ADMIN_PASSWORD` | Production BACPAC export | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Prefer Key Vault fallback if possible |
| Production environment | `DATABASE_URL` | Scheduled production database backup (`backup.yml`) | Tyler | GitHub environment secret | 🔴 TODO | 2026-04-30 | Set from production App Service setting without printing value; validation pending bd `jzpa`. |
| Production environment | `AZURE_STORAGE_ACCOUNT` | Scheduled production database backup upload target | Tyler | GitHub environment secret | 🔴 TODO | 2026-04-30 | Set to `stgovprodbkup001`; validation pending bd `jzpa`. |
| Production-backup environment | `AZURE_CLIENT_ID` / `AZURE_TENANT_ID` / `AZURE_SUBSCRIPTION_ID` | Approval-free scheduled production backup OIDC login | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Live environment confirmed by `ct-90r.14`; Azure OIDC subject is `repo:HTT-BRANDS/control-tower:environment:production-backup`. |
| Production-backup environment | `DATABASE_URL` | Scheduled production database backup target | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Must point to production database while environment is `production-backup`; copy pointer only, never value. |
| Production-backup environment | `AZURE_STORAGE_ACCOUNT` / `AZURE_BACKUP_CONTAINER` | Scheduled production backup upload target | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Should mirror production backup storage configuration; do not promote to repo-level secrets. |

---

## 3a. Application secret-bearing environment variables (code-evidenced)

Enumerated by ct-mmq/ct-b0n session (Richard, `code-puppy-1725d8`, 2026-06-02)
directly from `app/core/config.py`. These are the env vars the running app
actually reads — every one is a row Tyler should be able to point at a vault.
**Names and code locations only; no values.** "Storage location" is left as
`TODO (Tyler)` where the codebase can't prove where the value lives.

### Secret-bearing (hold a real credential — must live in a vault)

| Env var | Purpose | Code evidence | Consumed by | Storage location | Last rotated | Next due |
|---|---|---|---|---|---|---|
| `JWT_SECRET_KEY` | Signs internal control-tower JWTs | `config.py` `jwt_secret_key` + explicit `os.getenv` prod guard | `app/core/auth.py` | TODO (Tyler) — prod requires explicit set | 2026-05-18 (`ct-dp9.3`) | TODO (Tyler) |
| `AZURE_AD_CLIENT_SECRET` | Entra SSO app client secret | `config.py` `azure_ad_client_secret` (`AZURE_AD_CLIENT_SECRET`) | Azure AD login flow | TODO (Tyler) | 2026-05-18 (`ct-dp9.1`) | TODO (Tyler) |
| `AZURE_MULTI_TENANT_CLIENT_SECRET` | Phase B shared multi-tenant app secret | `config.py` `azure_multi_tenant_client_secret` | Cross-tenant Graph auth (Phase B) | TODO (Tyler) — should be `@Microsoft.KeyVault(...)` ref | TODO (Tyler) | TODO (Tyler) |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | App Insights telemetry (embeds InstrumentationKey) | `config.py` `os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")` | Telemetry/monitoring | TODO (Tyler) | TODO (Tyler) | TODO (Tyler) |
| `REDIS_URL` | Redis connection (may embed password) | `config.py` `redis_url` (`REDIS_URL`) | Token blacklist / cache backend | TODO (Tyler) — may be unset (in-memory fallback) | TODO (Tyler) | TODO (Tyler) |

### Identity / recovery-critical (not secret values, but needed to recover access)

| Env var | Purpose | Code evidence | Storage / source |
|---|---|---|---|
| `KEY_VAULT_URL` | The vault that backs the secrets above | `config.py` `key_vault_url` | TODO (Tyler) — e.g. `kv-gov-prod` URL |
| `AZURE_AD_CLIENT_ID` / `AZURE_AD_TENANT_ID` | Entra SSO app identity | `config.py` `azure_ad_client_id` / `azure_ad_tenant_id` | App registration (non-secret) |
| `AZURE_MULTI_TENANT_APP_ID` | Phase B multi-tenant app id | `config.py` `azure_multi_tenant_app_id` | App registration (non-secret) |
| `AZURE_MANAGED_IDENTITY_CLIENT_ID` | UAMI client id (system vs user-assigned) | `config.py` `azure_managed_identity_client_id` | Managed identity resource |
| `UAMI_CLIENT_ID` / `UAMI_PRINCIPAL_ID` | Phase C zero-secret UAMI | `config.py` `uami_client_id` / `uami_principal_id` | Managed identity resource |
| `MANAGED_IDENTITY_OBJECT_ID` | UAMI object id for RBAC | `config.py` `managed_identity_object_id` | Managed identity resource |
| `FEDERATED_IDENTITY_CREDENTIAL_ID` | FIC linking UAMI to the app (default `github-actions-federation`) | `config.py` `federated_identity_credential_id` | App registration FIC |

> Phase A/B/C context: per-tenant secrets (Phase A) -> single multi-tenant
> secret (Phase B, `USE_MULTI_TENANT_APP`) -> zero-secret UAMI+FIC (Phase C,
> `USE_UAMI_AUTH`). The long-term goal (bd `ct-f9p`) is Phase C, which retires
> the secret-bearing rows above entirely. Until then they're live.

---

## 4. Microsoft 365 / Entra / Teams

| Credential or role | Purpose | Storage location / admin path | Primary owner | Secondary reader/operator | Last reviewed | Next due | Recovery notes |
|---|---|---|---|---|---|---|---|
| M365 global/admin account(s) | Tenant administration / emergency recovery | 🔴 TODO | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Include break-glass policy pointer |
| Teams ops channel ownership | Incident comms and alert visibility | 🔴 TODO | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Include channel/team URL if safe |
| Teams webhook connector ownership | Alert webhook rotation | 🔴 TODO | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Maps to `PRODUCTION_TEAMS_WEBHOOK` |

---

## 5. Vendor / portfolio systems

| System | Purpose | Storage location / access path | Primary owner | Secondary reader/operator | Last reviewed | Next due | Recovery notes |
|---|---|---|---|---|---|---|---|
| AWS | 🔴 TODO | 🔴 TODO | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Remove row if not used |
| Pax8 | Billing/vendor escalation | 🔴 TODO | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Include account owner and support path |
| Riverside evidence access | Compliance/evidence consumer | 🔴 TODO | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Riverside consumes evidence; platform identity remains HTT-owned |

---

## Repo-evidenced non-secret pointers

These entries are derived from committed workflow/docs references only; they do
not prove the secret exists in GitHub/Azure and do not include secret values.

| Pointer | Evidence | Owner action still needed |
|---|---|---|
| `production-backup` GitHub environment | `.github/workflows/backup.yml`, `RUNBOOK.md`, `ct-90r.14` | Live environment exists and is intentionally retained for approval-free scheduled production backups; Tyler still owns rotation/secondary-reader fields |
| `Bicep Drift Reader` custom role definition | `infrastructure/azure/rbac/bicep-drift-reader.role.json` | Tyler/admin creates/assigns role; bd `rxki` remains open until workflow proof |
| Backup OIDC subject | `RUNBOOK.md`, `ct-90r.14` | Confirmed Entra FIC `github-actions-control-tower-production-backup` with subject `repo:HTT-BRANDS/control-tower:environment:production-backup` |

---

## 5a. domain-intelligence decommission — archived credentials (ct-mql)

The `domain-intelligence` project (separate codebase, Cloudways-hosted) is being
decommissioned (Option A, ct-mql — zero traffic 60+ days). Its Key Vault
`kv-domainiq-prod` (RG `rg-htt-domain-intelligence`, sub HTT-CORE) held **11
secrets**. Before any deletion these were copied vault-to-vault into
`kv-gov-prod` under the `domainiq-archived-` prefix on **2026-06-02** by Richard
(`code-puppy-1725d8`) with zero value exposure (values passed only through a
shell variable, never printed/written/committed).

**Usage check:** none of these 11 secret names are consumed anywhere in the
`control-tower` repo (`rg -i` for `cloudflare-api-token`, `CLOUDWAYS`,
`METRICS-BEARER` all returned 0 files). They belong solely to the
domain-intelligence app.

| Original secret | Archived copy (in `kv-gov-prod`) | Type | Source-side action when app is killed |
|---|---|---|---|
| `API-TOKEN` | `domainiq-archived-API-TOKEN` | app API token | Revoke if issued by a live service |
| `AZURE-AD-CLIENT-SECRET` | `domainiq-archived-AZURE-AD-CLIENT-SECRET` | Entra app secret | Delete the app-reg credential if app-reg is retired |
| `AZURE-CLIENT-SECRET` | `domainiq-archived-AZURE-CLIENT-SECRET` | Entra app secret | Delete the app-reg credential if app-reg is retired |
| `cloudflare-api-token` | `domainiq-archived-cloudflare-api-token` | **EXTERNAL: Cloudflare** | **Revoke at Cloudflare dashboard -> API Tokens.** Deleting the KV copy does NOT revoke Cloudflare access. |
| `CLOUDWAYS-SSH-PASSWORD` | `domainiq-archived-CLOUDWAYS-SSH-PASSWORD` | **EXTERNAL: Cloudways** | **Rotate/disable at Cloudways panel.** KV deletion does NOT change the Cloudways server credential. |
| `CSRF-SECRET-KEY` | `domainiq-archived-CSRF-SECRET-KEY` | app signing key | None (dies with app) |
| `DATABASE-URL` | `domainiq-archived-DATABASE-URL` | PG connection string | Moot once `domainiq-db-prod` is deleted |
| `e2e-api-token` | `domainiq-archived-e2e-api-token` | test API token | Revoke if issued by a live service |
| `JWT-PRIVATE-KEY` | `domainiq-archived-JWT-PRIVATE-KEY` | app JWT signing key | None (dies with app) |
| `METRICS-BEARER-TOKEN` | `domainiq-archived-METRICS-BEARER-TOKEN` | metrics scrape token | None (dies with app) |
| `SESSION-SIGNING-KEY` | `domainiq-archived-SESSION-SIGNING-KEY` | app session key | None (dies with app) |

> **Two are EXTERNAL-service credentials** (`cloudflare-api-token`,
> `CLOUDWAYS-SSH-PASSWORD`). Deleting the Azure Key Vault copy does **not**
> revoke access at Cloudflare/Cloudways — those must be revoked/rotated at the
> source if the domain-intelligence app is genuinely retired.
>
> `kv-domainiq-prod` has **purge protection ON** (90-day soft-delete). The RG
> was deleted 2026-06-02; the vault is now soft-deleted and recoverable until
> **2026-08-31** via `az keyvault recover --name kv-domainiq-prod`. The
> archived copies in `kv-gov-prod` are the durable backstop beyond that window.

---

## 6. Rotation log

| Date | Credential class | Action | Actor | Evidence pointer |
|---|---|---|---|---|
| 2026-05-18 | Obsidian local audit exposure | Repo-side containment started; exact secret rotations tracked as Tyler-only child beads | Richard (`code-puppy-1c7422`) | `ct-dp9`, `docs/security/obsidian-secret-triage-2026-05.md` |
| 2026-05-18 | Azure platform client secret | Rotated visible platform app password credential; updated prod App Service, dev Key Vault, and ignored local env; deleted previous app password | Richard (`code-puppy-1c7422`) | `ct-dp9.1`, `docs/security/obsidian-secret-triage-2026-05.md` |
| 2026-05-18 | Managed tenant app secrets | HTT aligned to rotated platform credential; BCC/FN/TLL/DCE app credentials rotated after tenant-specific admin auth; previous password credentials removed | Richard + Tyler | `ct-dp9.2` |
| 2026-05-18 | JWT signing secrets | Rotated staging + production App Service signing keys and restarted consumers | Richard (`code-puppy-1c7422`) | `ct-dp9.3`, health checks in `docs/security/obsidian-secret-triage-2026-05.md` |
| 2026-05-18 | Dev SQL/admin credential | Rotated dev SQL admin password; updated ignored local SQL env and dev Key Vault connection pointer | Richard (`code-puppy-1c7422`) | `ct-dp9.4` |
| 2026-05-18 | Teams/GitHub environment secrets | No Teams/webhook secret names found; staging SQL admin password rotated; GitHub staging/production/production-backup DB secrets overwritten from current App Service settings | Richard (`code-puppy-1c7422`) | `ct-dp9.6` |

---

## 7. Risk acceptances

Use this only when there is intentionally no secondary reader/operator yet.

| Date | Credential class | Risk | Accepted by | Expiry / review date |
|---|---|---|---|---|
| 2026-05-18 | Obsidian shell history exposure | Local shell history risky lines removed; no remaining tracked secret terms/patterns found | Tyler | `ct-dp9.5` |
| 🔴 TODO | 🔴 TODO | No secondary reader/operator documented | Tyler | 🔴 TODO |

---

## 8. How to update safely

- Commit pointers, not passwords.
- If a value ever lands here by accident, treat it as compromised: rotate it,
  purge it from git history if needed, and file an incident note.
- Keep exact secret values in Key Vault / GitHub secrets / 1Password, never in
  repo docs.
- Update `RUNBOOK.md` once Tyler fills the rows that replace the `🔴 TYLER-ONLY`
  markers.
