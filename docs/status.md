---
title: Platform Status
---

# Platform Status

Updated: `2026-04-30T13:55:08.044325+00:00`
Source: GitHub Pages build fallback; no committed `scripts/audit_output.json` was available.

## Current mainline health

| Signal | Status | Evidence |
|---|---|---|
| CI | ✅ Green | Run `25167652385` passed for `00c3745`; rerun pending after docs/workflow refresh. |
| Security Scan | ✅ Green | Run `25167652318` passed for `00c3745`; `UV_VERSION` is now pinned to `0.9.27` across setup-uv workflows. |
| Deploy to Staging | ✅ Green | Run `25168188519` passed QA, security, build/push, deploy, and staging validation. |
| Deploy GitHub Pages | ✅ Green | Run `25168188577` published Pages for `246e454`. |
| GitHub Pages Cross-Browser Tests | ✅ Green | Run `25168188537` passed after homepage title included `Azure Governance Platform` again. |
| Topology Diagram | ⚠️ Follow-up | Run `25168188576` generated a timestamp-only topology diff but could not push to protected `main`; local commit includes the refreshed diagram. |

## Ready work

| bd | Status | Owner | Notes |
|---|---|---|---|
| `9lfn` | Ready | Tyler | `SECRETS_OF_RECORD.md` skeleton exists; Tyler must fill non-secret inventory rows. |
| `213e` | Ready | Tyler | Second rollback human must be named and tabletop exercise recorded. |
| `jzpa` | In progress | code-puppy-661ed0 | Staging DB backup works; upload auth now uses an ephemeral storage key because RBAC data-plane writes still failed. Production still has SQL login/server blocker. |

## Blocked work

| bd | Blocker |
|---|---|
| `0nup` | Blocked by `213e` second rollback human. |
| `uchp` | Blocked by `213e` before quarterly DR test cycle. |
| `cz89` | BACPAC workflow exists, but staging Azure SQL Free edition does not support ImportExport. Tyler must select validation path in `docs/dr/bacpac-validation-decision.md`. |

## Backup / RPO watch

Scheduled Database Backup run `25145371945` failed on 2026-04-30 in both production and staging after Azure OIDC login succeeded. Logs showed `DATABASE_URL` and `AZURE_STORAGE_ACCOUNT` empty. Those GitHub environment secret names were configured on 2026-04-30. Manual validation then exposed two runner gaps: optional `mssqlscripter` was absent, and the GitHub runner did not have ODBC Driver 18 for SQL Server. `backup_database.py` now falls back to SQLAlchemy, and `backup.yml` installs `msodbcsql18` / `unixodbc-dev` before running `pyodbc`. Validation runs `25168192604` / `25168194585` moved past ODBC; staging created and verified a backup but still failed Blob upload with `AuthorizationPermissionMismatch` after the RBAC grant. The workflow now derives an ephemeral `AZURE_STORAGE_KEY` after OIDC login and passes it only via runner environment. Production still fails opening the SQL server/login. This remains tracked as bd `jzpa`.

## Audit output

_No tenant audit JSON is currently committed, so this page uses the operational status fallback above instead of rendering tenant consent/UI-fixture tables._
