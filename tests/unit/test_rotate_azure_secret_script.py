"""Regression tests for scripts/rotate-azure-secret.sh (ct-jxe helper).

The script rotates the AZURE_AD_CLIENT_SECRET across all THREE places it
lives (prod webapp, staging webapp, GitHub Secret). Getting any of these
wrong has real consequences — log a secret to CI and you're rotating
again the same day. These tests pin the safety properties so a future
"refactor" can't quietly regress them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "rotate-azure-secret.sh"


@pytest.fixture(scope="module")
def src() -> str:
    return SCRIPT.read_text()


def test_script_exists_and_is_executable():
    """Tyler will copy-paste an invocation from the runbook; if the file isn't
    executable the prompt-paste flow breaks for no good reason."""
    assert SCRIPT.exists(), "ct-jxe: scripts/rotate-azure-secret.sh must exist"
    # Octal 0o111 = at least one execute bit set.
    assert SCRIPT.stat().st_mode & 0o111, (
        "ct-jxe: scripts/rotate-azure-secret.sh must be executable "
        "(chmod +x). Otherwise Tyler has to remember to bash-prefix it."
    )


def test_uses_set_euo_pipefail(src: str):
    """A secret-handling script that doesn't fail-fast is a foot-and-mouth."""
    assert "set -euo pipefail" in src, (
        "ct-jxe: must use `set -euo pipefail` so a partial failure doesn't "
        "leave half the targets pointing at the old secret"
    )


def test_secret_never_passed_via_argv(src: str):
    """The whole point of the script — secrets must travel via stdin/env,
    not via argv. argv leaks through `ps`, shell history, CI logs."""
    # The az setting assignment must use SETTING_NAME=${NEW_SECRET} via the
    # --settings flag (which is fine because it's not the raw secret in
    # argv, it's a variable substitution from env). The literal raw secret
    # value must never appear inline.
    # What we DO want to see: --settings "${SETTING_NAME}=${NEW_SECRET}"
    # What we DO NOT want: --settings AZURE_AD_CLIENT_SECRET=$1 or similar
    # positional-arg pattern.
    assert "${SETTING_NAME}=${NEW_SECRET}" in src, (
        "ct-jxe: the az appsetting assignment must use the variable form, not a raw inline secret"
    )
    # And `gh secret set` must read from stdin (printf piped in), not --body.
    # Match only the dangerous *call-site* pattern (gh secret set ... --body)
    # in real shell code, not the word "--body" appearing in inline comments
    # or docstrings explaining why we *avoid* --body. Strip shell comments
    # first (lines whose first non-whitespace char is `#`).
    assert "gh secret set" in src
    non_comment_src = "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    )
    dangerous_body_call = re.search(r"gh\s+secret\s+set[^\n]*--body", non_comment_src)
    assert dangerous_body_call is None, (
        "ct-jxe: gh secret set must read from stdin (piped via printf), "
        "NOT from --body — --body puts the secret in argv where it can "
        "be read by `ps` and recorded in /proc/<pid>/cmdline"
    )
    # The interactive read must use `read -s` (no terminal echo).
    assert "read -rs NEW_SECRET" in src, (
        "ct-jxe: interactive secret entry must use `read -rs` (silent) so "
        "the secret never appears on the user's terminal"
    )


def test_secret_is_unset_after_use(src: str):
    """After the writes complete, we unset NEW_SECRET so it doesn't sit
    in the script's env where a later `env | grep SECRET` could find it."""
    assert "unset NEW_SECRET" in src, (
        "ct-jxe: NEW_SECRET must be `unset` after the writes complete, so "
        "it doesn't linger in env for any post-rotation child processes"
    )


def test_min_length_validation(src: str):
    """A short paste (e.g. only the secret-id portion, not the value) would
    silently rotate the live secret into a broken state. Validate length."""
    assert "${#NEW_SECRET}" in src or "${#NEW_SECRET}" in src, (
        "ct-jxe: must validate ${#NEW_SECRET} length to catch truncated pastes"
    )
    assert re.search(r"\b32\b|\bminimum length\b", src), (
        "ct-jxe: must enforce a minimum length of at least 32 chars (default Azure secrets are 40)"
    )


def test_supports_dry_run(src: str):
    """A rotation script with no dry-run mode is impossible to test safely.
    Tyler needs to be able to validate az/gh auth + see the plan without
    actually touching the live secret."""
    assert "--dry-run" in src, "ct-jxe: must support --dry-run for safe pre-flight validation"
    assert "DRY_RUN=true" in src or 'DRY_RUN="true"' in src, (
        "ct-jxe: dry-run must short-circuit before any az/gh writes"
    )


def test_supports_skip_flags_for_partial_rotation(src: str):
    """If gh CLI isn't installed, or if Tyler wants to rotate just prod first
    and verify before touching staging, the script should support it."""
    for flag in ("--skip-prod", "--skip-staging", "--skip-github"):
        assert flag in src, f"ct-jxe: must support {flag} for partial-rotation flows"


def test_restarts_webapps_after_appsetting_change(src: str):
    """Setting an app setting on App Service doesn't always take effect
    until restart — particularly for env-var-driven config loaded at
    process start (which is exactly how the python settings module reads
    AZURE_AD_CLIENT_SECRET). Without a restart, the rotation is a no-op
    until the next platform-initiated recycle (could be hours)."""
    # Count distinct webapp-restart invocations — should be 2 (prod, staging)
    # OR more robustly: the restart_webapp helper must exist and be called.
    assert "az webapp restart" in src, (
        "ct-jxe: must restart both webapps after the appsetting change so "
        "the new value is picked up immediately, not on the next platform "
        "recycle (which could be hours)"
    )


def test_does_NOT_redeploy_or_touch_bicep(src: str):
    """A redeploy is a much bigger blast radius than an appsetting flip.
    The whole point of using `az webapp config appsettings set` is to make
    the rotation low-risk. Anyone editing this script must NOT swap it for
    a bicep redeploy."""
    forbidden = [
        "az deployment group create",
        "az deployment sub create",
        "bicep build",
        "parameters.staging.json",
        "parameters.production.json",
    ]
    for needle in forbidden:
        assert needle not in src, (
            f"ct-jxe: must NOT do a {needle} as part of secret rotation — "
            f"that's a much bigger blast radius than an appsetting flip"
        )


def test_post_rotation_verification_is_present(src: str):
    """After the writes succeed, the script must verify the rotation worked
    by hitting /health on both webapps and dumping /api/v1/health/data so
    Tyler can see sync timestamps start climbing."""
    assert "/health" in src, "ct-jxe: must include a /health readiness probe after restart"
    assert "/api/v1/health/data" in src, (
        "ct-jxe: must dump /api/v1/health/data so Tyler can confirm syncs "
        "actually start climbing (the whole point of rotating)"
    )


def test_documents_what_it_deliberately_does_not_do(src: str):
    """Future maintainers will be tempted to make this script 'more
    helpful' by generating the new secret automatically or updating
    parameters.staging.json. Both are bad ideas. Lock the no-go list
    in a comment so they read it first."""
    # Looking for the "DELIBERATELY DOES NOT DO" section.
    assert "DELIBERATELY DOES NOT DO" in src, (
        "ct-jxe: the script must include a 'WHAT THIS SCRIPT DELIBERATELY "
        "DOES NOT DO' section so future maintainers don't 'helpfully' add "
        "secret-generation or parameter-file-writing"
    )
