"""Regression tests for ct-wph: deploy-staging.yml must wire AZURE_AD_*
app settings on every deploy.

Pre-fix:
  - staging webapp had AZURE_AD_* declared but empty
  - browser login was broken with 'Azure AD sign-in unavailable'
  - Tyler patched manually via `az webapp config appsettings set`
  - the patch lived only in local zsh history — any future deploy
    could silently wipe it

Post-fix:
  - deploy-staging.yml has an explicit step that calls
    `az webapp config appsettings set` with values from GitHub
    Secrets, before the container-image swap
  - the step gracefully no-ops if secrets aren't set yet (so
    existing branch deploys stay green)
  - docs/runbooks/staging-secrets.md walks Tyler through one-time setup
"""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-staging.yml"
RUNBOOK = ROOT / "docs" / "runbooks" / "staging-secrets.md"


def _load_workflow():
    return yaml.safe_load(WORKFLOW.read_text())


def test_deploy_staging_has_azure_ad_wiring_step():
    """A dedicated 'Configure Azure AD' step must exist in deploy-staging.yml."""
    wf = _load_workflow()
    # Find the deploy job (name varies, so look at all jobs).
    all_step_names = []
    for job in wf["jobs"].values():
        for step in job.get("steps", []):
            all_step_names.append(step.get("name", ""))
    azure_ad_steps = [n for n in all_step_names if "Azure AD" in n]
    assert azure_ad_steps, (
        "ct-wph: deploy-staging.yml must have a step that wires Azure AD "
        f"app settings; got steps: {all_step_names!r}"
    )


def test_azure_ad_step_runs_BEFORE_container_set():
    """The settings step must run before the container-image swap, so the
    new container starts up with the right env vars on the first request."""
    wf = _load_workflow()
    for job_name, job in wf["jobs"].items():
        step_names = [s.get("name", "") for s in job.get("steps", [])]
        azure_ad_idx = next(
            (i for i, n in enumerate(step_names) if "Azure AD" in n),
            None,
        )
        container_idx = next(
            (i for i, n in enumerate(step_names) if "container image" in n.lower()),
            None,
        )
        if azure_ad_idx is not None and container_idx is not None:
            assert azure_ad_idx < container_idx, (
                f"ct-wph: in job {job_name!r}, Azure AD wiring step "
                f"(index {azure_ad_idx}) must come BEFORE container image "
                f"update step (index {container_idx})"
            )


def test_azure_ad_step_uses_github_secrets_not_inline_values():
    """The four ground-truth values must come from GitHub Secrets, NOT inline
    literals — otherwise we'd be checking secrets into git."""
    src = WORKFLOW.read_text()
    azure_block = src.split("Configure Azure AD", 1)[1].split("Update container image", 1)[0]
    for required_secret in (
        "STAGING_AZURE_AD_TENANT_ID",
        "STAGING_AZURE_AD_CLIENT_ID",
        "STAGING_AZURE_AD_CLIENT_SECRET",
    ):
        assert required_secret in azure_block, (
            f"ct-wph: the Azure AD step must reference the {required_secret} "
            f"GitHub Secret"
        )
        # And it must be referenced via the secrets context, not env injection.
        assert f"secrets.{required_secret}" in azure_block, (
            f"ct-wph: {required_secret} must be sourced from ${{{{ secrets.* }}}}, "
            "not from env or hardcoded value"
        )


def test_azure_ad_step_skips_gracefully_when_secrets_missing():
    """If the secrets aren't set yet, the step must NOT fail the deploy.
    Otherwise every PR build would red-lock until Tyler walks through the
    one-time runbook."""
    src = WORKFLOW.read_text()
    azure_block = src.split("Configure Azure AD", 1)[1].split("Update container image", 1)[0]
    assert "exit 0" in azure_block, (
        "ct-wph: the Azure AD step must short-circuit with `exit 0` when "
        "secrets aren't configured (graceful no-op, not a deploy failure)"
    )
    assert "::warning::" in azure_block, (
        "ct-wph: missing-secrets short-circuit must emit a GitHub Actions "
        "warning so it's visible in the run log"
    )


def test_azure_ad_step_derives_endpoints_from_tenant_id():
    """The 5 discovery endpoints (issuer, jwks_uri, etc.) are deterministic
    from the tenant ID — derive them in shell, don't duplicate as secrets."""
    src = WORKFLOW.read_text()
    azure_block = src.split("Configure Azure AD", 1)[1].split("Update container image", 1)[0]
    # Each derived endpoint must reference the tenant_id-based login_base.
    for endpoint in (
        "AZURE_AD_AUTHORITY",
        "AZURE_AD_ISSUER",
        "AZURE_AD_TOKEN_ENDPOINT",
        "AZURE_AD_AUTHORIZATION_ENDPOINT",
        "AZURE_AD_JWKS_URI",
    ):
        assert endpoint in azure_block, (
            f"ct-wph: the Azure AD step must set {endpoint}"
        )
    # And the derivation logic itself must be present.
    assert "login.microsoftonline.com" in azure_block, (
        "ct-wph: derived endpoints must use the login.microsoftonline.com "
        "convention (matches the bicep template's authority computation)"
    )


def test_staging_secrets_runbook_exists():
    """A runbook must explain the one-time setup so Tyler doesn't have to
    remember the secret names from a code comment."""
    assert RUNBOOK.exists(), (
        "ct-wph: docs/runbooks/staging-secrets.md must exist to document "
        "the one-time GitHub Secret setup"
    )
    text = RUNBOOK.read_text()
    for required_secret in (
        "STAGING_AZURE_AD_TENANT_ID",
        "STAGING_AZURE_AD_CLIENT_ID",
        "STAGING_AZURE_AD_CLIENT_SECRET",
        "STAGING_ADMIN_EMAILS",
    ):
        assert required_secret in text, (
            f"ct-wph: runbook must document the {required_secret} secret"
        )
