"""Contract checks for subscription-scoped Bicep drift detection."""

from pathlib import Path

BICEP_DRIFT_WORKFLOW = Path(".github/workflows/bicep-drift-detection.yml")
MAIN_BICEP = Path("infrastructure/main.bicep")


def test_drift_workflow_matches_main_bicep_subscription_scope():
    """main.bicep is subscription-scoped, so what-if must be too.

    Azure CLI refuses to run a resource-group-scoped what-if against a template
    that declares ``targetScope = 'subscription'``. Pin the workflow command so
    scheduled drift detection stays useful instead of failing before it checks
    drift. Charming failure mode, Azure. Very generous.
    """
    workflow = BICEP_DRIFT_WORKFLOW.read_text()
    main_bicep = MAIN_BICEP.read_text()

    assert "targetScope = 'subscription'" in main_bicep
    assert "az deployment sub what-if" in workflow
    assert "az deployment group what-if" not in workflow


def test_subscription_what_if_uses_parameterized_deployment_location():
    """Subscription deployments need a deployment metadata location."""
    workflow = BICEP_DRIFT_WORKFLOW.read_text()

    assert "DEPLOY_LOCATION=$(jq -r '.parameters.location.value" in workflow
    assert '--location "$DEPLOY_LOCATION"' in workflow


def test_drift_remediation_text_uses_subscription_scope():
    """Operator instructions must match the command shape that actually works."""
    workflow = BICEP_DRIFT_WORKFLOW.read_text()

    assert "az deployment sub create" in workflow
    assert "az deployment group create" not in workflow


def test_bicep_drift_reader_role_documents_what_if_permission():
    """Custom drift role includes subscription what-if without write actions."""
    role = Path("infrastructure/azure/rbac/bicep-drift-reader.role.json").read_text()

    assert "Bicep Drift Reader" in role
    assert "Microsoft.Resources/deployments/whatIf/action" in role
    assert "*/read" in role
    assert "*/write" not in role
    assert "<subscription-id>" in role
