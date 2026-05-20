#!/usr/bin/env python3
"""Diagnose cross-tenant Graph/ARM permissions for Control Tower prod sync.

This script intentionally reads credentials from environment variables and never
prints secrets. It is safe to run locally after exporting the same app settings
used by production.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from azure.identity import ClientSecretCredential

GRAPH = "https://graph.microsoft.com/v1.0"
ARM = "https://management.azure.com"


def _tenant_name_map() -> dict[str, str]:
    """Return optional tenant-id → label map from env JSON.

    Example:
        CONTROL_TOWER_TENANT_NAMES='{"<tenant-guid>": "Head-To-Toe"}'
    """
    import os

    raw = os.environ.get("CONTROL_TOWER_TENANT_NAMES")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return {str(k): str(v) for k, v in data.items()}
    except Exception:
        return {}


GRAPH_PROBES = {
    "organization": (
        "/organization?$select=id,displayName",
        "Organization.Read.All/Directory.Read.All",
    ),
    "users_basic": (
        "/users?$top=1&$select=id,displayName,userPrincipalName",
        "User.Read.All/Directory.Read.All",
    ),
    "users_signin": ("/users?$top=1&$select=id,signInActivity", "AuditLog.Read.All + Entra P1/P2"),
    "groups": ("/groups?$top=1&$select=id,displayName", "Group.Read.All/Directory.Read.All"),
    "service_principals": (
        "/servicePrincipals?$top=1&$select=id,appId,displayName",
        "Application.Read.All/Directory.Read.All",
    ),
    "directory_roles": ("/directoryRoles", "RoleManagement.Read.Directory/Directory.Read.All"),
    "mfa_registration": (
        "/reports/authenticationMethods/userRegistrationDetails?$top=1",
        "Reports.Read.All",
    ),
    "conditional_access": ("/identity/conditionalAccess/policies?$top=1", "Policy.Read.All"),
    "domains": ("/domains?$top=1", "Domain.Read.All"),
    "managed_devices": (
        "/deviceManagement/managedDevices?$top=1",
        "DeviceManagementManagedDevices.Read.All + Intune license",
    ),
    "security_alerts": ("/security/alerts?$top=1", "SecurityEvents.Read.All"),
}


@dataclass
class ProbeResult:
    status: str
    http_status: int | None = None
    detail: str | None = None
    required: str | None = None


@dataclass
class TenantReport:
    tenant_id: str
    tenant_name: str
    token_graph: ProbeResult
    token_arm: ProbeResult
    graph_roles: list[str] = field(default_factory=list)
    graph: dict[str, ProbeResult] = field(default_factory=dict)
    subscriptions: ProbeResult = field(default_factory=lambda: ProbeResult("not_run"))
    subscription_count: int = 0
    arm: dict[str, dict[str, ProbeResult]] = field(default_factory=dict)


def _short_error(exc: Exception) -> str:
    text = str(exc).replace("\n", " ")
    return text[:500]


def _decode_jwt_roles(token: str) -> list[str]:
    """Return app roles from an access token without validating it.

    This is diagnostic-only; validation is unnecessary because the token was just
    obtained directly from Microsoft identity platform by this process.
    """
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
        return sorted(data.get("roles", []))
    except Exception:
        return []


def _token(tenant_id: str, client_id: str, client_secret: str, scope: str) -> str:
    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        connection_timeout=10,
    )
    return credential.get_token(scope).token


def _probe_http(
    client: httpx.Client,
    method: str,
    url: str,
    token: str,
    *,
    required: str | None = None,
    json_body: dict[str, Any] | None = None,
) -> ProbeResult:
    try:
        response = client.request(
            method,
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=json_body,
            timeout=20,
        )
        if 200 <= response.status_code < 300:
            return ProbeResult("pass", response.status_code, required=required)
        detail = response.text[:500]
        return ProbeResult("fail", response.status_code, detail=detail, required=required)
    except Exception as exc:
        return ProbeResult("error", detail=_short_error(exc), required=required)


def _list_subscriptions(
    client: httpx.Client, arm_token: str
) -> tuple[ProbeResult, list[dict[str, Any]]]:
    url = f"{ARM}/subscriptions?api-version=2022-12-01"
    try:
        response = client.get(url, headers={"Authorization": f"Bearer {arm_token}"}, timeout=20)
        if response.status_code == 200:
            data = response.json().get("value", [])
            return ProbeResult("pass", 200), data
        return ProbeResult("fail", response.status_code, response.text[:500]), []
    except Exception as exc:
        return ProbeResult("error", detail=_short_error(exc)), []


def _cost_query_body() -> dict[str, Any]:
    now = datetime.now(UTC)
    start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    return {
        "type": "ActualCost",
        "timeframe": "Custom",
        "timePeriod": {"from": f"{start}T00:00:00Z", "to": f"{end}T00:00:00Z"},
        "dataset": {
            "granularity": "Daily",
            "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
            "grouping": [{"type": "Dimension", "name": "ServiceName"}],
        },
    }


def diagnose_tenant(tenant_id: str, client_id: str, client_secret: str) -> TenantReport:
    report = TenantReport(
        tenant_id=tenant_id,
        tenant_name=_tenant_name_map().get(tenant_id, tenant_id),
        token_graph=ProbeResult("not_run"),
        token_arm=ProbeResult("not_run"),
    )

    try:
        graph_token = _token(
            tenant_id, client_id, client_secret, "https://graph.microsoft.com/.default"
        )
        report.token_graph = ProbeResult("pass")
        report.graph_roles = _decode_jwt_roles(graph_token)
    except Exception as exc:
        report.token_graph = ProbeResult("fail", detail=_short_error(exc))
        graph_token = None

    try:
        arm_token = _token(
            tenant_id, client_id, client_secret, "https://management.azure.com/.default"
        )
        report.token_arm = ProbeResult("pass")
    except Exception as exc:
        report.token_arm = ProbeResult("fail", detail=_short_error(exc))
        arm_token = None

    with httpx.Client() as client:
        if graph_token:
            for name, (path, required) in GRAPH_PROBES.items():
                report.graph[name] = _probe_http(
                    client,
                    "GET",
                    f"{GRAPH}{path}",
                    graph_token,
                    required=required,
                )

        if arm_token:
            sub_result, subs = _list_subscriptions(client, arm_token)
            report.subscriptions = sub_result
            report.subscription_count = len(subs)
            for sub in subs:
                sub_id = sub.get("subscriptionId") or sub.get("subscription_id")
                if not sub_id:
                    continue
                report.arm[sub_id] = {
                    "resources": _probe_http(
                        client,
                        "GET",
                        f"{ARM}/subscriptions/{sub_id}/resources?$top=1&api-version=2021-04-01",
                        arm_token,
                        required="Reader on subscription/resource group",
                    ),
                    "cost": _probe_http(
                        client,
                        "POST",
                        f"{ARM}/subscriptions/{sub_id}/providers/Microsoft.CostManagement/query?api-version=2023-03-01",
                        arm_token,
                        required="Cost Management Reader or Reader with billing visibility",
                        json_body=_cost_query_body(),
                    ),
                    "policy_states": _probe_http(
                        client,
                        "POST",
                        f"{ARM}/subscriptions/{sub_id}/providers/Microsoft.PolicyInsights/policyStates/latest/queryResults?api-version=2019-10-01",
                        arm_token,
                        required="Reader + Microsoft.PolicyInsights access",
                        json_body={"$top": 1},
                    ),
                }

    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", action="append", dest="tenants", help="Tenant ID to probe")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args()

    import os

    client_id = os.environ.get("AZURE_CLIENT_ID") or os.environ.get("AZURE_AD_CLIENT_ID")
    client_secret = os.environ.get("AZURE_CLIENT_SECRET") or os.environ.get(
        "AZURE_AD_CLIENT_SECRET"
    )
    tenant_ids = args.tenants or [
        t.strip() for t in os.environ.get("RIVERSIDE_TENANT_IDS", "").split(",") if t.strip()
    ]

    if not client_id or not client_secret:
        print("Missing AZURE_CLIENT_ID/AZURE_CLIENT_SECRET", file=sys.stderr)
        return 2
    if not tenant_ids:
        print("No tenants provided; set RIVERSIDE_TENANT_IDS or pass --tenant", file=sys.stderr)
        return 2

    reports = [diagnose_tenant(t, client_id, client_secret) for t in tenant_ids]
    payload = [asdict(r) for r in reports]

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for report in reports:
            print(f"\n## {report.tenant_name} ({report.tenant_id})")
            print(f"token_graph={report.token_graph.status} token_arm={report.token_arm.status}")
            print("graph_roles=" + ",".join(report.graph_roles))
            for name, result in report.graph.items():
                print(
                    f"graph.{name}: {result.status} {result.http_status or ''} required={result.required}"
                )
                if result.status != "pass" and result.detail:
                    print(f"  detail: {result.detail[:220]}")
            print(f"subscriptions: {report.subscriptions.status} count={report.subscription_count}")
            for sub_id, checks in report.arm.items():
                print(f"  sub {sub_id}:")
                for name, result in checks.items():
                    print(
                        f"    arm.{name}: {result.status} {result.http_status or ''} required={result.required}"
                    )
                    if result.status != "pass" and result.detail:
                        print(f"      detail: {result.detail[:220]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
