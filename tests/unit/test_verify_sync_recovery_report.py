"""Tests for scripts/verify_sync_recovery_report.py."""

from argparse import Namespace

from scripts.verify_sync_recovery_report import build_report, render_markdown


def _args(**overrides):
    defaults = {
        "sync_status_json": None,
        "recent_runs_json": None,
        "alerts_json": None,
        "exceptions_json": None,
        "traces_json": None,
        "baseline_alerts": 222,
        "output_json": None,
        "output_md": None,
    }
    defaults.update(overrides)
    return Namespace(**defaults)


def test_report_marks_recovery_blocked_when_costs_not_recovered_and_signatures_remain(tmp_path):
    sync_status = tmp_path / "sync_status.json"
    sync_status.write_text(
        """
        [
          {"job_type": "costs", "status": "failed", "runs": 4},
          {"job_type": "identity", "status": "completed", "runs": 2}
        ]
        """.strip()
    )
    recent_runs = tmp_path / "recent_runs.json"
    recent_runs.write_text(
        """
        [
          {
            "job_type": "costs",
            "tenant_id": "bad-tenant",
            "status": "failed",
            "error_message": "Key Vault credentials not found for tenant bad-tenant"
          }
        ]
        """.strip()
    )
    alerts = tmp_path / "alerts.json"
    alerts.write_text(
        """
        [
          {"is_resolved": false, "title": "Sync failed", "message": "falling back to settings credentials"},
          {"is_resolved": false, "title": "Still broken", "message": "invalid_tenant"}
        ]
        """.strip()
    )

    report = build_report(
        _args(sync_status_json=sync_status, recent_runs_json=recent_runs, alerts_json=alerts)
    )

    assert report["verdict"]["status"] == "blocked"
    assert report["verdict"]["costs_recovered"] is False
    assert report["verdict"]["dominant_remaining_signature"] in {
        "missing_per_tenant_key_vault_credentials",
        "unexpected_shared_settings_fallback",
        "invalid_tenant",
    }
    assert report["alert_summary"]["active_now"] == 2


def test_report_marks_recovery_verified_when_costs_recover_and_alerts_burn_down(tmp_path):
    sync_status = tmp_path / "sync_status.json"
    sync_status.write_text(
        """
        [
          {"job_type": "costs", "status": "completed", "runs": 3},
          {"job_type": "costs", "status": "failed", "runs": 0},
          {"job_type": "compliance", "status": "completed", "runs": 5}
        ]
        """.strip()
    )
    alerts = tmp_path / "alerts.json"
    alerts.write_text(
        """
        [
          {"is_resolved": false, "title": "One real alert", "message": "quota warning"},
          {"is_resolved": true, "title": "Old alert", "message": "resolved"}
        ]
        """.strip()
    )

    report = build_report(_args(sync_status_json=sync_status, alerts_json=alerts))

    assert report["verdict"]["status"] == "verified"
    assert report["verdict"]["costs_recovered"] is True
    assert report["verdict"]["alerts_burned_down"] is True
    assert report["verdict"]["suspicious_signature_total"] == 0


def test_report_understands_app_insights_table_payload(tmp_path):
    traces = tmp_path / "traces.json"
    traces.write_text(
        """
        {
          "tables": [
            {
              "columns": [{"name": "timestamp"}, {"name": "message"}],
              "rows": [["2026-04-24T00:00:00Z", "invalid_tenant for bogus tenant"]]
            }
          ]
        }
        """.strip()
    )

    report = build_report(_args(traces_json=traces))

    assert report["trace_signature_counts"]["invalid_tenant"] == 1
    assert report["verdict"]["status"] == "blocked"


def test_render_markdown_includes_verdict_and_burn_down():
    report = {
        "generated_at": "2026-04-24T12:00:00+00:00",
        "inputs_present": {
            "sync_status": True,
            "recent_runs": True,
            "alerts": True,
            "traces": False,
            "exceptions": False,
        },
        "status_counts": {"costs": {"completed": 2}},
        "recent_failure_summary": {"signature_counts": {}, "examples": {}},
        "alert_summary": {
            "baseline": 222,
            "active_now": 100,
            "burn_down": 122,
            "burn_down_direction": "down",
            "suspicious_signature_counts": {},
        },
        "trace_signature_counts": {},
        "exception_signature_counts": {},
        "verdict": {
            "status": "verified",
            "summary": "All good enough for now.",
        },
    }

    markdown = render_markdown(report)

    assert "Verdict: **verified**" in markdown
    assert "Baseline active alerts: **222**" in markdown
    assert "Burn-down delta: **122**" in markdown
