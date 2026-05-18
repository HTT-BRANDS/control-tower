# Obsidian Secret Triage — 2026-05

> Owner: Tyler + Richard (`code-puppy-1c7422`)  
> Bead: `ct-dp9`  
> Classification: sanitized incident-response notes only.  
> Rule: **Do not add secret values to this file.**

## Summary

Obsidian generated a local `AUDIT_REPORT.md` that contained a secret inventory and at least one literal SQL password. The report was intentionally removed from the working tree and was not committed. Because local `.env` files also contain real-looking credentials, treat the values that were visible to Obsidian as compromised unless Tyler can prove they were already invalidated.

This document captures the safe remediation checklist and repo-side containment work without recording any secret values.

## Current repo containment status

| Check | Result | Evidence |
|---|---|---|
| Dangerous `AUDIT_REPORT.md` committed? | ✅ No evidence found | `find`/`rg` found no active root `AUDIT_REPORT.md` containing Obsidian secret inventory |
| Local `.env` tracked? | ✅ No | `.gitignore` ignores `.env`; `git ls-files .env` empty |
| Local `.env.azure-sql-dev` tracked? | ✅ No | `.gitignore` ignores `.env.*`; `git ls-files .env.azure-sql-dev` empty |
| `.env.production` tracked? | ✅ Fixed | Removed from git index in `ct-dp9`; `.gitignore` blocks `.env.*` |
| Pre-commit secret scan | ✅ Pass | `uv run pre-commit run detect-secrets --all-files` passed |
| Canonical credential inventory | ⚠️ Tyler-owned | `SECRETS_OF_RECORD.md` exists but still has Tyler-only TODOs |

## Credential classes requiring Tyler rotation or explicit invalidation

These are derived from the `ct-dp9` description and local env key names only. They are intentionally non-secret.

| Class | Examples / scope | Required action | Owner | Status |
|---|---|---|---|---|
| Azure platform client secret | `AZURE_CLIENT_SECRET` | Rotate app credential or confirm OIDC/UAMI fully replaced it and delete old secret | Richard + Tyler | ✅ DONE for visible platform app; old app password deleted |
| Managed tenant app secrets | Riverside/HTT/BCC/FN/TLL/DCE client secrets | Rotate each tenant app credential or invalidate unused app registrations | Richard + Tyler | ✅ DONE: HTT aligned; BCC/FN/TLL/DCE rotated and previous password credentials removed |
| JWT signing key | `JWT_SECRET_KEY` / app runtime signing secret | Generate new production/staging values; update app settings/Key Vault; restart services | Richard | ✅ DONE for staging + production App Services |
| Dev SQL/admin password | Local Azure SQL dev URL / SQL admin password exposed to Obsidian | Rotate password or delete dev DB/user if no longer needed | Richard | ✅ DONE; ignored local SQL env + dev KV connection updated |
| Teams webhooks | Teams alert webhook URL if present in local env/report | Rotate connector URL if value was exposed | Richard | ✅ No Teams/webhook GitHub secret names found; ignored local env files had no webhook/GitHub/GHCR key names |
| Shell/history exposure | Local terminal history may include copied secret values | Review and purge affected entries; rotate any values found | Richard | ✅ DONE: risky `.zsh_history` lines removed; post-clean scan zero tracked terms/patterns |
| GitHub environment secrets | Staging/production `DATABASE_URL`, SQL backup secrets, webhook secrets | Confirm current values differ from exposed local values or rotate | Richard | ✅ DONE: DB secrets overwritten/synced from current App Service settings; staging SQL admin password rotated |
| Azure Key Vault secrets | `sql-admin-password`, runtime app secrets | Rotate affected secrets and verify consuming services read latest version | Richard + Tyler | ✅ DONE for reachable dev/runtime secret refs; staging/prod app health validated |

## Rotation order

1. **Freeze further secret printing**
   - Do not run commands that echo env files, app settings, GitHub secrets, or Key Vault secret values.
   - Use key names, version IDs, timestamps, or masked summaries only.

2. **Rotate externally-valid credentials first**
   - Azure app/client secrets across platform + managed tenants.
   - SQL admin/dev password.
   - Teams webhook connectors.

3. **Update secret stores**
   - Azure Key Vault secrets.
   - GitHub environment secrets.
   - App Service configuration settings if still used directly.

4. **Restart consumers**
   - Staging App Service.
   - Production App Service.
   - Any scheduled backup/deploy workflow that caches configuration.

