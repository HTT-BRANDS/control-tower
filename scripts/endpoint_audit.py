#!/usr/bin/env python3
"""Comprehensive endpoint audit with data-quality heuristics.

Diagnoses "the dashboard is blank" problems by:

1. **Discovering** every GET endpoint from /openapi.json (no hardcoded list).
2. **Hitting** each one (auth optional) and recording status, latency, size.
3. **Flagging "silently blank"** responses — endpoints that return 200 OK
   but with empty arrays, null `last_synced`, all-zero totals, etc.

Usage:
    # Unauthenticated sweep (still useful — health endpoints, 401 surface)
    python scripts/endpoint_audit.py --url https://app-governance-prod.azurewebsites.net

    # With auth via username/password
    python scripts/endpoint_audit.py \\
        --url https://app-governance-staging-xnczpwyv.azurewebsites.net \\
        --username you@example.com --password '...'

    # With pre-existing bearer token (e.g., grabbed from browser devtools)
    AUDIT_TOKEN=eyJ... python scripts/endpoint_audit.py --url https://...

    # Multiple envs at once
    python scripts/endpoint_audit.py \\
        --url https://app-governance-staging-xnczpwyv.azurewebsites.net \\
        --url https://app-governance-prod.azurewebsites.net

Exit codes:
    0 — every endpoint healthy & populated
    1 — at least one endpoint silently blank or returned 5xx
    2 — could not reach the server / config error
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import httpx
except ImportError:
    print("❌ httpx is required. Install with: uv add httpx", file=sys.stderr)
    sys.exit(2)


# ============================================================================
# Constants — single source of truth for "what counts as blank"
# ============================================================================

# Keys whose values, if all-zero, suggest no data is flowing through the API.
# Kept as a tuple so it is iterable and ordering is preserved for reports.
NUMERIC_SUMMARY_KEYS: tuple[str, ...] = (
    "total_cost",
    "total_resources",
    "total_users",
    "total_alerts",
    "compliance_score",
    "active_count",
    "count",
    "total",
)

# Container-shaped keys; an empty list/dict here is the classic "blank UI" signal.
COLLECTION_KEYS: tuple[str, ...] = (
    "items",
    "resources",
    "alerts",
    "logs",
    "results",
    "data",
    "tenants",
    "users",
    "subscriptions",
    "findings",
    "recommendations",
    "records",
)

# Freshness-style keys — a `None` value means "we have never synced".
FRESHNESS_KEYS: tuple[str, ...] = (
    "last_synced",
    "last_sync",
    "started_at",
    "last_run",
    "updated_at",
)

# Endpoints we never call (mutating, async, or otherwise dangerous to probe).
EXCLUDED_PATH_PATTERNS: tuple[str, ...] = (
    "/logout",
    "/export",  # may generate large files
    "/download",
    "/refresh",  # token refresh has side effects
    "{",  # paths with required path params; we can't fill them blindly
)


# ============================================================================
# Result types
# ============================================================================


@dataclass
class EndpointResult:
    """Outcome of probing a single endpoint."""

    path: str
    status_code: int
    latency_ms: float
    response_size: int
    verdict: str  # "ok" | "blank" | "auth_required" | "error" | "unreachable"
    blank_reasons: list[str] = field(default_factory=list)
    error: str | None = None
    sample: dict[str, Any] | None = None  # tiny preview for the report


@dataclass
class EnvAuditReport:
    """All endpoint results for a single target environment."""

    base_url: str
    started_at: str
    finished_at: str = ""
    authenticated: bool = False
    auth_method: str = "none"
    results: list[EndpointResult] = field(default_factory=list)

    def summary(self) -> dict[str, int]:
        """Bucket results by verdict for the headline numbers."""
        buckets: dict[str, int] = {}
        for r in self.results:
            buckets[r.verdict] = buckets.get(r.verdict, 0) + 1
        return buckets


# ============================================================================
# Data-quality heuristics — the "is this response silently blank?" brain
# ============================================================================


def detect_blank_signals(payload: Any) -> list[str]:
    """Inspect a JSON response and return human-readable 'blank' reasons.

    Empty list ⇒ response looks populated.

    We deliberately keep this conservative: only well-known shapes are flagged.
    A 200 OK with rich nested data we don't recognize is *not* assumed blank.
    """
    reasons: list[str] = []

    if payload is None:
        return ["response body is null"]
    if isinstance(payload, list):
        if len(payload) == 0:
            reasons.append("top-level array is empty")
        return reasons
    if not isinstance(payload, dict):
        # Strings/bytes/numbers at top level — not our concern.
        return reasons

    for key in COLLECTION_KEYS:
        value = payload.get(key)
        if isinstance(value, list) and len(value) == 0:
            reasons.append(f"'{key}' array is empty")

    for key in FRESHNESS_KEYS:
        if key in payload and payload[key] in (None, "", 0):
            reasons.append(f"'{key}' is unset — never synced?")

    # last_synced dict (e.g., dashboard's per-job-type mapping)
    last_synced = payload.get("last_synced")
    if isinstance(last_synced, dict) and last_synced:
        unset = [k for k, v in last_synced.items() if v in (None, "", 0)]
        if unset and len(unset) == len(last_synced):
            reasons.append(f"all sync types unset ({', '.join(unset)}) — scheduler not running?")
        elif unset:
            reasons.append(f"sync types never run: {', '.join(unset)}")

    # All-zero numeric summary → no data flowing
    seen_numeric = {k: payload[k] for k in NUMERIC_SUMMARY_KEYS if k in payload}
    if seen_numeric and all(v in (0, 0.0, None) for v in seen_numeric.values()):
        reasons.append(
            f"all numeric summary fields are zero/null ({', '.join(seen_numeric.keys())})"
        )

    return reasons


def shrink_for_preview(payload: Any, max_chars: int = 400) -> dict[str, Any] | None:
    """Trim a payload down to something digestible for the report."""
    if not isinstance(payload, dict):
        return None
    preview: dict[str, Any] = {}
    for k, v in list(payload.items())[:8]:
        if isinstance(v, list):
            preview[k] = f"<list len={len(v)}>"
        elif isinstance(v, dict):
            preview[k] = f"<dict keys={list(v.keys())[:5]}>"
        else:
            s = str(v)
            preview[k] = s if len(s) <= max_chars else s[:max_chars] + "…"
    return preview


# ============================================================================
# The auditor
# ============================================================================


class EndpointAuditor:
    """Audits all GET endpoints on a single base URL."""

    def __init__(
        self,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        bearer_token: str | None = None,
        verbose: bool = False,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.bearer_token = bearer_token
        self.verbose = verbose
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------ session

    async def __aenter__(self) -> EndpointAuditor:
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=False,  # we want to *see* 302s, not chase them
        )
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        assert self._client is not None, "Use 'async with EndpointAuditor(...)'"
        return self._client

    # --------------------------------------------------------------- auth flow

    async def authenticate(self) -> tuple[bool, str]:
        """Return (success, method). Method ∈ {none, bearer, password}."""
        if self.bearer_token:
            return True, "bearer"
        if not (self.username and self.password):
            return False, "none"

        try:
            resp = await self.client.post(
                "/api/v1/auth/login",
                data={"username": self.username, "password": self.password},
            )
        except httpx.HTTPError as exc:
            if self.verbose:
                print(f"  auth network error: {exc}", file=sys.stderr)
            return False, "none"

        if resp.status_code != 200:
            if self.verbose:
                print(
                    f"  auth failed: HTTP {resp.status_code} — {resp.text[:200]}",
                    file=sys.stderr,
                )
            return False, "none"

        try:
            self.bearer_token = resp.json().get("access_token")
        except ValueError:
            return False, "none"
        return bool(self.bearer_token), "password"

    def _headers(self) -> dict[str, str]:
        if self.bearer_token:
            return {"Authorization": f"Bearer {self.bearer_token}"}
        return {}

    # ------------------------------------------------------------ discovery

    async def discover_get_paths(self) -> list[str]:
        """Pull every parameterless GET path from /openapi.json."""
        try:
            resp = await self.client.get("/openapi.json")
        except httpx.HTTPError as exc:
            print(f"⚠️  could not fetch /openapi.json: {exc}", file=sys.stderr)
            return self._fallback_paths()

        if resp.status_code != 200:
            print(
                f"⚠️  /openapi.json returned {resp.status_code}; "
                "falling back to a hardcoded short-list",
                file=sys.stderr,
            )
            return self._fallback_paths()

        spec = resp.json()
        paths: list[str] = []
        for path, methods in spec.get("paths", {}).items():
            if "get" not in methods:
                continue
            if any(token in path for token in EXCLUDED_PATH_PATTERNS):
                continue
            paths.append(path)
        return sorted(paths)

    @staticmethod
    def _fallback_paths() -> list[str]:
        """Used only if /openapi.json is unreachable — keeps the tool useful."""
        return [
            "/health",
            "/health/detailed",
            "/healthz/data",
            "/api/v1/status",
            "/api/v1/auth/health",
            "/api/v1/dashboard",
            "/metrics",
        ]

    # -------------------------------------------------------------- probing

    async def probe(self, path: str) -> EndpointResult:
        """Hit one endpoint, classify the response."""
        start = time.perf_counter()
        try:
            resp = await self.client.get(path, headers=self._headers())
        except httpx.HTTPError as exc:
            latency = (time.perf_counter() - start) * 1000
            return EndpointResult(
                path=path,
                status_code=0,
                latency_ms=latency,
                response_size=0,
                verdict="unreachable",
                error=str(exc),
            )

        latency = (time.perf_counter() - start) * 1000
        body_bytes = resp.content or b""
        size = len(body_bytes)

        # Classify by HTTP status first; the JSON body only matters on 2xx.
        if resp.status_code in (401, 403):
            return EndpointResult(
                path=path,
                status_code=resp.status_code,
                latency_ms=latency,
                response_size=size,
                verdict="auth_required",
            )
        if resp.status_code >= 500:
            return EndpointResult(
                path=path,
                status_code=resp.status_code,
                latency_ms=latency,
                response_size=size,
                verdict="error",
                error=resp.text[:300],
            )
        if resp.status_code >= 400:
            return EndpointResult(
                path=path,
                status_code=resp.status_code,
                latency_ms=latency,
                response_size=size,
                verdict="error",
                error=resp.text[:300],
            )
        if 300 <= resp.status_code < 400:
            # Redirect (e.g., unauth → /auth/login). Treat as auth gate.
            return EndpointResult(
                path=path,
                status_code=resp.status_code,
                latency_ms=latency,
                response_size=size,
                verdict="auth_required",
                error=f"redirect to {resp.headers.get('location', '?')}",
            )

        # 2xx — inspect for "silently blank" signals
        try:
            payload = resp.json()
        except ValueError:
            # HTML or text — we can't reason about emptiness here; report ok.
            return EndpointResult(
                path=path,
                status_code=resp.status_code,
                latency_ms=latency,
                response_size=size,
                verdict="ok",
            )

        blank = detect_blank_signals(payload)
        return EndpointResult(
            path=path,
            status_code=resp.status_code,
            latency_ms=latency,
            response_size=size,
            verdict="blank" if blank else "ok",
            blank_reasons=blank,
            sample=shrink_for_preview(payload),
        )

    # --------------------------------------------------------------- driver

    async def run(self) -> EnvAuditReport:
        """End-to-end: auth → discover → probe all → return report."""
        report = EnvAuditReport(
            base_url=self.base_url,
            started_at=datetime.now(UTC).isoformat(),
        )

        authed, method = await self.authenticate()
        report.authenticated = authed
        report.auth_method = method
        if self.verbose:
            print(f"  auth: {method} ({'ok' if authed else 'skipped/failed'})")

        paths = await self.discover_get_paths()
        if self.verbose:
            print(f"  discovered {len(paths)} GET paths")

        # Bounded concurrency — be polite to App Service / Free SKU.
        semaphore = asyncio.Semaphore(6)

        async def _bounded(path: str) -> EndpointResult:
            async with semaphore:
                return await self.probe(path)

        report.results = await asyncio.gather(*(_bounded(p) for p in paths))
        report.finished_at = datetime.now(UTC).isoformat()
        return report


# ============================================================================
# Reporting
# ============================================================================

VERDICT_GLYPHS: dict[str, str] = {
    "ok": "✅",
    "blank": "⚠️ ",
    "auth_required": "🔒",
    "error": "❌",
    "unreachable": "💀",
}


def print_console_report(report: EnvAuditReport) -> None:
    """Human-readable summary for one env."""
    print()
    print("=" * 78)
    print(f"📍 {report.base_url}")
    print(
        f"   auth={report.auth_method}  "
        f"endpoints={len(report.results)}  "
        f"{report.started_at} → {report.finished_at}"
    )
    print("=" * 78)

    summary = report.summary()
    summary_line = "  ".join(
        f"{VERDICT_GLYPHS.get(k, '?')} {k}={v}" for k, v in sorted(summary.items())
    )
    print(f"  {summary_line}")
    print()

    # Sort: errors first, then blank, then auth-required, then ok
    priority = {"error": 0, "unreachable": 1, "blank": 2, "auth_required": 3, "ok": 4}
    ordered = sorted(report.results, key=lambda r: (priority.get(r.verdict, 9), r.path))

    for r in ordered:
        glyph = VERDICT_GLYPHS.get(r.verdict, "?")
        line = (
            f"  {glyph} {r.verdict:14s} "
            f"{r.status_code:3d}  {r.latency_ms:6.0f}ms  "
            f"{r.response_size:7d}B  {r.path}"
        )
        print(line)
        for reason in r.blank_reasons:
            print(f"        ↳ {reason}")
        if r.error:
            err_line = r.error.replace("\n", " ")[:140]
            print(f"        ↳ {err_line}")


def diagnose_blank_dashboard(report: EnvAuditReport) -> list[str]:
    """Turn raw results into actionable hypotheses for Tyler's blank-dashboard pain."""
    hypotheses: list[str] = []

    by_path = {r.path: r for r in report.results}

    # Dashboard SSR endpoint
    dash = by_path.get("/dashboard")
    if dash and dash.verdict == "auth_required":
        hypotheses.append(
            "🔒 /dashboard requires auth — confirm browser session is sending "
            "the access_token cookie. Login fix may have changed cookie name/SameSite."
        )

    # Look at partial-card endpoints — these mirror the dashboard's SSR services
    partial_paths = [
        "/partials/cost-summary-card",
        "/partials/compliance-gauge",
        "/partials/resource-stats",
        "/partials/identity-stats",
    ]
    blank_partials = [p for p in partial_paths if (r := by_path.get(p)) and r.verdict == "blank"]
    if blank_partials:
        hypotheses.append(
            "⚠️  These dashboard partials returned 200 OK but EMPTY — the underlying "
            f"services have no data: {', '.join(blank_partials)}"
        )

    # Sync / scheduler state
    sync_status = by_path.get("/api/v1/sync/status") or by_path.get("/api/v1/status")
    if sync_status and sync_status.verdict in ("blank", "ok"):
        for reason in sync_status.blank_reasons:
            if "scheduler" in reason or "sync" in reason:
                hypotheses.append(f"📅 {sync_status.path}: {reason}")

    # Auth-protected health
    detailed = by_path.get("/health/detailed")
    if detailed and detailed.verdict == "ok" and detailed.sample:
        components = detailed.sample.get("components", "")
        if "not_running" in str(components):
            hypotheses.append(
                "📅 /health/detailed shows scheduler not_running — APScheduler isn't "
                "firing sync jobs. No fresh data ⇒ blank dashboard."
            )

    # 5xxs anywhere are an obvious smoking gun
    errors = [r for r in report.results if r.verdict == "error" and r.status_code >= 500]
    if errors:
        hypotheses.append(
            f"❌ {len(errors)} endpoints returning 5xx — backend errors. "
            f"First: {errors[0].path} → {errors[0].error or 'no body'}"
        )

    if not hypotheses:
        hypotheses.append(
            "🤔 No obvious blank-data signal in unauth probe. "
            "Re-run with credentials (or use QA Kitten with a real browser session) "
            "to inspect authenticated dashboard partials."
        )

    return hypotheses


