# Current State Assessment — HTT Portfolio Platform

**Assessment Date:** 2026-04-30
**HEAD assessed:** `00c3745` (`ops(backup): restore backup config evidence trail`)
**Source of truth for in-flight detail:** [`SESSION_HANDOFF.md`](./SESSION_HANDOFF.md), `bd ready`, and GitHub Actions run history.

> This file is a reality dashboard. If it says "green," it needs a run ID or
> it is just decorative confetti. We are not doing decorative confetti.

---

## TL;DR

The platform runtime is up in both environments, but continuity work is still in
progress.

- Production health: `https://app-governance-prod.azurewebsites.net/health` returns `healthy` / `2.5.0`.
- Staging health: `https://app-governance-staging-xnczpwyv.azurewebsites.net/health` returns `healthy` / `2.5.0`.
- Mainline CI and Security Scan were green for `00c3745`.
- GitHub Pages deployed for `246e454`, and cross-browser tests passed after the homepage title compatibility fix.
- Staging deploy run `25168188519` passed QA, security, build/push, deploy, and staging validation.
- Scheduled/manual Database Backup is still partially red under bd `jzpa`: staging schema backup now passes end-to-end (`25169438794`), while production failed opening SQL from the GitHub runner (`25169514387`). The workflow now adds/removes a temporary Azure SQL firewall rule for the runner IP.
- Tyler-only continuity gates remain: `9lfn` secret inventory completion and `213e` second rollback human.

---

## Live environment checks

| Environment | URL | Latest observed status | Notes |
|---|---|---|---|
| Production | <https://app-governance-prod.azurewebsites.net/health> | ✅ `healthy`, version `2.5.0` | Checked 2026-04-30 during this session. |
| Staging | <https://app-governance-staging-xnczpwyv.azurewebsites.net/health> | ✅ `healthy`, version `2.5.0` | The older `xncz` hostname is stale; use `xnczpwyv`. |
| GitHub Pages | <https://htt-brands.github.io/azure-governance-platform/> | ✅ Deploy and browser checks passed for `246e454` | Public site is refreshed with continuity status and portfolio-platform framing. |

---

## Latest relevant GitHub Actions

| Workflow | Run | Conclusion | Meaning |
|---|---:|---|---|
| CI | `25168188513` | ✅ success | Source checks passed for `246e454`. |
| Security Scan | `25168188503` | ✅ success | Security scan passed for `246e454` after `UV_VERSION=0.9.27` pin. |
| Deploy GitHub Pages | `25168188577` | ✅ success | Pages content was published for `246e454`. |
| GitHub Pages Cross-Browser Tests | `25168188537` | ✅ success | Homepage title compatibility fix passed all browser/device projects. |
| Deploy to Staging | `25168188519` | ✅ success | QA, security, build/push, deploy, and staging validation passed. |
| Topology Diagram | `25168188576` | ❌ failure | Generated timestamp-only topology diff but bot could not push to protected `main`; local commit includes refreshed diagram. |
| Database Backup production manual | `25169514387` | ❌ failure | Reached ODBC/SQLAlchemy; production SQL metadata exists, so workflow now adds a temporary runner-IP SQL firewall rule before retrying. |
| Database Backup staging manual | `25169438794` | ✅ success | Schema-only staging backup created, verified, uploaded, integrity-checked, and cleanup completed after ephemeral `AZURE_STORAGE_KEY` workflow change. |
| Scheduled Database Backup | `25145371945` | ❌ failure | Original prod/staging empty `DATABASE_URL` / `AZURE_STORAGE_ACCOUNT` failure. |

---

## Current work queue

`bd ready` currently shows:

| bd | Priority | Owner | Status |
|---|---|---|---|
| `9lfn` | P1 | Tyler | Ready — finish non-secret `SECRETS_OF_RECORD.md` inventory. |
| `jzpa` | P1 | `code-puppy-661ed0` | In progress — backup workflow config/tooling validation. |
| `213e` | P2 | Tyler | Ready — name second rollback human before waiver expiry. |

Blocked:

| bd | Blocker |
|---|---|
| `0nup` | Blocked by `213e`. |
| `uchp` | Blocked by `213e`. |
| `cz89` | Blocked operationally by Azure SQL Free ImportExport limitation; see `docs/dr/bacpac-validation-decision.md`. |

---

## Backup / RPO truth

The backup story is not green yet.

1. `fifh` fixed the broken Teams notify action.
2. `3flq` fixed OIDC permission for Azure login.
3. Run `25145371945` then exposed missing production/staging GitHub environment backup secret names.
4. On 2026-04-30, `DATABASE_URL` and `AZURE_STORAGE_ACCOUNT` were configured for production and staging without printing secret values.
5. Production backup storage account `stgovprodbkup001` was created in `rg-governance-production`.
6. Manual validation runs `25167657417` and `25167659155` then exposed missing runner SQL tooling: optional `mssqlscripter` and ODBC Driver 18.
7. Current code makes `backup_database.py` fall back to SQLAlchemy and updates `backup.yml` to install `msodbcsql18` / `unixodbc-dev` before running `pyodbc`.
8. Validation runs `25168192604`, `25168194585`, and `25168804362` moved past ODBC. Staging created and verified a SQL backup, then failed Blob upload on `AuthorizationPermissionMismatch` even after Storage Blob Data Contributor was granted. The workflow now derives an ephemeral `AZURE_STORAGE_KEY` after OIDC login and passes it only through runner environment.
9. Staging schema backup passed end-to-end in run `25169438794`.
10. Production schema backup still failed opening the SQL server/login in run `25169514387`; SQL server/database metadata exists and the server firewall only had App Service/Tyler IP rules, so `backup.yml` now creates a temporary per-run GitHub runner IP firewall rule and removes it in an `always()` cleanup step.

Do **not** declare RPO backup hygiene complete until production and staging backup evidence runs pass and bd `jzpa` is closed with run IDs.

---

## Public docs / Pages freshness

The public GitHub Pages site now has:

- Portfolio-platform framing on the home page instead of stale Riverside-first positioning.
- A linked Operations → Continuity Status page.
- `docs/status.md` fallback content that shows current CI/backup/continuity state even when `scripts/audit_output.json` is absent.
- Continuity links to `RUNBOOK.md`, `SECRETS_OF_RECORD.md`, RTO/RPO, and BACPAC validation decision docs.

Still verify the Pages cross-browser failure after this update; the site deploy can succeed while the browser check catches broken links or rendering issues. Tiny rude robot, but useful.

---

## Tyler-only decisions still open

Do not decide these on Tyler's behalf:

- `9lfn`: complete `SECRETS_OF_RECORD.md` ownership/access/rotation metadata.
- `213e`: name second rollback human.
- Portfolio platform final name (`PORTFOLIO_PLATFORM_PLAN_V2.md` §11).
- D8 CIEM build-vs-buy, D9 WIGGUM relationship, D10 cross-tenant identity stance.