5. **Validate without printing values**
   - App starts and health endpoints pass.
   - OIDC/UAMI login succeeds where expected.
   - Data sync/fetch smoke passes.
   - Backup/export workflows authenticate using new secret versions.

6. **Record metadata only**
   - Update `SECRETS_OF_RECORD.md` with storage pointers, owners, last rotated date, next due date, and recovery notes.
   - Never paste values.

## Sanitized findings to track

| Finding | Status | Bead |
|---|---|---|
| `.env.production` remained tracked after `.gitignore` fix | ✅ Fixed in repo | `ct-dp9` |
| Platform Azure app secret exposed locally | ✅ Rotated; old password credential deleted | `ct-dp9.1` |
| JWT signing secrets exposed locally | ✅ Rotated for staging/prod and apps restarted | `ct-dp9.3` |
| Dev SQL/admin credential exposed locally | ✅ Rotated; local ignored env + dev KV pointer updated | `ct-dp9.4` |
| Managed BCC/FN/TLL/DCE tenant app secrets | ✅ Fixed; BCC/FN/TLL/DCE rotated after tenant-specific admin auth | `ct-dp9.2` |
| Teams/GitHub environment exposure confirmation | ✅ Fixed/confirmed: no Teams/webhook secret names found; DB env secrets overwritten; staging SQL admin rotated | `ct-dp9.6` |
| Shell history review | ✅ Fixed: 3 risky `.zsh_history` lines removed; post-clean scan clean | `ct-dp9.5` |
| Tyler-only secret inventory incomplete | Open | `azure-governance-platform-9lfn` |

## Commands used safely

```bash
git ls-files .env .env.production .env.azure-sql-dev SECRETS_OF_RECORD.md .secrets.baseline
git check-ignore -v .env .env.production .env.azure-sql-dev
uv run pre-commit run detect-secrets --all-files
git rm --cached .env.production
```

## Execution evidence — 2026-05-18

| Action | Evidence |
|---|---|
| Staging `JWT_SECRET_KEY` rotated | App setting updated, App Service restarted, `/health` returned HTTP 200 with `environment=staging` |
| Production `JWT_SECRET_KEY` rotated | App setting updated, App Service restarted, `/health` returned HTTP 200 with `environment=production` |
| Dev SQL admin password rotated | `sql-governance-dev-76481` password reset; ignored `.env.azure-sql-dev` and `kv-gov-dev-001/sql-governance-dev-connection` updated |
| Platform Azure app secret rotated | New password credential added to `Riverside-Capital-PE-Governance-Platform`; prod `AZURE_CLIENT_SECRET`, dev KV `azure-client-secret` / `primary-client-secret`, and ignored local `.env` updated |
| Old platform app password invalidated | Previous password credential deleted; only `ct-dp9-platform-rotation-2026-05-18` remained afterward |
| HTT managed tenant secret aligned | Ignored local `RIVERSIDE_HTT_CLIENT_SECRET` and dev KV `htt-client-secret` aligned to rotated platform credential |
| Production health after rotations | `https://app-governance-prod.azurewebsites.net/health` returned HTTP 200 |
| Dev health after rotations | `https://app-governance-dev-001.azurewebsites.net/health` returned HTTP 200 |
| BCC/FN/TLL/DCE managed app rotation | DCE rotated first; BCC/FN/TLL rotated after tenant-specific admin re-auth; previous password credentials removed; remaining password credential count=1 each |
| Shell history key-name scan | Initial scan found no tracked key names; deeper pattern scan found 3 risky `.zsh_history` lines, removed them, and post-clean scan returned zero tracked terms/patterns |
| GitHub/Teams local exposure inventory | Ignored local env files contained no webhook/GitHub/GHCR keys; no GitHub secret names matched Teams/webhook; GitHub DB secrets were overwritten as defense-in-depth |
| GitHub staging SQL admin secret | Rotated `sql-governance-staging-77zfjyem` admin password and updated GitHub `staging/SQL_ADMIN_PASSWORD` |
| GitHub DB URL secrets | Synced `staging/DATABASE_URL`, `production/DATABASE_URL`, and `production-backup/DATABASE_URL` from current App Service settings |
| Final app health | Dev, staging, and production `/health` returned HTTP 200 after rotations |


## Closure rule for `ct-dp9`

`ct-dp9` should not be closed solely because repo-side containment is complete. Close only after Tyler confirms one of the following for each credential class above:

- rotated and deployed,
- invalidated/deleted,
- proven placeholder/non-live, or
- explicitly risk-accepted with review date in `SECRETS_OF_RECORD.md`.
