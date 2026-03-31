#!/usr/bin/env python3
"""Manual sync trigger + data validation for production.

Usage:
    python scripts/manual_sync.py                 # Run all syncs + validate
    python scripts/manual_sync.py --sync-only     # Just trigger syncs
    python scripts/manual_sync.py --validate-only  # Just validate existing data
"""

import argparse
import json
import sys
import time
from datetime import UTC, datetime, timedelta

import httpx
import jwt

# ---------------------------------------------------------------------------
# Configuration — pulled from App Service settings
# ---------------------------------------------------------------------------
PROD_URL = "https://app-governance-prod.azurewebsites.net"

JWT_SECRET = "gc8A0RjZwv15CCG0h98_4nYc1syUjxG9yav26Km7azw"  # pragma: allowlist secret
JWT_ALGORITHM = "HS256"

TENANT_IDS = [
    "0c0e35dc-188a-4eb3-b8ba-61752154b407",  # HTT
    "b5380912-79ec-452d-a6ca-6d897b19b294",  # BCC
    "98723287-044b-4bbb-9294-19857d4128a0",  # FN
    "3c7d2bf3-b597-4766-b5cb-2b489c2904d6",  # TLL
    "ce62e17d-2feb-4e67-a115-8ea4af68da30",  # DCE
]

TENANT_NAMES = {
    "0c0e35dc-188a-4eb3-b8ba-61752154b407": "HTT",
    "b5380912-79ec-452d-a6ca-6d897b19b294": "BCC",
    "98723287-044b-4bbb-9294-19857d4128a0": "FN",
    "3c7d2bf3-b597-4766-b5cb-2b489c2904d6": "TLL",
    "ce62e17d-2feb-4e67-a115-8ea4af68da30": "DCE",
}

# All sync types the scheduler supports
SYNC_TYPES = ["costs", "compliance", "resources", "identity"]
RIVERSIDE_SYNCS = ["hourly_mfa", "daily_full"]


