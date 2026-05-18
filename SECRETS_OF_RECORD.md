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
| BCC tenant | 🔴 TODO | Read governance data | 🔴 TODO | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Include Lighthouse/app-registration path |
| FN tenant | 🔴 TODO | Read governance data | 🔴 TODO | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Include Lighthouse/app-registration path |
| TLL tenant | 🔴 TODO | Read governance data | 🔴 TODO | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Include Lighthouse/app-registration path |
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
| Repository / environments | `AZURE_CLIENT_ID` | GitHub Actions OIDC login | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Used by `backup.yml`, `bacpac-export.yml`, deploy/drift workflows; recreate federated credential if lost |
| Repository / environments | `AZURE_TENANT_ID` | GitHub Actions OIDC login | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Used by `azure/login@v2`; non-secret-ish but keep with environment config |
| Repository / environments | `AZURE_SUBSCRIPTION_ID` | GitHub Actions OIDC login | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Required by `azure/login@v2`; non-secret-ish but operationally important |
| Repository / environments | `GHCR_PAT` | App Service GHCR pull fallback | Tyler | 🔴 TODO / none risk accepted | 2026-04-10 per RUNBOOK | 🔴 TODO | Confirm actual expiration in GitHub |
| Repository / environments | `PRODUCTION_TEAMS_WEBHOOK` | Production/deploy/BACPAC alerting | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Rotate in Teams connector if exposed |
| Staging environment | `SQL_ADMIN_PASSWORD` | Staging BACPAC export | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Current stopgap was set from staging app `DATABASE_URL`; document final source |
| Staging environment | `DATABASE_URL` | Scheduled staging database backup (`backup.yml`) | Tyler | GitHub environment secret | 🔴 TODO | 2026-04-30 | Set from staging App Service setting without printing value; validation pending bd `jzpa`. |
| Staging environment | `AZURE_STORAGE_ACCOUNT` | Scheduled staging database backup upload target | Tyler | GitHub environment secret | 🔴 TODO | 2026-04-30 | Set to `stgovstagingxnczpwyv`; validation pending bd `jzpa`. |
| Production environment | `SQL_ADMIN_PASSWORD` | Production BACPAC export | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Prefer Key Vault fallback if possible |
| Production environment | `DATABASE_URL` | Scheduled production database backup (`backup.yml`) | Tyler | GitHub environment secret | 🔴 TODO | 2026-04-30 | Set from production App Service setting without printing value; validation pending bd `jzpa`. |
| Production environment | `AZURE_STORAGE_ACCOUNT` | Scheduled production database backup upload target | Tyler | GitHub environment secret | 🔴 TODO | 2026-04-30 | Set to `stgovprodbkup001`; validation pending bd `jzpa`. |
| Production-backup environment | `AZURE_CLIENT_ID` / `AZURE_TENANT_ID` / `AZURE_SUBSCRIPTION_ID` | Approval-free scheduled production backup OIDC login | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Future environment for bd `wnyx`; Azure OIDC subject must be `repo:HTT-BRANDS/control-tower:environment:production-backup`. |
| Production-backup environment | `DATABASE_URL` | Scheduled production database backup target | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Must point to production database while environment is `production-backup`; copy pointer only, never value. |
| Production-backup environment | `AZURE_STORAGE_ACCOUNT` / `AZURE_BACKUP_CONTAINER` | Scheduled production backup upload target | Tyler | 🔴 TODO / none risk accepted | 🔴 TODO | 🔴 TODO | Should mirror production backup storage configuration; do not promote to repo-level secrets. |

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
| `production-backup` GitHub environment | `.github/workflows/backup.yml`, `RUNBOOK.md` | Tyler/admin creates environment, secrets, and OIDC federation; bd `wnyx` remains open until live proof |
| `Bicep Drift Reader` custom role definition | `infrastructure/azure/rbac/bicep-drift-reader.role.json` | Tyler/admin creates/assigns role; bd `rxki` remains open until workflow proof |
| Backup OIDC subject | `RUNBOOK.md` | Configure `repo:HTT-BRANDS/control-tower:environment:production-backup` in Entra federated credential |

---

## 6. Rotation log

| Date | Credential class | Action | Actor | Evidence pointer |
|---|---|---|---|---|
| 2026-05-18 | Obsidian local audit exposure | Repo-side containment started; exact secret rotations tracked as Tyler-only child beads | Richard (`code-puppy-1c7422`) | `ct-dp9`, `docs/security/obsidian-secret-triage-2026-05.md` |
| 2026-05-18 | Azure platform client secret | Rotated visible platform app password credential; updated prod App Service, dev Key Vault, and ignored local env; deleted previous app password | Richard (`code-puppy-1c7422`) | `ct-dp9.1`, `docs/security/obsidian-secret-triage-2026-05.md` |
| 2026-05-18 | Managed tenant app secrets | HTT aligned to rotated platform credential; BCC/FN/TLL/DCE app credentials rotated after tenant-specific admin auth; previous password credentials removed | Richard + Tyler | `ct-dp9.2` |
| 2026-05-18 | JWT signing secrets | Rotated staging + production App Service signing keys and restarted consumers | Richard (`code-puppy-1c7422`) | `ct-dp9.3`, health checks in `docs/security/obsidian-secret-triage-2026-05.md` |
| 2026-05-18 | Dev SQL/admin credential | Rotated dev SQL admin password; updated ignored local SQL env and dev Key Vault connection pointer | Richard (`code-puppy-1c7422`) | `ct-dp9.4` |
| 🔴 TODO | Teams/GitHub environment secrets | Rotate/prove unaffected | Tyler | `ct-dp9.6` |

---

## 7. Risk acceptances

Use this only when there is intentionally no secondary reader/operator yet.

| Date | Credential class | Risk | Accepted by | Expiry / review date |
|---|---|---|---|---|
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