def write_json_report(report: EnvAuditReport, out_dir: Path) -> Path:
    """Persist the full report to reports/endpoint_audit_<host>_<ts>.json."""
    out_dir.mkdir(parents=True, exist_ok=True)
    host = urlparse(report.base_url).hostname or "unknown"
    safe_host = host.replace(".", "_")
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"endpoint_audit_{safe_host}_{ts}.json"
    path.write_text(json.dumps(asdict(report), indent=2, default=str))
    return path


# ============================================================================
# CLI
# ============================================================================


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Comprehensive GET-endpoint audit with data-quality checks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--url",
        action="append",
        required=True,
        help="Base URL to audit (repeatable for multiple envs).",
    )
    p.add_argument("--username", help="Login username (overrides AUDIT_USERNAME).")
    p.add_argument("--password", help="Login password (overrides AUDIT_PASSWORD).")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("reports"),
        help="Where to write JSON reports (default: ./reports/).",
    )
    p.add_argument(
        "--no-write",
        action="store_true",
        help="Skip writing JSON files (console output only).",
    )
    return p


async def _audit_one(
    url: str,
    *,
    username: str | None,
    password: str | None,
    bearer: str | None,
    verbose: bool,
) -> EnvAuditReport:
    print(f"\n🔍 Auditing {url} ...")
    async with EndpointAuditor(
        base_url=url,
        username=username,
        password=password,
        bearer_token=bearer,
        verbose=verbose,
    ) as auditor:
        return await auditor.run()


async def _main_async(args: argparse.Namespace) -> int:
    username = args.username or os.getenv("AUDIT_USERNAME")
    password = args.password or os.getenv("AUDIT_PASSWORD")
    bearer = os.getenv("AUDIT_TOKEN")

    reports = await asyncio.gather(
        *(
            _audit_one(
                url,
                username=username,
                password=password,
                bearer=bearer,
                verbose=args.verbose,
            )
            for url in args.url
        )
    )

    exit_code = 0
    for report in reports:
        print_console_report(report)

        print("\n💡 Hypotheses for blank-dashboard:")
        for h in diagnose_blank_dashboard(report):
            print(f"   {h}")

        if not args.no_write:
            out = write_json_report(report, args.reports_dir)
            print(f"\n📝 wrote {out}")

        summary = report.summary()
        if summary.get("error") or summary.get("unreachable") or summary.get("blank"):
            exit_code = 1

    return exit_code


def main() -> int:
    args = _build_parser().parse_args()
    try:
        return asyncio.run(_main_async(args))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
