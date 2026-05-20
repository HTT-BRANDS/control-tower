#!/usr/bin/env python3
"""Grant Microsoft Graph application roles to the Control Tower service principal.

Uses the *currently logged-in Azure CLI user* for the target tenant. This is for
admin-consent repair where the app registration already declares required Graph
permissions, but the customer tenant service principal is missing assignments.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

import httpx

GRAPH = "https://graph.microsoft.com/v1.0"
GRAPH_APP_ID = "00000003-0000-0000-c000-000000000000"
CONTROL_TOWER_APP_ID = os.environ.get("CONTROL_TOWER_APP_ID", "")

DEFAULT_ROLES = [
    "Application.Read.All",
    "AuditLog.Read.All",
    "DeviceManagementManagedDevices.Read.All",
    "Directory.Read.All",
    "Domain.Read.All",
    "Group.Read.All",
    "GroupMember.Read.All",
    "IdentityRiskEvent.Read.All",
    "IdentityRiskyUser.Read.All",
    "Organization.Read.All",
    "Policy.Read.All",
    "Reports.Read.All",
    "RoleManagement.Read.Directory",
    "SecurityEvents.Read.All",
    "User.Read.All",
    "UserAuthenticationMethod.Read.All",
]


@dataclass(frozen=True)
class ServicePrincipal:
    id: str
    app_id: str
    display_name: str


def _az_graph_token(tenant_id: str) -> str:
    return subprocess.check_output(
        [
            "az",
            "account",
            "get-access-token",
            "--tenant",
            tenant_id,
            "--resource",
            "https://graph.microsoft.com",
            "--query",
            "accessToken",
            "-o",
            "tsv",
        ],
        text=True,
    ).strip()


def _request(
    client: httpx.Client,
    method: str,
    path: str,
    token: str,
    *,
    json_body: dict[str, Any] | None = None,
) -> httpx.Response:
    response = client.request(
        method,
        f"{GRAPH}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=json_body,
        timeout=30,
    )
    response.raise_for_status()
    return response


def _get_sp(client: httpx.Client, token: str, app_id: str) -> ServicePrincipal:
    query = f"/servicePrincipals?$filter=appId eq '{app_id}'&$select=id,appId,displayName"
    data = _request(client, "GET", query, token).json().get("value", [])
    if not data:
        raise RuntimeError(f"Service principal for appId {app_id} was not found in tenant")
    item = data[0]
    return ServicePrincipal(item["id"], item["appId"], item.get("displayName", app_id))


def _graph_role_map(client: httpx.Client, token: str, graph_sp_id: str) -> dict[str, str]:
    data = _request(
        client, "GET", f"/servicePrincipals/{graph_sp_id}?$select=appRoles", token
    ).json()
    return {
        role["value"]: role["id"]
        for role in data.get("appRoles", [])
        if role.get("value") and "Application" in role.get("allowedMemberTypes", [])
    }


def _existing_assignments(
    client: httpx.Client,
    token: str,
    principal_sp_id: str,
    graph_sp_id: str,
) -> set[str]:
    data = _request(
        client,
        "GET",
        f"/servicePrincipals/{principal_sp_id}/appRoleAssignments?$select=appRoleId,resourceId",
        token,
    ).json()
    return {
        assignment["appRoleId"]
        for assignment in data.get("value", [])
        if assignment.get("resourceId") == graph_sp_id
    }


def grant_roles(
    tenant_id: str,
    roles: list[str],
    *,
    app_id: str,
    dry_run: bool,
) -> dict[str, Any]:
    token = _az_graph_token(tenant_id)
    with httpx.Client() as client:
        graph_sp = _get_sp(client, token, GRAPH_APP_ID)
        app_sp = _get_sp(client, token, app_id)
        role_map = _graph_role_map(client, token, graph_sp.id)
        existing = _existing_assignments(client, token, app_sp.id, graph_sp.id)

        planned: list[str] = []
        granted: list[str] = []
        already: list[str] = []
        missing_from_graph: list[str] = []

        for role in roles:
            role_id = role_map.get(role)
            if not role_id:
                missing_from_graph.append(role)
                continue
            if role_id in existing:
                already.append(role)
                continue
            planned.append(role)
            if dry_run:
                continue
            body = {"principalId": app_sp.id, "resourceId": graph_sp.id, "appRoleId": role_id}
            _request(
                client,
                "POST",
                f"/servicePrincipals/{app_sp.id}/appRoleAssignments",
                token,
                json_body=body,
            )
            granted.append(role)

        return {
            "tenant_id": tenant_id,
            "app_sp_id": app_sp.id,
            "graph_sp_id": graph_sp.id,
            "dry_run": dry_run,
            "already": sorted(already),
            "planned": sorted(planned),
            "granted": sorted(granted),
            "missing_from_graph": sorted(missing_from_graph),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", action="append", required=True, help="Target tenant ID")
    parser.add_argument("--role", action="append", dest="roles", help="Graph app role value")
    parser.add_argument(
        "--app-id", default=CONTROL_TOWER_APP_ID, help="Control Tower app registration client ID"
    )
    parser.add_argument("--execute", action="store_true", help="Actually grant missing roles")
    args = parser.parse_args()

    if not args.app_id:
        print("Missing --app-id or CONTROL_TOWER_APP_ID", file=sys.stderr)
        return 2

    roles = args.roles or DEFAULT_ROLES
    reports = []
    for tenant in args.tenant:
        try:
            reports.append(grant_roles(tenant, roles, app_id=args.app_id, dry_run=not args.execute))
        except Exception as exc:
            reports.append({"tenant_id": tenant, "error": str(exc)[:1000]})
    print(json.dumps(reports, indent=2, sort_keys=True))
    return 1 if any("error" in r for r in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
