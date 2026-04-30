---
title: Platform Status
---

# Platform Status

Updated: `2026-04-30T13:29:17.533078+00:00`
Source: GitHub Pages build fallback; no committed `scripts/audit_output.json` was available.

## Current mainline health

| Signal | Status | Evidence |
|---|---|---|
| CI | ✅ Green | Run `25167652385` passed for `00c3745`; rerun pending after docs/workflow refresh. |
| Security Scan | ✅ Green | Run `25167652318` passed for `00c3745`; `UV_VERSION` is now pinned to `0.9.27` across setup-uv workflows. |
| Deploy to Staging | ⚠️ Needs rerun | Run `25167652308` failed because `astral-sh/setup-uv` could not resolve wildcard `0.5.x`; workflows now pin `0.9.27`. |
| Deploy GitHub Pages | ✅ Green | Run `25167652314` published Pages for `00c3745`. |
| GitHub Pages Cross-Browser Tests | ⚠️ Needs rerun | Run `25167652311` failed because homepage title changed; title now includes `Azure Governance Platform` again. |

## Ready work

| bd | Status | Owner | Notes |
|---|---|---|---|
| `9lfn` | Ready | Tyler | `SECRETS_OF_RECORD.md` skeleton exists; Tyler must fill non-secret inventory rows. |
| `213e` | Ready | Tyler | Second rollback human must be named and tabletop exercise recorded. |
| `jzpa` | In progress | code-puppy-661ed0 | Environment secret names configured; backup workflow now installs ODBC Driver 18; production/staging validation pending. |

## Blocked work

| bd | Blocker |
|---|---|
| `0nup` | Blocked by `213e` second rollback human. |
| `uchp` | Blocked by `213e` before quarterly DR test cycle. |
| `cz89` | BACPAC workflow exists, but staging Azure SQL Free edition does not support ImportExport. Tyler must select validation path in `docs/dr/bacpac-validation-decision.md`. |

## Backup / RPO watch

Scheduled Database Backup run `25145371945` failed on 2026-04-30 in both production and staging after Azure OIDC login succeeded. Logs showed `DATABASE_URL` and `AZURE_STORAGE_ACCOUNT` empty. Those GitHub environment secret names were configured on 2026-04-30. Manual validation then exposed two runner gaps: optional `mssqlscripter` was absent, and the GitHub runner did not have ODBC Driver 18 for SQL Server. `backup_database.py` now falls back to SQLAlchemy, and `backup.yml` installs `msodbcsql18` / `unixodbc-dev` before running `pyodbc`. This remains tracked as bd `jzpa` until production and staging evidence runs pass.

## Audit output

_No tenant audit JSON is currently committed, so this page uses the operational status fallback above instead of rendering tenant consent/UI-fixture tables._
