"""Diagnose sync health across all tenants and identify configuration gaps.

Usage:
    python scripts/diagnose_sync.py [--env production|staging|dev]

This script queries the production API's /healthz/data endpoint and
correlates with tenant metadata to identify which tenants have sync
gaps and which domains are missing.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class TenantHealth:
    name: str
    resources: str | None
    costs: str | None
    compliance: str | None
    identity: str | None
    dmarc: str | None
    dkim: str | None
    riverside_compliance: str | None
    riverside_mfa: str | None
    stale: bool | None
    optional_stale: bool | None

    @property
    def missing_required(self) -> list[str]:
        """Domains that MUST be present for a healthy tenant."""
        missing = []
        for domain in ["resources", "costs", "compliance", "identity"]:
            if getattr(self, domain) is None:
                missing.append(domain)
        return missing

    @property
    def is_healthy(self) -> bool:
        return not self.missing_required


def fetch_json(url: str, timeout: int = 15) -> dict:
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def diagnose(env: str) -> dict:
    urls = {
        "production": "https://app-governance-prod.azurewebsites.net",
        "staging": "https://app-governance-staging.azurewebsites.net",
        "dev": "https://app-governance-dev.azurewebsites.net",
    }
    base = urls.get(env, env)

    healthz = fetch_json(f"{base}/healthz/data")
    tenants_raw = healthz.get("tenants", {})

    tenants: list[TenantHealth] = []
    for name, data in tenants_raw.items():
        tenants.append(
            TenantHealth(
                name=name,
                resources=data.get("resources"),
                costs=data.get("costs"),
                compliance=data.get("compliance"),
                identity=data.get("identity"),
                dmarc=data.get("dmarc"),
                dkim=data.get("dkim"),
                riverside_compliance=data.get("riverside_compliance"),
                riverside_mfa=data.get("riverside_mfa"),
                stale=data.get("stale"),
                optional_stale=data.get("optional_stale"),
            )
        )

    return {
        "environment": env,
        "url": base,
        "any_stale": healthz.get("any_stale"),
        "tenants": tenants,
    }


def render(result: dict) -> None:
    print(f"\n╔{'═' * 69}╗")
    print(f"║  Sync Diagnostic — {result['environment']:12s} — {result['url']:<30s} ║")
    print(f"╚{'═' * 69}╝\n")

    healthy = [t for t in result["tenants"] if t.is_healthy]
    unhealthy = [t for t in result["tenants"] if not t.is_healthy]

    print(f"Summary: {len(healthy)}/{len(result['tenants'])} tenants fully synced")
    print(f"Any stale: {result['any_stale']}\n")

    if healthy:
        print("Healthy tenants:")
        for t in healthy:
            print(f"  ✅ {t.name}")

    if unhealthy:
        print("\nTenants with gaps:")
        for t in unhealthy:
            print(f"  🔴 {t.name}: missing {t.missing_required}")

    # Check for partial syncs (some domains work, others don't)
    partial = [
        t
        for t in result["tenants"]
        if t.missing_required
        and any(getattr(t, d) for d in ["resources", "costs", "compliance", "identity"])
    ]
    if partial:
        print("\nPartial syncs (some domains work — suggests tenant-specific config issue):")
        for t in partial:
            working = [d for d in ["resources", "costs", "compliance", "identity"] if getattr(t, d)]
            print(f"  🟡 {t.name}: works={working}, missing={t.missing_required}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose sync health")
    parser.add_argument("--env", default="production", choices=["production", "staging", "dev"])
    args = parser.parse_args()

    try:
        result = diagnose(args.env)
        render(result)
    except Exception as e:
        print(f"❌ Diagnostic failed: {e}", file=sys.stderr)
        return 1

    # Exit code = number of unhealthy tenants (0 = all healthy)
    unhealthy_count = sum(1 for t in result["tenants"] if not t.is_healthy)
    return min(unhealthy_count, 1)


if __name__ == "__main__":
    sys.exit(main())
