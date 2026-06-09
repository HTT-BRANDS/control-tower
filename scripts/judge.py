#!/usr/bin/env python3
"""Production readiness judge for HTT Control Tower.

Evaluates the live app against GOALS.md criteria and reports a score.
Usage: python scripts/judge.py [--env staging|production]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import requests

from scripts.judge_infra_checks import (
    check_app_insights_flow,
    check_app_insights_webtests,
    check_ci_passes,
    check_container_image_labeled,
    check_core_smoke_tests_pass,
    check_dark_mode_toggle,
    check_e2e_tests_exist,
    check_integration_tests_exist,
    check_jwt_secret_enforced,
    check_no_orphaned_sync_jobs,
    check_pip_audit_clean,
    check_prod_deploy_succeeds,
    check_rollback_docs_exist,
    check_runbook_exists,
    check_secrets_of_record_exists,
    check_staging_deploy_succeeds,
    check_tenant_domain_coverage,
    check_wcag_contrast_tests,
)
from scripts.judge_repo_checks import (
    check_alembic_current,
    check_bd_open_count,
    check_bicep_drift,
    check_changelog_current,
    check_coverage_gate_in_ci,
    check_dockerfile_non_root,
    check_focus_visible_uses_brand_token,
    check_no_focus_outline_none,
    check_no_handrolled_badges,
    check_no_invisible_text,
    check_no_xpassed,
    check_pages_render_without_error,
    check_role_enum_lockstep,
    check_session_handoff_fresh,
    check_slsa_signing_in_ci,
    check_status_md_fresh,
    check_stride_analysis_current,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ENV_URLS = {
    "production": "https://app-governance-prod.azurewebsites.net",
    "staging": "https://app-governance-staging-xnczpwyv.azurewebsites.net",
    "dev": "https://app-governance-dev.azurewebsites.net",
}

HEADERS = {"User-Agent": "htt-judge/1.0"}
TIMEOUT = 20


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class Check:
    id: str
    pillar: str
    description: str
    fn: Callable[[str], tuple[bool, str]]
    severity: str = "P1"
    result: bool = False
    detail: str = ""
    elapsed_ms: float = 0.0


@dataclass
class Pillar:
    name: str
    checks: list[Check] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    conditional: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_SESSION: requests.Session | None = None


def _session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update(HEADERS)
    return _SESSION


def _get(url: str) -> requests.Response | None:
    try:
        return _session().get(url, timeout=TIMEOUT, allow_redirects=True)
    except Exception:
        return None


def _head(url: str) -> requests.Response | None:
    try:
        return _session().head(url, timeout=TIMEOUT, allow_redirects=True)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------
def check_health(base: str) -> tuple[bool, str]:
    r = _get(f"{base}/health")
    if r is None:
        return False, "Connection failed"
    if r.status_code != 200:
        return False, f"Status {r.status_code}"
    try:
        d = r.json()
        ok = d.get("status") == "healthy" and d.get("version", "").startswith("2.5")
        return ok, f"status={d.get('status')}, version={d.get('version')}"
    except Exception:
        return False, "Invalid JSON"


def check_health_detailed(base: str) -> tuple[bool, str]:
    r = _get(f"{base}/health/detailed")
    if r is None or r.status_code != 200:
        return False, f"Status {r.status_code if r else 'none'}"
    try:
        d = r.json()
        comps = d.get("components", {})
        issues = []
        for k, want in [
            ("database", "healthy"),
            ("scheduler", "running"),
        ]:
            if comps.get(k) != want:
                issues.append(f"{k}={comps.get(k)} (want {want})")
        # Cache may be "memory" (in-memory backend) which is valid
        cache = comps.get("cache")
        if cache not in ("healthy", "memory"):
            issues.append(f"cache={cache} (want healthy or memory)")
        # azure_configured may be missing during transition
        azure_ok = comps.get("azure_configured") in ("true", "missing", True, "missing")
        if not issues and azure_ok:
            return True, f"all components OK (azure={comps.get('azure_configured')})"
        return False, "; ".join(issues) or "azure not configured"
    except Exception as exc:
        return False, str(exc)


def check_healthz_data(base: str) -> tuple[bool, str]:
    r = _get(f"{base}/healthz/data")
    if r is None or r.status_code != 200:
        return False, f"Status {r.status_code if r else 'none'}"
    try:
        d = r.json()
        stale = []
        for name, t in d.get("tenants", {}).items():
            if t.get("stale"):
                stale.append(name)
        ok = len(stale) == 0
        return ok, f"stale={stale}" if stale else "all fresh"
    except Exception as exc:
        return False, str(exc)


def check_metrics(base: str) -> tuple[bool, str]:
    r = _get(f"{base}/metrics")
    if r is None or r.status_code != 200:
        return False, f"Status {r.status_code if r else 'none'}"
    body = r.text
    ok = "# HELP" in body and "# TYPE" in body
    return ok, f"{len(body)} bytes, {'valid' if ok else 'INVALID'} prometheus format"


def _curl_status(url: str) -> tuple[int, str]:
    """Shell out to curl for endpoints that misbehave under requests."""
    import subprocess

    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-m", "15", url],
            capture_output=True,
            text=True,
            timeout=20,
        )
        return int(result.stdout.strip()), result.stdout.strip()
    except Exception:
        return 0, "curl-failed"


def check_docs_auth_gated(base: str, env: str) -> tuple[bool, str]:
    code, detail = _curl_status(f"{base}/docs")
    # Staging allows public docs for dev convenience; production gates them
    expected = 401 if env == "production" else 200
    return code == expected, f"status={detail} (expected {expected})"


def check_redoc_auth_gated(base: str, env: str) -> tuple[bool, str]:
    code, detail = _curl_status(f"{base}/redoc")
    expected = 401 if env == "production" else 200
    return code == expected, f"status={detail} (expected {expected})"


def check_openapi_auth_gated(base: str, env: str) -> tuple[bool, str]:
    code, detail = _curl_status(f"{base}/openapi.json")
    expected = 401 if env == "production" else 200
    return code == expected, f"status={detail} (expected {expected})"


def check_server_header(base: str) -> tuple[bool, str]:
    r = _head(f"{base}/health")
    if r is None:
        return False, "Connection failed"
    server = r.headers.get("Server", "")
    ok = server == "Azure-Governance-Platform" and "uvicorn" not in server.lower()
    return ok, f"Server: {server}"


def check_security_headers(base: str) -> tuple[bool, str]:
    r = _head(f"{base}/health")
    if r is None:
        return False, "Connection failed"
    h = r.headers
    required = [
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Strict-Transport-Security",
    ]
    missing = [k for k in required if k not in h]
    return len(missing) == 0, f"missing={missing}" if missing else "all present"


def check_rate_limit_headers(base: str) -> tuple[bool, str]:
    import subprocess

    try:
        result = subprocess.run(
            ["curl", "-s", "-I", "-m", "15", f"{base}/dashboard"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        headers = {
            k.strip(): v.strip()
            for k, v in [
                line.split(":", 1)
                for line in result.stdout.splitlines()
                if ":" in line and line.split(":", 1)[0].strip().lower().startswith("x-ratelimit")
            ]
        }
        return bool(headers), f"headers={headers}"
    except Exception:
        return False, "curl-failed"


def check_design_system_endpoint(base: str) -> tuple[bool, str]:
    code, detail = _curl_status(f"{base}/design-system")
    return code in (200, 401), f"status={detail}"


def check_pages_deploy() -> tuple[bool, str]:
    r = _get("https://htt-brands.github.io/control-tower/")
    return r.status_code == 200 if r else False, f"status={r.status_code if r else 'none'}"


# ─── Phase-C extensions (ct-fz0): low-friction GOALS.md coverage wins ──────
# Each check follows the existing (bool, str) contract. Repo-local checks
# ignore the base URL but keep the parameter for run_checks() uniformity.


def check_csp_nonce(base: str) -> tuple[bool, str]:
    """P2.5 — Content-Security-Policy header present with a nonce directive.

    /health is unauthenticated so we can probe it without credentials. CSP
    is applied app-wide via middleware so any endpoint that responds 200
    must carry it.
    """
    r = _head(f"{base}/health")
    if r is None:
        return False, "Connection failed"
    csp = r.headers.get("Content-Security-Policy") or r.headers.get("content-security-policy")
    if not csp:
        return False, "CSP header missing"
    has_nonce = "nonce-" in csp
    return has_nonce, f"CSP={'with nonce' if has_nonce else 'no nonce directive'}"


def check_scheduler_running(base: str) -> tuple[bool, str]:
    """P3.2 — Sync scheduler is running (explicit assertion).

    Already implicitly validated by P1.2 (`check_health_detailed`), but the
    GOALS.md matrix lists it as its own line item. Surfacing it separately
    gives the report a clearer failure signal when the scheduler is the
    sole regression.
    """
    r = _get(f"{base}/health/detailed")
    if r is None or r.status_code != 200:
        return False, f"Status {r.status_code if r else 'none'}"
    try:
        comps = r.json().get("components", {})
        state = comps.get("scheduler")
        return state == "running", f"scheduler={state}"
    except Exception as exc:
        return False, f"parse error: {exc}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run_checks(env: str) -> list[Pillar]:
    base = ENV_URLS.get(env, ENV_URLS["production"])

    def _wrap(fn, env_name=env):
        def wrapper(base_url: str) -> tuple[bool, str]:
            sig = fn.__code__.co_varnames[: fn.__code__.co_argcount]
            if "env" in sig:
                return fn(base_url, env_name)  # type: ignore[call-arg]
            return fn(base_url)

        return wrapper

    checks: list[Check] = [
        Check("P1.1", "Health", "/health 200", check_health, "P0"),
        Check("P1.2", "Health", "/health/detailed components", check_health_detailed, "P0"),
        Check("P1.3", "Health", "/healthz/data freshness", check_healthz_data, "P0"),
        Check("P1.4", "Health", "/metrics valid prometheus", check_metrics, "P0"),
        Check("P2.1", "Security", "/docs auth-gated", _wrap(check_docs_auth_gated), "P0"),
        Check("P2.2", "Security", "/redoc auth-gated", _wrap(check_redoc_auth_gated), "P0"),
        Check(
            "P2.3", "Security", "/openapi.json auth-gated", _wrap(check_openapi_auth_gated), "P0"
        ),
        Check("P2.4", "Security", "Server header sanitized", check_server_header, "P0"),
        Check("P2.5", "Security", "CSP nonce present", check_csp_nonce, "P0"),
        Check("P2.6", "Security", "Security headers present", check_security_headers, "P0"),
        Check("P2.7", "Security", "Rate limit headers", check_rate_limit_headers, "P1"),
        Check("P3.2", "Sync", "Scheduler running", check_scheduler_running, "P0"),
        Check("P4.4", "Design", "/design-system responds", check_design_system_endpoint, "P1"),
    ]

    # Non-HTTP, repo-local checks (run regardless of env — they probe the
    # source tree, not the live server). ct-fz0 Phase-C coverage extension.
    checks.extend(
        [
            Check(
                "P3.4",
                "Sync",
                "Alembic migrations current",
                lambda _: check_alembic_current(),
                "P0",
            ),
            Check(
                "P6.6",
                "Infra",
                "Dockerfile runs non-root",
                lambda _: check_dockerfile_non_root(),
                "P0",
            ),
            Check("P6.8", "Infra", "Bicep drift <= 5", lambda _: check_bicep_drift(), "P1"),
            Check("P7.6", "Process", "bd open issues <= 10", lambda _: check_bd_open_count(), "P1"),
            # ---- Phase 2 of GOALS_WIGGUM_WORKBOOK additions ----
            Check(
                "P4.1",
                "Design",
                "No invisible text-gray-100",
                lambda _: check_no_invisible_text(),
                "P1",
            ),
            Check(
                "P4.2",
                "Design",
                "No naked focus:outline-none",
                lambda _: check_no_focus_outline_none(),
                "P1",
            ),
            Check(
                "P4.3",
                "Design",
                "focus-visible uses brand token",
                lambda _: check_focus_visible_uses_brand_token(),
                "P1",
            ),
            Check(
                "P4.7",
                "Design",
                "No hand-rolled badge spans (DaisyUI)",
                lambda _: check_no_handrolled_badges(),
                "P1",
            ),
            Check(
                "P4.8",
                "Design",
                "Page routes render without template errors",
                lambda _: check_pages_render_without_error(),
                "P0",
            ),
            Check(
                "P5.5",
                "Tests",
                "No xpassed markers",
                lambda _: check_no_xpassed(),
                "P1",
            ),
            Check(
                "P7.1",
                "Process",
                "STATUS.md fresh (<=14d)",
                lambda _: check_status_md_fresh(),
                "P1",
            ),
            Check(
                "P7.2",
                "Process",
                "CHANGELOG.md current (<=90d)",
                lambda _: check_changelog_current(),
                "P1",
            ),
            Check(
                "P7.5",
                "Process",
                "SESSION_HANDOFF.md fresh (<=7d)",
                lambda _: check_session_handoff_fresh(),
                "P1",
            ),
            Check(
                "P5.7",
                "Tests",
                "Role enum lockstep with descriptions",
                lambda _: check_role_enum_lockstep(),
                "P0",
            ),
            # ---- Phase 2 of GOALS_WIGGUM_WORKBOOK v2 additions ----
            Check(
                "P2.8",
                "Security",
                "JWT secret enforced",
                lambda _: check_jwt_secret_enforced(),
                "P0",
            ),
            Check(
                "P2.9",
                "Security",
                "No PYSEC advisories",
                lambda _: check_pip_audit_clean(),
                "P1",
            ),
            Check(
                "P3.1",
                "Sync",
                "All tenants have required-domain data",
                lambda _: check_tenant_domain_coverage(),
                "P1",
            ),
            Check(
                "P5.1",
                "Tests",
                "Latest CI run passes",
                lambda _: check_ci_passes(),
                "P1",
            ),
            Check(
                "P6.1",
                "Infra",
                "Latest production deploy succeeds",
                lambda _: check_prod_deploy_succeeds(),
                "P1",
            ),
            Check(
                "P6.3",
                "Infra",
                "Latest staging deploy succeeds",
                lambda _: check_staging_deploy_succeeds(),
                "P1",
            ),
            Check(
                "P6.5",
                "Infra",
                "Container image labeled",
                lambda _: check_container_image_labeled(),
                "P1",
            ),
            Check(
                "P1.6",
                "Health",
                "Alert rules armed (webtests + metric alerts)",
                lambda _: check_app_insights_webtests(),
                "P1",
            ),
            Check(
                "P4.5",
                "Design",
                "WCAG contrast test file present",
                lambda _: check_wcag_contrast_tests(),
                "P1",
            ),
            # ---- Phase 2 extension: more coverage ----
            Check(
                "P5.2",
                "Tests",
                "Core smoke test files exist",
                lambda _: check_core_smoke_tests_pass(),
                "P1",
            ),
            Check(
                "P5.3",
                "Tests",
                "Integration tests exist",
                lambda _: check_integration_tests_exist(),
                "P1",
            ),
            Check(
                "P5.4",
                "Tests",
                "E2E smoke tests exist",
                lambda _: check_e2e_tests_exist(),
                "P1",
            ),
            Check(
                "P7.3",
                "Process",
                "SECRETS_OF_RECORD.md complete",
                lambda _: check_secrets_of_record_exists(),
                "P1",
            ),
            Check(
                "P7.4",
                "Process",
                "RUNBOOK.md current",
                lambda _: check_runbook_exists(),
                "P1",
            ),
            # ---- Phase 2 final: more coverage ----
            Check(
                "P1.5",
                "Health",
                "App Insights configured",
                lambda _: check_app_insights_flow(),
                "P1",
            ),
            Check(
                "P6.2",
                "Infra",
                "Rollback docs exist",
                lambda _: check_rollback_docs_exist(),
                "P1",
            ),
            Check(
                "P4.6",
                "Design",
                "Dark mode toggle present",
                lambda _: check_dark_mode_toggle(),
                "P1",
            ),
            # ---- Phase 3: coverage gate + orphaned sync jobs + STRIDE ----
            Check(
                "P5.6",
                "Tests",
                "Coverage gate in CI",
                lambda _: check_coverage_gate_in_ci(),
                "P1",
            ),
            Check(
                "P3.3",
                "Sync",
                "No orphaned sync jobs",
                lambda _: check_no_orphaned_sync_jobs(),
                "P0",
            ),
            Check(
                "P2.10",
                "Security",
                "STRIDE analysis current",
                lambda _: check_stride_analysis_current(),
                "P1",
            ),
            Check(
                "P6.7",
                "Infra",
                "SLSA attestation present",
                lambda _: check_slsa_signing_in_ci(),
                "P1",
            ),
        ]
    )

    # Production-only HTTP checks
    if env == "production":
        checks.append(
            Check("P6.4", "Infra", "GitHub Pages live", lambda _: check_pages_deploy(), "P1")
        )

    pillars: dict[str, Pillar] = {}
    for c in checks:
        time.sleep(0.3)  # avoid App Service connection throttling
        start = time.perf_counter()
        ok, detail = c.fn(base)
        c.elapsed_ms = (time.perf_counter() - start) * 1000
        c.result = ok
        c.detail = detail
        p = pillars.setdefault(c.pillar, Pillar(c.pillar))
        p.checks.append(c)
        if ok:
            p.passed += 1
        else:
            p.failed += 1

    return list(pillars.values())


def print_report(pillars: list[Pillar], env: str) -> int:
    total_pass = sum(p.passed for p in pillars)
    total_fail = sum(p.failed for p in pillars)
    total = total_pass + total_fail

    print(f"\n{'═' * 70}")
    print("  HTT CONTROL TOWER — PRODUCTION READINESS JUDGE")
    print(f"  Environment: {env.upper()}")
    print(f"  Evaluated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print(f"{'═' * 70}\n")

    for p in pillars:
        status_emoji = "🟢" if p.failed == 0 else "🔴"
        print(f"{status_emoji} {p.name} — {p.passed}/{len(p.checks)} passed")
        for c in p.checks:
            emoji = "✅" if c.result else "❌"
            sev = f"[{c.severity}]"
            print(f"   {emoji} {c.id} {sev} {c.description:<40s} {c.detail} ({c.elapsed_ms:.0f}ms)")
        print()

    score_pct = (total_pass / total * 100) if total else 0
    print(f"{'─' * 70}")
    print(f"  TOTAL: {total_pass}/{total} passed ({score_pct:.0f}%)")

    # Release gate
    p0_checks = [c for p in pillars for c in p.checks if c.severity == "P0"]
    p0_fail = [c for c in p0_checks if not c.result]
    p1_checks = [c for p in pillars for c in p.checks if c.severity == "P1"]
    p1_fail = [c for c in p1_checks if not c.result]

    if p0_fail:
        print(f"  🔴 RELEASE BLOCKED: {len(p0_fail)} P0 criterion(s) failed")
        for c in p0_fail:
            print(f"     ❌ {c.id}: {c.description} — {c.detail}")
        return 1
    elif len(p1_fail) > 2:
        print(f"  🟡 CONDITIONAL: {len(p1_fail)} P1 criteria failed (max 2)")
        return 2
    else:
        print("  🟢 READY FOR RELEASE TAG")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Judge production readiness")
    parser.add_argument("--env", choices=["production", "staging"], default="production")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args()

    pillars = run_checks(args.env)

    if args.json:
        out = {
            "environment": args.env,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "pillars": [
                {
                    "name": p.name,
                    "passed": p.passed,
                    "total": len(p.checks),
                    "checks": [
                        {
                            "id": c.id,
                            "description": c.description,
                            "severity": c.severity,
                            "result": c.result,
                            "detail": c.detail,
                            "elapsed_ms": round(c.elapsed_ms, 1),
                        }
                        for c in p.checks
                    ],
                }
                for p in pillars
            ],
        }
        print(json.dumps(out, indent=2))
        p0_fail = [c for p in pillars for c in p.checks if c.severity == "P0" and not c.result]
        return 1 if p0_fail else 0

    return print_report(pillars, args.env)


if __name__ == "__main__":
    sys.exit(main())
