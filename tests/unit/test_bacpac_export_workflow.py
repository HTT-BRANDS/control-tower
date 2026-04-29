"""Contract checks for weekly BACPAC export automation."""

from pathlib import Path

BACPAC_WORKFLOW = Path(".github/workflows/bacpac-export.yml")
DR_RUNBOOK = Path("docs/runbooks/disaster-recovery.md")
RETENTION_POLICY = Path("docs/DATA_RETENTION_POLICY.md")


def workflow_text() -> str:
    return BACPAC_WORKFLOW.read_text()


def test_bacpac_workflow_uses_oidc_azure_login():
    """Azure CLI export runs via GitHub OIDC, not static Azure creds."""
    workflow = workflow_text()

    assert "uses: azure/login@v2" in workflow
    assert "permissions:" in workflow
    assert "contents: read" in workflow
    assert "id-token: write" in workflow


def test_bacpac_workflow_runs_weekly_and_supports_manual_staging_validation():
    """Acceptance needs weekly prod schedule plus one staging dispatch path."""
    workflow = workflow_text()

    assert "cron: '30 3 * * 0'" in workflow
    assert "workflow_dispatch:" in workflow
    assert "- staging" in workflow
    assert "- production" in workflow
    assert "environment: ${{ github.event.inputs.environment || 'production' }}" in workflow


def test_bacpac_workflow_exports_sql_to_cool_blob_storage():
    """Pin the actual long-term recovery primitive: az sql db export -> Cool blob."""
    workflow = workflow_text()

    assert "az storage account list" in workflow
    assert "az sql db export" in workflow
    assert "--storage-key-type StorageAccessKey" in workflow
    assert '--storage-uri "${{ steps.config.outputs.storage_uri }}"' in workflow
    assert "az storage blob set-tier" in workflow
    assert "--tier Cool" in workflow
    assert "az storage blob delete-batch" in workflow
    assert "365 days ago" in workflow
    assert "RETENTION_MONTHS: '12'" in workflow


def test_bacpac_workflow_uses_documented_prod_defaults_and_teams_notifications():
    """Prod defaults must match the runbook and failures must page humans."""
    workflow = workflow_text()

    assert "rg-governance-production" in workflow
    assert "sql-gov-prod-mylxq53d" in workflow
    assert "PRODUCTION_TEAMS_WEBHOOK" in workflow
    assert "Weekly BACPAC Export Complete" in workflow
    assert "Weekly BACPAC Export Failed" in workflow


def test_disaster_recovery_runbook_documents_bacpac_restore():
    """Automation without restore docs is theater. Fancy theater, but theater."""
    runbook = DR_RUNBOOK.read_text()

    assert "### B.5 Long-term restore from BACPAC" in runbook
    assert "az sql db import" in runbook
    assert "bacpac-exports" in runbook
    assert "SQL_ADMIN_PASSWORD" in runbook


def test_retention_policy_no_longer_says_weekly_bacpac_is_unautomated():
    policy = RETENTION_POLICY.read_text()

    assert "`.github/workflows/bacpac-export.yml`" in policy
    assert "The weekly BACPAC export is currently manual" not in policy
