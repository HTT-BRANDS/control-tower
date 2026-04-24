#!/usr/bin/env python3
"""Summarize post-deploy sync recovery evidence into a single report.

This is a read-only reporting tool for issue 0gz3. It consumes exported JSON
from API/SQL/KQL queries and answers the question people actually care about:
"did sync recovery happen, or are we still blocked by the same auth garbage?"
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ALERT_BASELINE = 222
SUSPICIOUS_SIGNATURES: tuple[tuple[str, str], ...] = (
    ("invalid_tenant", "invalid_tenant"),
    ("key vault credentials not found", "missing_per_tenant_key_vault_credentials"),
    (
        "falling back to settings credentials",
        "unexpected_shared_settings_fallback",
    ),
    (
        "not configured for per-tenant key vault credentials",
        "tenant_not_configured_for_per_tenant_key_vault",
    ),
    ("fake tenant", "fake_or_bogus_tenant_reference"),
    ("unconfigured tenant", "fake_or_bogus_tenant_reference"),
)
COST_JOB_TYPES = {"cost", "costs"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync-status-json", type=Path, default=None)
    parser.add_argument("--recent-runs-json", type=Path, default=None)
    parser.add_argument("--alerts-json", type=Path, default=None)
    parser.add_argument("--exceptions-json", type=Path, default=None)
    parser.add_argument("--traces-json", type=Path, default=None)
    parser.add_argument("--baseline-alerts", type=int, default=ALERT_BASELINE)
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--output-md", type=Path, default=None)
    return parser.parse_args()


def _load_json(path: Path | None) -> Any:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _coerce_scalar(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
    return value


def _rows_from_table_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    tables = payload.get("tables")
    if not isinstance(tables, list) or not tables:
        return []
    table = tables[0]
    columns = table.get("columns", [])
    rows = table.get("rows", [])
    if not isinstance(columns, list) or not isinstance(rows, list):
        return []
    names = [c.get("name") if isinstance(c, dict) else str(c) for c in columns]
    result = []
    for row in rows:
        if isinstance(row, list):
            result.append(
                {name: _coerce_scalar(value) for name, value in zip(names, row, strict=False)}
            )
    return result


def _normalize_rows(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("value"), list):
            return [item for item in payload["value"] if isinstance(item, dict)]
        if isinstance(payload.get("items"), list):
            return [item for item in payload["items"] if isinstance(item, dict)]
        table_rows = _rows_from_table_payload(payload)
        if table_rows:
            return table_rows
    return []


def _text_signature(text: str | None) -> str | None:
    if not text:
        return None
    lowered = text.lower()
    for needle, label in SUSPICIOUS_SIGNATURES:
        if needle in lowered:
            return label
    return None


def _safe_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return default


def _build_status_counts(
    sync_status_rows: list[dict[str, Any]], recent_run_rows: list[dict[str, Any]]
) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    source_rows = sync_status_rows if sync_status_rows else recent_run_rows
    for row in source_rows:
        job_type = str(row.get("job_type", "unknown")).lower()
        status = str(row.get("status", "unknown")).lower()
        runs = _safe_int(row.get("runs", 1), default=1)
        counts[job_type][status] += runs
    return {job: dict(statuses) for job, statuses in counts.items()}


def _summarize_recent_failures(recent_run_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_signature: Counter[str] = Counter()
    examples: dict[str, dict[str, Any]] = {}
    tenant_hits: Counter[str] = Counter()

    for row in recent_run_rows:
        if str(row.get("status", "")).lower() != "failed":
            continue
        message = str(row.get("error_message") or row.get("message") or "")
        signature = _text_signature(message)
        if not signature:
            continue
        by_signature[signature] += 1
        tenant_id = str(row.get("tenant_id") or "unknown")
        tenant_hits[tenant_id] += 1
        examples.setdefault(
            signature,
            {
                "tenant_id": tenant_id,
                "job_type": row.get("job_type"),
                "message": message[:240],
            },
        )

    return {
        "signature_counts": dict(by_signature.most_common()),
        "tenant_hits": dict(tenant_hits.most_common()),
        "examples": examples,
    }


def _summarize_alerts(alert_rows: list[dict[str, Any]], baseline_alerts: int) -> dict[str, Any]:
    active = 0
    signature_counts: Counter[str] = Counter()
    for row in alert_rows:
        resolved = row.get("is_resolved", False)
        if resolved in (False, 0, "0", "false", "False", None):
            active += 1
        text = " ".join(
            str(row.get(key, "")) for key in ("title", "message", "alert_type", "job_type")
        )
        signature = _text_signature(text)
        if signature:
            signature_counts[signature] += 1
    return {
        "baseline": baseline_alerts,
        "active_now": active,
        "burn_down": baseline_alerts - active,
        "burn_down_direction": "down" if active < baseline_alerts else "flat_or_up",
        "suspicious_signature_counts": dict(signature_counts.most_common()),
    }


def _summarize_text_rows(rows: list[dict[str, Any]], text_keys: tuple[str, ...]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        text = " ".join(str(row.get(key, "")) for key in text_keys)
        signature = _text_signature(text)
        if signature:
            counts[signature] += 1
    return dict(counts.most_common())


def _costs_recovered(status_counts: dict[str, dict[str, int]]) -> bool:
    for job_type in COST_JOB_TYPES:
        if status_counts.get(job_type, {}).get("completed", 0) > 0:
            return True
    return False


def _overall_verdict(
    status_counts: dict[str, dict[str, int]],
    failure_summary: dict[str, Any],
    alert_summary: dict[str, Any],
    trace_signatures: dict[str, int],
    exception_signatures: dict[str, int],
) -> dict[str, Any]:
    costs_ok = _costs_recovered(status_counts)
    suspicious_counts = Counter(failure_summary["signature_counts"])
    suspicious_counts.update(alert_summary["suspicious_signature_counts"])
    suspicious_counts.update(trace_signatures)
    suspicious_counts.update(exception_signatures)
    suspicious_total = sum(suspicious_counts.values())
    alerts_down = alert_summary["active_now"] < alert_summary["baseline"]

    if costs_ok and suspicious_total == 0 and alerts_down:
        status = "verified"
        summary = (
            "Costs recovered, suspicious bogus-tenant signatures absent, and alerts burned down."
        )
    else:
        status = "blocked"
        reasons = []
        if not costs_ok:
            reasons.append("cost sync success rate has not recovered above 0%")
        if suspicious_total:
            dominant = suspicious_counts.most_common(1)[0][0]
            reasons.append(f"suspicious sync/auth signatures still present ({dominant})")
        if not alerts_down:
            reasons.append("active alerts have not burned down below the 222 baseline")
        summary = "; ".join(reasons)

    return {
        "status": status,
        "summary": summary,
        "costs_recovered": costs_ok,
        "alerts_burned_down": alerts_down,
        "dominant_remaining_signature": suspicious_counts.most_common(1)[0][0]
        if suspicious_counts
        else None,
        "suspicious_signature_total": suspicious_total,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    sync_status_rows = _normalize_rows(_load_json(args.sync_status_json))
    recent_run_rows = _normalize_rows(_load_json(args.recent_runs_json))
    alert_rows = _normalize_rows(_load_json(args.alerts_json))
    trace_rows = _normalize_rows(_load_json(args.traces_json))
    exception_rows = _normalize_rows(_load_json(args.exceptions_json))

    status_counts = _build_status_counts(sync_status_rows, recent_run_rows)
    failure_summary = _summarize_recent_failures(recent_run_rows)
    alert_summary = _summarize_alerts(alert_rows, args.baseline_alerts)
    trace_signatures = _summarize_text_rows(trace_rows, ("message", "outerMessage"))
    exception_signatures = _summarize_text_rows(exception_rows, ("outerMessage", "type", "message"))
    verdict = _overall_verdict(
        status_counts=status_counts,
        failure_summary=failure_summary,
        alert_summary=alert_summary,
        trace_signatures=trace_signatures,
        exception_signatures=exception_signatures,
    )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "baseline_alerts": args.baseline_alerts,
        "inputs_present": {
            "sync_status": bool(sync_status_rows),
            "recent_runs": bool(recent_run_rows),
            "alerts": bool(alert_rows),
            "traces": bool(trace_rows),
            "exceptions": bool(exception_rows),
        },
        "status_counts": status_counts,
        "recent_failure_summary": failure_summary,
        "alert_summary": alert_summary,
        "trace_signature_counts": trace_signatures,
        "exception_signature_counts": exception_signatures,
        "verdict": verdict,
    }


def render_markdown(report: dict[str, Any]) -> str:
    verdict = report["verdict"]
    failure_summary = report["recent_failure_summary"]
    alert_summary = report["alert_summary"]

    lines = [
        "# Sync recovery verification report",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Verdict: **{verdict['status']}**",
        "",
        f"Summary: {verdict['summary']}",
        "",
        "## Inputs present",
        "",
    ]
    for name, present in report["inputs_present"].items():
        lines.append(f"- `{name}`: {'yes' if present else 'no'}")

    lines.extend(
        [
            "",
            "## Sync status counts",
            "",
            "| Job type | Status | Runs |",
            "|---|---|---:|",
        ]
    )
    for job_type, statuses in sorted(report["status_counts"].items()):
        for status, runs in sorted(statuses.items()):
            lines.append(f"| {job_type} | {status} | {runs} |")
    if len(lines) >= 4 and lines[-1] == "|---|---|---:|":
        lines.append("| _none_ | _none_ | 0 |")

    lines.extend(
        [
            "",
            "## Alert burn-down",
            "",
            f"- Baseline active alerts: **{alert_summary['baseline']}**",
            f"- Active alerts now: **{alert_summary['active_now']}**",
            f"- Burn-down delta: **{alert_summary['burn_down']}**",
            f"- Direction: **{alert_summary['burn_down_direction']}**",
            "",
            "## Dominant suspicious signatures",
            "",
        ]
    )

    dominant = Counter()
    dominant.update(failure_summary["signature_counts"])
    dominant.update(alert_summary["suspicious_signature_counts"])
    dominant.update(report["trace_signature_counts"])
    dominant.update(report["exception_signature_counts"])
    if dominant:
        for signature, count in dominant.most_common():
            lines.append(f"- `{signature}`: {count}")
    else:
        lines.append("- None detected")

    examples = failure_summary["examples"]
    if examples:
        lines.extend(["", "## Example recent failures", ""])
        for signature, example in examples.items():
            lines.append(
                f"- `{signature}` on tenant `{example['tenant_id']}` "
                f"({example['job_type']}): {example['message']}"
            )

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    report = build_report(args)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output_json:
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    if args.output_md:
        args.output_md.write_text(render_markdown(report), encoding="utf-8")
    if not args.output_json and not args.output_md:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