def mint_admin_token() -> str:
    """Create a short-lived admin JWT for production API calls."""
    payload = {
        "sub": "manual-sync-operator",
        "email": "tyler.granlund-admin@httbrands.com",
        "name": "Manual Sync Operator",
        "roles": ["admin", "operator"],
        "tenant_ids": TENANT_IDS,
        "exp": datetime.now(UTC) + timedelta(minutes=30),
        "iat": datetime.now(UTC),
        "iss": "azure-governance-platform",
        "aud": "azure-governance-api",
        "jti": f"manual-sync-{int(time.time())}",
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def make_client() -> httpx.Client:
    """Create an authenticated HTTP client."""
    token = mint_admin_token()
    return httpx.Client(
        base_url=PROD_URL,
        headers={"Authorization": f"Bearer {token}"},
        timeout=300,  # Syncs can take a while
    )


# ---------------------------------------------------------------------------
# Sync triggers
# ---------------------------------------------------------------------------


def trigger_infrastructure_syncs(client: httpx.Client) -> dict:
    """Trigger costs, compliance, resources, identity syncs."""
    results = {}
    for sync_type in SYNC_TYPES:
        print(f"  ⏳ Triggering {sync_type} sync...", end=" ", flush=True)
        try:
            resp = client.post(f"/api/v1/sync/{sync_type}")
            if resp.status_code == 200:
                print(f"✅ triggered")
                results[sync_type] = "triggered"
            elif resp.status_code == 429:
                print(f"⚠️ rate limited (sync may already be running)")
                results[sync_type] = "rate_limited"
            else:
                print(f"❌ {resp.status_code}: {resp.text[:100]}")
                results[sync_type] = f"error_{resp.status_code}"
        except Exception as e:
            print(f"❌ {e}")
            results[sync_type] = f"error: {e}"
    return results


def trigger_riverside_sync(client: httpx.Client) -> dict:
    """Trigger the Riverside MFA + full sync."""
    print("  ⏳ Triggering Riverside full sync...", end=" ", flush=True)
    try:
        resp = client.post("/api/v1/riverside/sync")
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ {data}")
            return data
        else:
            print(f"❌ {resp.status_code}: {resp.text[:200]}")
            return {"error": resp.status_code, "detail": resp.text[:200]}
    except Exception as e:
        print(f"❌ {e}")
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Data validation
# ---------------------------------------------------------------------------


def validate_sync_health(client: httpx.Client) -> dict:
    """Check sync job health metrics."""
    print("\n📊 Sync Health:")
    try:
        resp = client.get("/api/v1/sync/status/health")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  Status: {json.dumps(data, indent=2)[:500]}")
            return data
        else:
            print(f"  ❌ {resp.status_code}: {resp.text[:100]}")
            return {}
    except Exception as e:
        print(f"  ❌ {e}")
        return {}


def validate_sync_history(client: httpx.Client) -> list:
    """Check recent sync job history."""
    print("\n📋 Recent Sync History (last 20):")
    try:
        resp = client.get("/api/v1/sync/history?limit=20")
        if resp.status_code == 200:
            logs = resp.json().get("logs", [])
            for log in logs:
                status_icon = {"success": "✅", "partial": "⚠️", "failed": "❌"}.get(
                    log.get("status", ""), "❓"
                )
                tenant_code = TENANT_NAMES.get(log.get("tenant_id", ""), log.get("tenant_id", "—")[:8])
                duration = log.get("duration_ms", 0)
                records = log.get("records_processed", 0)
                errors = log.get("errors_count", 0)
                print(
                    f"  {status_icon} {log['job_type']:<20} "
                    f"tenant={tenant_code:<5} "
                    f"records={records:<6} "
                    f"errors={errors:<3} "
                    f"duration={duration}ms "
                    f"at {log.get('started_at', '?')}"
                )
            return logs
        else:
            print(f"  ❌ {resp.status_code}")
            return []
    except Exception as e:
        print(f"  ❌ {e}")
        return []


def validate_riverside_data(client: httpx.Client) -> dict:
    """Validate Riverside MFA data exists for all tenants."""
    print("\n🏢 Riverside MFA Data:")
    try:
        resp = client.get("/api/v1/riverside/summary")
        if resp.status_code == 200:
            data = resp.json()
            tenants = data.get("tenants", data.get("tenant_summaries", []))
            if isinstance(tenants, dict):
                for code, info in tenants.items():
                    mfa = info.get("mfa_coverage", info.get("mfa_coverage_pct", "?"))
                    users = info.get("total_users", info.get("user_count", "?"))
                    print(f"  {'✅' if mfa != '?' else '❓'} {code}: {mfa}% MFA coverage, {users} users")
            elif isinstance(tenants, list):
                for t in tenants:
                    code = t.get("code", t.get("tenant_code", "?"))
                    mfa = t.get("mfa_coverage", t.get("mfa_coverage_pct", "?"))
                    users = t.get("total_users", t.get("user_count", "?"))
                    print(f"  {'✅' if users else '❓'} {code}: {mfa}% MFA, {users} users")
            else:
                print(f"  Raw response: {json.dumps(data, indent=2)[:500]}")
            return data
        else:
            print(f"  ❌ {resp.status_code}: {resp.text[:200]}")
            return {}
    except Exception as e:
        print(f"  ❌ {e}")
        return {}


def validate_costs(client: httpx.Client) -> dict:
    """Validate cost data exists."""
    print("\n💰 Cost Data:")
    try:
        resp = client.get("/api/v1/costs/summary")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  {json.dumps(data, indent=2)[:500]}")
            return data
        else:
            print(f"  ❌ {resp.status_code}: {resp.text[:100]}")
            return {}
    except Exception as e:
        print(f"  ❌ {e}")
        return {}


def validate_resources(client: httpx.Client) -> dict:
    """Validate resource inventory."""
    print("\n🖥️  Resources:")
    try:
        resp = client.get("/api/v1/resources")
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("total_resources", data.get("total", "?"))
            print(f"  Total resources: {total}")
            if "by_type" in data:
                for rtype, count in list(data["by_type"].items())[:10]:
                    print(f"    {rtype}: {count}")
            elif "resource_types" in data:
                for item in data["resource_types"][:10]:
                    print(f"    {item.get('type', '?')}: {item.get('count', '?')}")
            else:
                print(f"  {json.dumps(data, indent=2)[:400]}")
            return data
        else:
            print(f"  ❌ {resp.status_code}: {resp.text[:100]}")
            return {}
    except Exception as e:
        print(f"  ❌ {e}")
        return {}


def validate_compliance(client: httpx.Client) -> dict:
    """Validate compliance data."""
    print("\n📋 Compliance:")
    try:
        resp = client.get("/api/v1/compliance/summary")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  {json.dumps(data, indent=2)[:500]}")
            return data
        else:
            print(f"  ❌ {resp.status_code}: {resp.text[:100]}")
            return {}
    except Exception as e:
        print(f"  ❌ {e}")
        return {}


def validate_alerts(client: httpx.Client) -> list:
    """Check active alerts."""
    print("\n🚨 Active Alerts:")
    try:
        resp = client.get("/api/v1/sync/alerts")
        if resp.status_code == 200:
            data = resp.json()
            alerts = data.get("alerts", [])
            if not alerts:
                print("  ✅ No active alerts!")
            for alert in alerts:
                sev = alert.get("severity", "?")
                icon = {"critical": "🔴", "error": "🟠", "warning": "🟡", "info": "🔵"}.get(sev, "❓")
                print(f"  {icon} [{sev}] {alert.get('title', '?')} — {alert.get('message', '')[:80]}")
            return alerts
        else:
            print(f"  ❌ {resp.status_code}")
            return []
    except Exception as e:
        print(f"  ❌ {e}")
        return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Manual sync trigger + validation")
    parser.add_argument("--sync-only", action="store_true", help="Only trigger syncs")
    parser.add_argument("--validate-only", action="store_true", help="Only validate data")
    parser.add_argument("--wait", type=int, default=60, help="Seconds to wait after triggering syncs (default: 60)")
    args = parser.parse_args()

    print("=" * 60)
    print("🐶 Manual Sync & Validation — Azure Governance Platform")
    print(f"   Target: {PROD_URL}")
    print(f"   Time:   {datetime.now(UTC).isoformat()}")
    print("=" * 60)

    client = make_client()

    # Quick health check first
    print("\n🏥 Health Check:")
    try:
        resp = client.get("/health/detailed")
        health = resp.json()
        print(f"  Status: {health.get('status', '?')}")
        for comp, val in health.get("components", {}).items():
            print(f"    {comp}: {val}")
    except Exception as e:
        print(f"  ❌ Cannot reach production: {e}")
        sys.exit(1)

    if not args.validate_only:
        print("\n" + "=" * 60)
        print("🔄 TRIGGERING SYNCS")
        print("=" * 60)

        print("\n📡 Infrastructure syncs:")
        infra_results = trigger_infrastructure_syncs(client)

        print("\n🏢 Riverside sync:")
        riverside_results = trigger_riverside_sync(client)

        if not args.sync_only:
            print(f"\n⏳ Waiting {args.wait}s for syncs to complete...")
            for i in range(args.wait, 0, -10):
                print(f"  {i}s remaining...", flush=True)
                time.sleep(min(10, i))

    if not args.sync_only:
        print("\n" + "=" * 60)
        print("✅ DATA VALIDATION")
        print("=" * 60)

        validate_sync_health(client)
        validate_sync_history(client)
        validate_riverside_data(client)
        validate_costs(client)
        validate_resources(client)
        validate_compliance(client)
        validate_alerts(client)

    print("\n" + "=" * 60)
    print("🏁 Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
