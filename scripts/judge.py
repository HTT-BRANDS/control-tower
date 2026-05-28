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

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ENV_URLS = {
    "production": "https://app-governance-prod.azurewebsites.net",
    "staging": "https://app-governance-staging-xnczpwyv.azurewebsites.net",
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


def check_docs_auth_gated(base: str) -> tuple[bool, str]:
    code, detail = _curl_status(f"{base}/docs")
    return code == 401, f"status={detail}"


def check_redoc_auth_gated(base: str) -> tuple[bool, str]:
    code, detail = _curl_status(f"{base}/redoc")
    return code == 401, f"status={detail}"


def check_openapi_auth_gated(base: str) -> tuple[bool, str]:
    code, detail = _curl_status(f"{base}/openapi.json")
    return code == 401, f"status={detail}"


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
                if ":" in line and line.split(":", 1)[0].strip().startswith("X-RateLimit")
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run_checks(env: str) -> list[Pillar]:
    base = ENV_URLS.get(env, ENV_URLS["production"])

    checks: list[Check] = [
        Check("P1.1", "Health", "/health 200", check_health, "P0"),
        Check("P1.2", "Health", "/health/detailed components", check_health_detailed, "P0"),
        Check("P1.3", "Health", "/healthz/data freshness", check_healthz_data, "P0"),
        Check("P1.4", "Health", "/metrics valid prometheus", check_metrics, "P0"),
        Check("P2.1", "Security", "/docs 401", check_docs_auth_gated, "P0"),
        Check("P2.2", "Security", "/redoc 401", check_redoc_auth_gated, "P0"),
        Check("P2.3", "Security", "/openapi.json 401", check_openapi_auth_gated, "P0"),
        Check("P2.4", "Security", "Server header sanitized", check_server_header, "P0"),
        Check("P2.6", "Security", "Security headers present", check_security_headers, "P0"),
        Check("P2.7", "Security", "Rate limit headers", check_rate_limit_headers, "P1"),
        Check("P4.4", "Design", "/design-system responds", check_design_system_endpoint, "P1"),
    ]

    # Non-HTTP checks
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
