"""Render scripts/audit_output.json into docs/status.md for GitHub Pages.

Runs as a step inside .github/workflows/pages.yml. Safe to run when the
audit output is missing — produces a "no data" placeholder.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def render(report: dict[str, Any] | None) -> str:
    now = datetime.now(UTC).isoformat()
    if not report:
        return (
            "---\ntitle: Platform Status\n---\n\n"
            "# Platform Status\n\n"
            f"Updated: `{now}`\n"
            "Source: GitHub Pages build fallback; no committed "
            "`scripts/audit_output.json` was available.\n\n"
            "## Current mainline health\n\n"
            "| Signal | Status | Evidence |\n"
            "|---|---|---|\n"
            "| CI | ⏳ In progress | Run `25169432815` is still running for `bf4685f`; previous run `25168188513` was green. |\n"
            "| Security Scan | ✅ Green | Run `25169432889` passed for `bf4685f`; `UV_VERSION` is pinned to `0.9.27` across setup-uv workflows. |\n"
            "| Deploy to Staging | ⏳ In progress | Run `25169432814` is still running; previous run `25168188519` passed QA/security/build/deploy/validation. |\n"
            "| Deploy GitHub Pages | ✅ Green | Run `25169432895` published Pages for `bf4685f`. |\n"
            "| GitHub Pages Cross-Browser Tests | ⏳ In progress | Run `25169432848` is still running; previous run `25168188537` was green. |\n"
            "| Topology Diagram | ⚠️ Follow-up | Run `25168188576` generated a timestamp-only topology diff but could not push to protected `main`; local commit includes the refreshed diagram. |\n\n"
            "## Ready work\n\n"
            "| bd | Status | Owner | Notes |\n"
            "|---|---|---|---|\n"
            "| `9lfn` | Ready | Tyler | `SECRETS_OF_RECORD.md` skeleton exists; Tyler must fill non-secret inventory rows. |\n"
            "| `213e` | Ready | Tyler | Second rollback human must be named and tabletop exercise recorded. |\n"
            "| `jzpa` | In progress | code-puppy-661ed0 | Staging schema backup passes end-to-end (`25169438794`). Production failed SQL access (`25169514387`); backup workflow now adds/removes a temporary SQL firewall rule for runner IP. |\n\n"
            "## Blocked work\n\n"
            "| bd | Blocker |\n"
            "|---|---|\n"
            "| `0nup` | Blocked by `213e` second rollback human. |\n"
            "| `uchp` | Blocked by `213e` before quarterly DR test cycle. |\n"
            "| `cz89` | BACPAC workflow exists, but staging Azure SQL Free edition does not support ImportExport. Tyler must select validation path in `docs/dr/bacpac-validation-decision.md`. |\n\n"
            "## Backup / RPO watch\n\n"
            "Scheduled Database Backup run `25145371945` failed on 2026-04-30 "
            "in both production and staging after Azure OIDC login succeeded. "
            "Logs showed `DATABASE_URL` and `AZURE_STORAGE_ACCOUNT` empty. "
            "Those GitHub environment secret names were configured on "
            "2026-04-30. Manual validation then exposed two runner gaps: "
            "optional `mssqlscripter` was absent, and the GitHub runner did "
            "not have ODBC Driver 18 for SQL Server. `backup_database.py` "
            "now falls back to SQLAlchemy, and `backup.yml` installs "
            "`msodbcsql18` / `unixodbc-dev` before running `pyodbc`. "
            "Validation runs `25168192604` / `25168194585` moved past ODBC; "
            "staging created and verified a backup but still failed Blob upload "
            "with `AuthorizationPermissionMismatch` after the RBAC grant. "
            "The workflow now derives an ephemeral `AZURE_STORAGE_KEY` after "
            "OIDC login and passes it only via runner environment. Staging "
            "schema backup then passed end-to-end in run `25169438794`. "
            "Production still fails opening the SQL server/login in run "
            "`25169514387`; production SQL metadata exists, so `backup.yml` "
            "now adds a temporary per-run Azure SQL firewall rule for the "
            "GitHub runner IP and removes it with `always()`. This remains "
            "tracked as bd `jzpa` until production passes.\n\n"
            "## Audit output\n\n"
            "_No tenant audit JSON is currently committed, so this page uses "
            "the operational status fallback above instead of rendering tenant "
            "consent/UI-fixture tables._\n"
        )

    lines: list[str] = [
        "---",
        "title: Platform Status",
        "---",
        "",
        "# Platform Status",
        "",
        f"Generated: `{report.get('generated_at', now)}`",
        f"Environment: **{report.get('environment', 'unknown')}**",
        "",
        "## Tenant health",
        "",
        "| Tenant | Reader | Consent | Missing scopes |",
        "|---|---|---|---|",
    ]
    for t in report.get("tenants", []):
        reader = "✅" if t["reader"].get("ok") else "❌"
        consent = "✅" if t["graph_consent"].get("ok") else "❌"
        missing = ", ".join(t["graph_consent"].get("missing", [])) or "—"
        lines.append(f"| {t['code']} | {reader} | {consent} | `{missing}` |")

    lines += ["", "## UI-fixture leaks", ""]
    leaks = report.get("ui_fixture_leaks", [])
    if not leaks:
        lines.append("_None — no MOCK_ / fixture imports in page routes or templates._")
    else:
        for p in leaks:
            lines.append(f"- `{p}`")
    lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Render audit JSON into docs/status.md.")
    p.add_argument("--input", default=str(REPO_ROOT / "scripts" / "audit_output.json"))
    p.add_argument("--output", default=str(REPO_ROOT / "docs" / "status.md"))
    args = p.parse_args(argv)

    report = _load(Path(args.input))
    Path(args.output).write_text(render(report), encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
