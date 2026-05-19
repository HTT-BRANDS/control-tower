"""Regression test for ct-9f1 / F-4: scripts/gh-setup.sh + docs must not
re-disable ``enforce_admins`` on main.

The audit recommended a CI gate that calls the GitHub API and fails if
``enforce_admins.enabled`` ever drifts to false — that gate lives in
``.github/workflows/weekly-ops.yml`` (added as part of this fix).

This test is the static-source counterpart: it makes sure the SCRIPTS
that set branch protection never paste ``enforce_admins: false`` again.
Without this check, someone could re-introduce the regression in a
local script edit and we'd only catch it on Monday when weekly-ops
ran (and by then a maintainer might already have run gh-setup.sh and
silently downgraded main).
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "gh-setup.sh"
DOC = ROOT / "docs" / "GITHUB_CLI_GUIDE.md"
WEEKLY_OPS = ROOT / ".github" / "workflows" / "weekly-ops.yml"


def test_gh_setup_script_uses_enforce_admins_true():
    """The branch-protection PUT body in gh-setup.sh must use true, not false."""
    src = SCRIPT.read_text()
    assert '"enforce_admins": true' in src, (
        "ct-9f1 / F-4: scripts/gh-setup.sh must POST `enforce_admins: true`. "
        "Anyone running ./scripts/gh-setup.sh would otherwise silently "
        "downgrade main branch protection."
    )
    assert '"enforce_admins": false' not in src, (
        "ct-9f1 / F-4: do NOT re-introduce `enforce_admins: false` into "
        "scripts/gh-setup.sh — even in comments or examples. The literal "
        "regex match here is intentional: if someone needs to demonstrate "
        "the disabled state, do it as a separate `false_example` variable, "
        "not as the active PUT body."
    )


def test_github_cli_guide_uses_enforce_admins_true():
    """The docs example must mirror the script — true, not false."""
    src = DOC.read_text()
    assert '"enforce_admins": true' in src, (
        "ct-9f1 / F-4: docs/GITHUB_CLI_GUIDE.md must document "
        "`enforce_admins: true` as the canonical configuration"
    )


def test_weekly_ops_has_enforce_admins_fitness_function():
    """The audit's recommended CI gate must be wired up in weekly-ops.yml."""
    src = WEEKLY_OPS.read_text()
    assert "branches/main/protection" in src, (
        "ct-9f1 / F-4: weekly-ops.yml must call the GitHub branch-protection "
        "API to check enforce_admins state"
    )
    assert "enforce_admins" in src, (
        "ct-9f1 / F-4: weekly-ops.yml must specifically check enforce_admins"
    )
    # And the check must actually fail the build (exit non-zero), not just
    # warn — a warning-only check would silently rot.
    assert "exit 1" in src, (
        "ct-9f1 / F-4: the enforce_admins check must hard-fail the workflow "
        "if drift is detected (otherwise it'd silently rot)"
    )
