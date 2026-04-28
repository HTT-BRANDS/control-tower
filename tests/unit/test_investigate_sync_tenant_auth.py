"""Tests for scripts/investigate_sync_tenant_auth.py."""

import json
from argparse import Namespace

from scripts.investigate_sync_tenant_auth import build_report, render_markdown


def _args(**overrides):
    defaults = {
        "tenants_json": None,
        "app_settings_json": None,
        "keyvault_secrets_json": None,
        "tenant_id": [],
        "output_json": None,
        "output_md": None,
    }
    defaults.update(overrides)
    return Namespace(**defaults)


def test_classifies_keyvault_tenants_with_explicit_ref_and_standard_pair(tmp_path):
    tenants = tmp_path / "tenants.json"
    tenants.write_text(
        json.dumps(
            [
                {
                    "name": "Explicit",
                    "tenant_id": "0c0e35dc-188a-4eb3-b8ba-61752154b407",
                    "is_active": True,
                    "use_lighthouse": False,
                    "client_id": "explicit-app-id",
                    "client_secret_ref": "htt-client-ref",  # pragma: allowlist secret
                },
                {
                    "name": "StandardPair",
                    "tenant_id": "b5380912-79ec-452d-a6ca-6d897b19b294",
                    "is_active": True,
                    "use_lighthouse": False,
                    "client_id": None,
                    "client_secret_ref": None,  # pragma: allowlist secret
                },
            ]
        )
    )
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps(
            [
                {"name": "KEY_VAULT_URL", "value": "https://kv-gov-prod.vault.azure.net/"},
                {"name": "AZURE_CLIENT_ID", "value": "shared-client"},
                {"name": "AZURE_CLIENT_SECRET", "value": "shared-credential"},
            ]
        )
    )
    secrets = tmp_path / "secrets.json"
    secrets.write_text(
        json.dumps(
            [
                {"name": "htt-client-ref"},
                {"name": "b5380912-79ec-452d-a6ca-6d897b19b294-client-id"},
                {"name": "b5380912-79ec-452d-a6ca-6d897b19b294-client-secret"},
            ]
        )
    )

    report = build_report(
        _args(tenants_json=tenants, app_settings_json=settings, keyvault_secrets_json=secrets)
    )

    explicit = report["tenants"][0]
    standard = report["tenants"][1]
    assert explicit["expected_auth_path"] == "explicit_per_tenant_secret_ref"
    assert explicit["explicit_secret_metadata_present"] is True
    assert explicit["scheduler_eligible"] is True
    assert standard["expected_auth_path"] == "standard_key_vault_secret_pair"
    assert standard["scheduler_eligible"] is False
    assert standard["scheduler_reason"] == "missing_db_declared_secret_path"


def test_classifies_oidc_runtime_from_app_settings(tmp_path):
    tenants = tmp_path / "tenants.json"
    tenants.write_text(
        """
        [
          {
            "name": "HTT",
            "tenant_id": "0c0e35dc-188a-4eb3-b8ba-61752154b407",
            "is_active": true,
            "use_lighthouse": false,
            "client_id": null,
            "client_secret_ref": null
          }
        ]
        """.strip()
    )
    settings = tmp_path / "settings.json"
    settings.write_text('{"USE_OIDC_FEDERATION": true}')

    report = build_report(_args(tenants_json=tenants, app_settings_json=settings))

    assert report["runtime_mode"] == "oidc"
    assert report["tenants"][0]["scheduler_eligible"] is True
    assert report["tenants"][0]["scheduler_reason"] == "oidc_app_id_resolved"


def test_render_markdown_includes_table_and_counts():
    report = {
        "generated_at": "2026-04-24T12:00:00+00:00",
        "runtime_mode": "secret_keyvault",
        "tenant_count": 1,
        "path_counts": {"no_declared_secret_path": 1},
        "tenants": [
            {
                "name": "Noisy Tenant",
                "scheduler_eligible": False,
                "scheduler_reason": "missing_db_declared_secret_path",
                "expected_auth_path": "no_declared_secret_path",
                "config_status": "ineligible",
                "yaml_known": True,
                "standard_secret_pair_present": False,
                "explicit_secret_metadata_present": False,
                "recommended_action": (
                    "disable tenant for scheduled sync or add an explicit auth path"
                ),
            }
        ],
    }

    markdown = render_markdown(report)

    assert "Runtime mode: **secret_keyvault**" in markdown
    assert "`no_declared_secret_path`: 1" in markdown
    assert "Noisy Tenant" in markdown
    assert "`missing_db_declared_secret_path`" in markdown
    # Pin that the rendered table actually surfaces the new columns the
    # render path now depends on; otherwise drift here goes undetected.
    assert "`ineligible`" in markdown
    assert "disable tenant for scheduled sync" in markdown
