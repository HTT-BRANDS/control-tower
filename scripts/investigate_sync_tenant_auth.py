#!/usr/bin/env python3
"""Classify tenant sync auth expectations from exported production evidence.

Read-only helper for issue 918b. Feed it exported tenant rows, optional app
settings, and optional Key Vault secret metadata, and it will tell you which
noisy tenants are expected to use Lighthouse, explicit per-tenant refs,
OIDC/UAMI app IDs, legacy standard Key Vault pairs, or nothing useful at all.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.sync.utils import build_sync_eligibility_decision
from app.core.tenants_config import get_tenant_by_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenants-json", type=Path, required=True)
    parser.add_argument("--app-settings-json", type=Path, default=None)
    parser.add_argument("--keyvault-secrets-json", type=Path, default=None)
    parser.add_argument("--tenant-id", action="append", default=[])
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--output-md", type=Path, default=None)
    return parser.parse_args()


def _load_json(path: Path | None) -> Any:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _coerce_scalar(value: Any) -> Any:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "false"}:
            return lowered == "true"
        if value.strip().isdigit():
            return int(value.strip())
    return value


def _rows_from_table_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    tables = payload.get("tables")
    if not isinstance(tables, list) or not tables:
        return []
    table = tables[0]
    names = [c.get("name") if isinstance(c, dict) else str(c) for c in table.get("columns", [])]
    result: list[dict[str, Any]] = []
    for row in table.get("rows", []):
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
        rows = _rows_from_table_payload(payload)
        if rows:
            return rows
    return []


def _normalize_app_settings(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, dict):
        if "properties" in payload and isinstance(payload["properties"], dict):
            return {str(k): _coerce_scalar(v) for k, v in payload["properties"].items()}
        return {str(k): _coerce_scalar(v) for k, v in payload.items()}
    if isinstance(payload, list):
        settings: dict[str, Any] = {}
        for item in payload:
            if isinstance(item, dict) and "name" in item:
                settings[str(item["name"])] = _coerce_scalar(item.get("value"))
        return settings
    return {}


def _normalize_secret_names(payload: Any) -> set[str]:
    names: set[str] = set()
    if payload is None:
        return names
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, str):
                names.add(item)
            elif isinstance(item, dict) and item.get("name"):
                names.add(str(item["name"]))
    elif isinstance(payload, dict):
        for row in _normalize_rows(payload):
            name = row.get("name")
            if name:
                names.add(str(name))
    return names


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _runtime_mode(settings: dict[str, Any]) -> str:
    if _as_bool(settings.get("USE_UAMI_AUTH")):
        return "uami"
    if _as_bool(settings.get("USE_OIDC_FEDERATION")):
        return "oidc"
    if settings.get("KEY_VAULT_URL"):
        return "secret_keyvault"
    return "shared_secret"


def _recommended_action(
    *,
    runtime_mode: str,
    scheduler_eligible: bool,
    scheduler_reason: str,
    expected_auth_path: str,
    standard_secret_pair_present: bool,
    explicit_secret_present: bool,
    use_lighthouse: bool,
) -> str:
    if not scheduler_eligible:
        if scheduler_reason == "missing_db_declared_secret_path":
            return "disable tenant for scheduled sync or add an explicit auth path"
        if scheduler_reason in {
            "missing_shared_settings_credentials",
            "lighthouse_missing_shared_settings_credentials",
        }:
            return "fix shared secret settings before treating tenant as schedulable"
        if scheduler_reason in {"missing_app_id_for_uami", "missing_app_id_for_oidc"}:
            return "add tenant app ID mapping or disable scheduled sync for this tenant"
        return "confirm tenant should be excluded from scheduled sync"

    if runtime_mode == "secret_keyvault":
        if expected_auth_path == "explicit_per_tenant_secret_ref" and not explicit_secret_present:
            return "create or repair the explicit client_secret_ref secret in Key Vault"
        if (
            expected_auth_path == "standard_key_vault_secret_pair"
            and not standard_secret_pair_present
        ):
            return "create the standard {tenant-id}-client-id/client-secret pair or move tenant to explicit refs"
        if expected_auth_path == "lighthouse_shared_credentials":
            return "confirm Lighthouse is intended and shared settings creds are still valid"

    return "configuration appears internally consistent; inspect runtime logs/evidence for remaining mismatch"


def _config_status(
    *,
    scheduler_eligible: bool,
    expected_auth_path: str,
    standard_secret_pair_present: bool,
    explicit_secret_present: bool,
) -> str:
    if not scheduler_eligible:
        return "ineligible"
    if expected_auth_path == "explicit_per_tenant_secret_ref":
        return "ready" if explicit_secret_present else "missing_secret_metadata"
    if expected_auth_path == "standard_key_vault_secret_pair":
        return "ready" if standard_secret_pair_present else "missing_secret_metadata"
    return "ready"


def _classify_tenant(
    row: dict[str, Any], app_settings: dict[str, Any], secret_names: set[str]
) -> dict[str, Any]:
    tenant_id = str(row.get("tenant_id") or "")
    yaml_cfg = get_tenant_by_id(tenant_id)
    resolved_app_id = (
        yaml_cfg.multi_tenant_app_id if yaml_cfg and yaml_cfg.multi_tenant_app_id else None
    ) or (yaml_cfg.app_id if yaml_cfg else None)
    decision = build_sync_eligibility_decision(
        tenant_is_active=_as_bool(row.get("is_active", True)),
        tenant_id=tenant_id,
        tenant_client_id=row.get("client_id"),
        tenant_client_secret_ref=row.get("client_secret_ref"),
        tenant_use_lighthouse=_as_bool(row.get("use_lighthouse", False)),
        use_uami_auth=_as_bool(app_settings.get("USE_UAMI_AUTH")),
        use_oidc_federation=_as_bool(app_settings.get("USE_OIDC_FEDERATION")),
        key_vault_url=app_settings.get("KEY_VAULT_URL"),
        azure_client_id=app_settings.get("AZURE_CLIENT_ID"),
        azure_client_secret=app_settings.get("AZURE_CLIENT_SECRET"),
        resolved_app_id=resolved_app_id,
    )

    standard_secret_names = (
        {f"{tenant_id}-client-id", f"{tenant_id}-client-secret"} if tenant_id else set()
    )
    standard_secret_pair_present = standard_secret_names.issubset(secret_names)
    explicit_secret_ref = row.get("client_secret_ref")
    explicit_secret_present = bool(explicit_secret_ref and explicit_secret_ref in secret_names)

    if decision.auth_mode in {"uami", "oidc"}:
        expected_path = decision.auth_mode
    elif _as_bool(row.get("use_lighthouse", False)):
        expected_path = "lighthouse_shared_credentials"
    elif row.get("client_id") and row.get("client_secret_ref"):
        expected_path = "explicit_per_tenant_secret_ref"
    elif standard_secret_pair_present:
        expected_path = "standard_key_vault_secret_pair"
    else:
        expected_path = "no_declared_secret_path"

    config_status = _config_status(
        scheduler_eligible=decision.eligible,
        expected_auth_path=expected_path,
        standard_secret_pair_present=standard_secret_pair_present,
        explicit_secret_present=explicit_secret_present,
    )
    recommended_action = _recommended_action(
        runtime_mode=_runtime_mode(app_settings),
        scheduler_eligible=decision.eligible,
        scheduler_reason=decision.reason,
        expected_auth_path=expected_path,
        standard_secret_pair_present=standard_secret_pair_present,
        explicit_secret_present=explicit_secret_present,
        use_lighthouse=_as_bool(row.get("use_lighthouse", False)),
    )

    return {
        "name": row.get("name"),
        "tenant_id": tenant_id,
        "is_active": _as_bool(row.get("is_active", True)),
        "use_lighthouse": _as_bool(row.get("use_lighthouse", False)),
        "use_oidc": _as_bool(row.get("use_oidc", False)),
        "client_id": row.get("client_id"),
        "client_secret_ref": explicit_secret_ref,
        "yaml_known": bool(yaml_cfg),
        "yaml_code": yaml_cfg.code if yaml_cfg else None,
        "yaml_app_id": resolved_app_id,
        "runtime_mode": _runtime_mode(app_settings),
        "scheduler_eligible": decision.eligible,
        "scheduler_reason": decision.reason,
        "expected_auth_path": expected_path,
        "config_status": config_status,
        "standard_secret_pair_present": standard_secret_pair_present,
        "explicit_secret_metadata_present": explicit_secret_present,
        "recommended_action": recommended_action,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    tenant_rows = _normalize_rows(_load_json(args.tenants_json))
    app_settings = _normalize_app_settings(_load_json(args.app_settings_json))
    secret_names = _normalize_secret_names(_load_json(args.keyvault_secrets_json))
    requested_ids = set(args.tenant_id or [])
    if requested_ids:
        tenant_rows = [
            row for row in tenant_rows if str(row.get("tenant_id") or "") in requested_ids
        ]

    classifications = [_classify_tenant(row, app_settings, secret_names) for row in tenant_rows]
    counts: dict[str, int] = {}
    for row in classifications:
        key = row["expected_auth_path"]
        counts[key] = counts.get(key, 0) + 1

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "runtime_mode": _runtime_mode(app_settings),
        "tenant_count": len(classifications),
        "path_counts": counts,
        "tenants": classifications,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Sync tenant auth investigation",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Runtime mode: **{report['runtime_mode']}**",
        f"Tenant count: **{report['tenant_count']}**",
        "",
        "## Expected auth path counts",
        "",
    ]
    if report["path_counts"]:
        for path, count in sorted(report["path_counts"].items()):
            lines.append(f"- `{path}`: {count}")
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Tenant classification",
            "",
            "| Tenant | Scheduler eligible | Reason | Expected auth path | Config status | YAML known | Standard KV pair | Explicit secret metadata | Recommended action |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for tenant in report["tenants"]:
        lines.append(
            "| {name} | {eligible} | `{reason}` | `{path}` | `{config_status}` | {yaml_known} | {std_pair} | {explicit_present} | {action} |".format(
                name=tenant.get("name") or tenant.get("tenant_id") or "unknown",
                eligible="yes" if tenant["scheduler_eligible"] else "no",
                reason=tenant["scheduler_reason"],
                path=tenant["expected_auth_path"],
                config_status=tenant["config_status"],
                yaml_known="yes" if tenant["yaml_known"] else "no",
                std_pair="yes" if tenant["standard_secret_pair_present"] else "no",
                explicit_present=("yes" if tenant["explicit_secret_metadata_present"] else "no"),
                action=tenant["recommended_action"],
            )
        )
    if not report["tenants"]:
        lines.append("| _none_ | no | `n/a` | `n/a` | `n/a` | no | no | no | n/a |")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    report = build_report(args)
    rendered_json = json.dumps(report, indent=2, sort_keys=True)
    if args.output_json:
        args.output_json.write_text(rendered_json + "\n", encoding="utf-8")
    if args.output_md:
        args.output_md.write_text(render_markdown(report), encoding="utf-8")
    if not args.output_json and not args.output_md:
        print(rendered_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
