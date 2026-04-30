---
title: Platform Status
---

# Platform Status

Updated: `2026-04-30T14:35:59.554836+00:00`
Source: GitHub Pages build fallback; no committed `scripts/audit_output.json` was available.

## Current mainline health

| Signal | Status | Evidence |
|---|---|---|
| CI | ⏳ In progress | Run `25169432815` is still running for `bf4685f`; previous run `25168188513` was green. |
| Security Scan | ✅ Green | Run `25169432889` passed for `bf4685f`; `UV_VERSION` is pinned to `0.9.27` across setup-uv workflows. |
| Deploy to Staging | ⏳ In progress | Run `25169432814` is still running; previous run `25168188519` passed QA/security/build/deploy/validation. |
| Deploy GitHub Pages | ✅ Green | Run `25169432895` published Pages for `bf4685f`. |
| GitHub Pages Cross-Browser Tests | ⏳ In progress | Run `25169432848` is still running; previous run `25168188537` was green. |
| Topology Diagram | ⚠️ Follow-up | Run `25168188576` generated a timestamp-only topology diff but could not push to protected `main`; local commit includes the refreshed diagram. |

## Ready work

| bd | Status | Owner | Notes |
|---|---|---|---|
| `9lfn` | Ready | Tyler | `SECRETS_OF_RECORD.md` skeleton exists; Tyler must fill non-secret inventory rows. |
| `213e` | Ready | Tyler | Second rollback human must be named and tabletop exercise recorded. |
| `jzpa` | Closed | code-puppy-661ed0 | Backup workflow validated: staging schema backup `25169438794`, production schema backup `25171354807`; no temporary SQL firewall rules left behind. |

## Blocked work

| bd | Blocker |
|---|---|
| `0nup` | Blocked by `213e` second rollback human. |
| `uchp` | Blocked by `213e` before quarterly DR test cycle. |
| `cz89` | BACPAC workflow exists, but staging Azure SQL Free edition does not support ImportExport. Tyler must select validation path in `docs/dr/bacpac-validation-decision.md`. |

## Backup / RPO watch

Scheduled Database Backup run `25145371945` failed on 2026-04-30 in both production and staging after Azure OIDC login succeeded. Logs showed `DATABASE_URL` and `AZURE_STORAGE_ACCOUNT` empty. Those GitHub environment secret names were configured on 2026-04-30. Manual validation then exposed two runner gaps: optional `mssqlscripter` was absent, and the GitHub runner did not have ODBC Driver 18 for SQL Server. `backup_database.py` now falls back to SQLAlchemy, and `backup.yml` installs `msodbcsql18` / `unixodbc-dev` before running `pyodbc`. Validation runs `25168192604` / `25168194585` moved past ODBC; staging created and verified a backup but still failed Blob upload with `AuthorizationPermissionMismatch` after the RBAC grant. The workflow now derives an ephemeral `AZURE_STORAGE_KEY` after OIDC login and passes it only via runner environment. Staging schema backup then passed end-to-end in run `25169438794`. Production then created, uploaded, verified, and cleaned up a schema backup in run `25171161761`; only the SQL firewall cleanup step failed because `az sql server firewall-rule delete` does not support `--yes`. The leftover rule was removed manually, the flag was removed from `backup.yml`, and production validation passed end-to-end in run `25171354807`. No temporary `GitHubActions-*` SQL firewall rules remained afterward. bd `jzpa` is closed.

## Audit output

_No tenant audit JSON is currently committed, so this page uses the operational status fallback above instead of rendering tenant consent/UI-fixture tables._
