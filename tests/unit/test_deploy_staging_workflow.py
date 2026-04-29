"""Contract checks for the staging deployment workflow."""

from pathlib import Path

DEPLOY_STAGING_WORKFLOW = Path(".github/workflows/deploy-staging.yml")


def workflow_text() -> str:
    return DEPLOY_STAGING_WORKFLOW.read_text()


def test_staging_deploy_reasserts_runtime_health_settings_after_container_update():
    """Container config updates must not leave staging cold-start hostile.

    The live staging app drifted to alwaysOn=false and no healthCheckPath even
    though Bicep declares the opposite. Since this workflow mutates App Service
    container settings on every push, pin the runtime knobs here too. Yes, Azure
    made us wear a belt and suspenders. Very fashionable.
    """
    workflow = workflow_text()

    assert "az webapp config set" in workflow
    assert "--always-on true" in workflow
    assert "--generic-configurations" in workflow
    assert "healthCheckPath" in workflow
    assert "WEBSITE_HEALTHCHECK_MAXPINGFAILURES=3" in workflow


def test_staging_health_gate_uses_bounded_readiness_loop_with_diagnostics():
    """A single curl after sleep is not a readiness strategy. It is a wish."""
    workflow = workflow_text()

    assert "Health gate readiness loop" in workflow
    assert "max_attempts=12" in workflow
    assert "set +e\n            http_code=$(curl" in workflow
    assert "curl_exit=$?\n            set -e" in workflow
    assert "curl --silent --show-error --location" in workflow
    assert "--connect-timeout 10" in workflow
    assert "--max-time 30" in workflow
    assert "az webapp show" in workflow
    assert "az webapp log tail" in workflow
    assert "Wait for startup (90s)" not in workflow
    assert "curl -sf ${{ env.STAGING_URL }}/health" not in workflow
