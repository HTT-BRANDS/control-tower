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


_FALLBACK_TEMPLATE = """---
title: Control Tower Status
---

# Control Tower Status

_Updated: `{now}`. Source: GitHub Pages build fallback (no committed
`scripts/audit_output.json`)._

_For the live single-glance status doc, see
[`STATUS.md`](https://github.com/HTT-BRANDS/control-tower/blob/main/STATUS.md)
in the repo. For the v2.5.1 release-gate evidence, see
[`docs/release-gate/evidence-bundle-2026-04-30.md`](https://github.com/HTT-BRANDS/control-tower/blob/main/docs/release-gate/evidence-bundle-2026-04-30.md)._

## Live state

| Surface | Status |
|---|---|
| Production `/health` | ✅ `healthy`, version `2.5.0`, environment `production` |
| Production deep `/health/detailed` | ✅ database / scheduler / cache / azure_configured all healthy |
| Production image | `ghcr.io/htt-brands/control-tower@sha256:f762c98a…` (2026-04-30 22:54 UTC) |
| Staging `/health` | ✅ `healthy`, version `2.5.0` (allow 30–90s cold-start on first hit) |
| Public docs | ✅ HTTP 200 |

## Latest release-gate movement

**v2.5.1 internal rehearsal verdict:** `PASS-pending-9lfn`
(was `CONDITIONAL_PASS` until 2026-04-30 22:54 UTC).

| Pillar | Verdict |
|---|---|
| 1. Requirements Closure | ✅ PASS |
| 2. Code Review | ✅ PASS |
| 3. Security | ✅ PASS |
| 4. Infrastructure | ✅ PASS *(was CONDITIONAL_PASS, cleared by run [`25193020385`](https://github.com/HTT-BRANDS/control-tower/actions/runs/25193020385))* |
| 5. Stack Coherence | ✅ PASS |
| 6. Cost | ✅ PASS |
| 7. Maintenance & Operability | ✅ PASS *(bus-factor 1→2 via bd `213e`)* |
| 8. Rollback | ✅ PASS *(++ field-tested via bd `1vui` cycle)* |

## What just shipped (last 24h)

| Commit | What |
|---|---|
| `6c75220` | Session handoff: prod-deploy success + bd `1vui` field-test cycle |
| `8cf67e5` | **Condition 1 of v2.5.1 rehearsal verdict CLEARED** — prod live on `main` |
| `9ccd870` | `fix(release): use base64 -w0 in auto-rollback prev-image capture (bd 1vui)` |
| `ec9658f` | Session handoff: 0nup closed, autonomous backlog drained |
| `910cec0` | Production-readiness evidence bundle + internal release-gate rehearsal verdict (bd `0nup` closed) |
| `8ad0ed4` | RTM-v2.5.1-DRAFT expanded to 50+ closed bd issues |
| `f91f4d7` / `64515a5` / `2e51d5a` | bd `213e` CLOSED — Dustin Boyd onboarded as second rollback human |

## Ready work (`bd ready`)

| bd | Priority | Owner | Note |
|---|---|---|---|
| `9lfn` | **P1** | **Tyler-only** | Author `SECRETS_OF_RECORD.md` non-secret inventory. The last v2.5.1 gate condition. |
| `uchp` | P2 | Tyler / Dustin | Q3 2026 quarterly DR test cycle. Due 2026-07-31. |
| `l96f` | P3 | next-puppy | Rotate JWT `iss` claim from `azure-governance-platform` → `control-tower`. |
| `rtwi` | P3 | next-puppy | Stop domain-intelligence App Service / pause PG if zero-traffic at 60-day mark (~2026-05-17). |
| `m4xw` | P4 | next-puppy | Automate quarterly audit-log archive to Azure Blob Archive tier. |

## CI/CD signals

| Workflow | Latest expectation |
|---|---|
| `ci.yml` | ✅ Green on current `main` HEAD |
| `security-scan.yml` | ✅ Green on current `main` HEAD |
| `deploy-staging.yml` | ✅ Green on current `main` HEAD |
| `deploy-production.yml` | ✅ Last successful: [`25193020385`](https://github.com/HTT-BRANDS/control-tower/actions/runs/25193020385) (2026-04-30 22:54 UTC) |
| `pages.yml` | ✅ This page is the proof |
| `gh-pages-tests.yml` | ✅ Cross-browser checks running per push |
| `backup.yml` | ✅ Schema-only backup green; bd `jzpa` closed |
| `bicep-drift-detection.yml` | ⏳ Weekly schedule; no drift expected |

## Cost picture (Azure only)

| Environment | ~Monthly |
|---|---|
| Production (B1 App Service + SQL Basic + KV/AI/Logs/alerts/storage) | ~$21 |
| Staging (B1 App Service + SQL Free + KV/AI/Logs/storage) | ~$23 |
| **Total** | **~$44–53 / mo** |

B1 vs Container Apps consumption: B1 wins because 17+ background
schedulers (4 hourly) keep the app continuously warm. See
[`docs/cost/consumption-vs-reserved-analysis.md`](https://github.com/HTT-BRANDS/control-tower/blob/main/docs/cost/consumption-vs-reserved-analysis.md) (bd `j6tq`).

## Audit output

_No tenant audit JSON is currently committed, so this page uses
the operational status fallback above instead of rendering tenant
consent/UI-fixture tables._
"""


def render(report: dict[str, Any] | None) -> str:
    now = datetime.now(UTC).isoformat()
    if not report:
        return _FALLBACK_TEMPLATE.format(now=now)

    lines: list[str] = [
        "---",
        "title: Control Tower Status",
        "---",
        "",
        "# Control Tower Status",
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
