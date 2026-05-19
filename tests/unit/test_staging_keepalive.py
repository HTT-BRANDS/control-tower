"""Regression tests for ct-boh: staging keepalive workflow.

The B1 SKU + Always On combination still leaks cold-starts (~10 min idle
→ 30-60s first-hit hang per the 2026-05-19 API audit). The
.github/workflows/staging-keepalive.yml workflow is the cheap mitigation:
external curl every ~5 min keeps the container warm without spending
money on an S1 upgrade or a third-party uptime service.

These tests pin the design decisions so they don't accidentally regress
into something useless (e.g. an hourly schedule that's slower than the
idle threshold, or a hard-fail that masks the production monitor).
"""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "staging-keepalive.yml"


def _load():
    return yaml.safe_load(WORKFLOW.read_text())


def test_keepalive_workflow_exists():
    assert WORKFLOW.exists(), (
        "ct-boh: staging-keepalive.yml must exist to mitigate B1 cold-starts"
    )


def test_keepalive_runs_at_5_minute_cadence():
    """The B1 cold-start threshold is ~10 min idle. A schedule slower than
    that would defeat the purpose; we want every 5 min so even with GitHub's
    'best effort up to 15 min late' guarantee, most ticks land under 10 min."""
    wf = _load()
    # PyYAML maps the YAML `on:` key to the Python boolean True (not the
    # string "on") because YAML 1.1 treats `on` as a synonym for `true`.
    # Tolerate both.
    on_key = wf.get("on") or wf.get(True)
    schedules = on_key["schedule"]
    cron_exprs = [s["cron"] for s in schedules]
    assert "*/5 * * * *" in cron_exprs, (
        f"ct-boh: keepalive cron must be '*/5 * * * *'; got {cron_exprs!r}"
    )


def test_keepalive_does_not_hard_fail():
    """The keepalive is informational — a transient cold-start timeout
    should NOT red-light the Actions UI. Production has a real uptime
    monitor for that signal."""
    src = WORKFLOW.read_text()
    assert "continue-on-error: true" in src, (
        "ct-boh: keepalive must use continue-on-error: true so a transient "
        "timeout doesn't pollute the Actions UI with red runs that are "
        "below the production monitor's noise floor"
    )


def test_keepalive_targets_staging_only():
    """Production has Application Insights availability monitoring. The
    keepalive is for staging specifically. Including prod would just burn
    cron minutes without adding signal."""
    src = WORKFLOW.read_text()
    assert "app-governance-staging-xnczpwyv" in src, (
        "ct-boh: keepalive must target the staging hostname"
    )
    # And not silently expanded into prod too.
    assert "app-governance-prod" not in src, (
        "ct-boh: keepalive must NOT ping production — that's covered by "
        "Application Insights availability tests"
    )


def test_keepalive_uses_concurrency_to_avoid_pileup():
    """If a ping takes >5 min (cold-start scenarios), the next cron tick
    arrives before the previous finishes. Without concurrency control
    we'd queue up indefinitely."""
    wf = _load()
    assert "concurrency" in wf, (
        "ct-boh: keepalive must declare concurrency to avoid run-pileup "
        "during slow-warm scenarios"
    )
    assert wf["concurrency"].get("cancel-in-progress") is True, (
        "ct-boh: concurrency.cancel-in-progress must be true"
    )
