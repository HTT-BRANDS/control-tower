---
title: Control Tower Status
---

# Control Tower Status

Updated: `2026-04-30T17:29:44.322088+00:00`
Source: GitHub Pages build fallback; no committed `scripts/audit_output.json` was available.

## Current mainline / rebrand health

| Signal | Status | Evidence |
|---|---|---|
| Main CI | ✅ Green | Run `25171482414` passed for `f9f7c60`. |
| Main Security Scan | ✅ Green | Run `25171482365` passed for `f9f7c60`; `UV_VERSION` is pinned to `0.9.27` across setup-uv workflows. |
| Main Deploy to Staging | ✅ Green | Run `25171482459` passed for `f9f7c60`. |
| Main Deploy GitHub Pages | ✅ Green | Run `25171483184` published Pages for `f9f7c60`. |
| Main Pages Cross-Browser Tests | ✅ Green | Run `25171483199` passed for `f9f7c60`. |
| PR #8 CI | ✅ Green | Run `25179222805` passed for `b577fde` on `control-tower-internal-rebrand`. |
| PR #8 Security Scan | ✅ Green | Run `25179222861` passed for `b577fde`. |
| PR #8 Pages Cross-Browser Tests | ✅ Green | Run `25179222831` passed for `b577fde`. |
| Topology Diagram | ⚠️ Follow-up | Run `25168188576` generated a timestamp-only topology diff but could not push to protected `main`; local commit includes the refreshed diagram. |

## Ready work

| bd | Status | Owner | Notes |
|---|---|---|---|
| `9lfn` | Ready | Tyler | `SECRETS_OF_RECORD.md` skeleton exists; Tyler must fill non-secret inventory rows. |
| `0dsr` | Ready | Tyler/Richard | Execute GitHub repo/GHCR/Pages Control Tower cutover after PR #8 merge decision. |
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
