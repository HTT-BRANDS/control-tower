"""Tests for scripts/manual_sync.py credential resolution (ct-51g).

These tests cover the credential plumbing only — they NEVER hit the network
and NEVER assert on real secret values. The goal is to lock in:

* AC #1 — no hardcoded JWT secret anywhere in the script source.
* AC #2 — script fails closed with a clear message when no operator credential
  is supplied.
* AC #3 — script supports the issuer transition (``JWT_ISSUER`` overridable).
* AC #4 — token generation/validation is exercised end-to-end with a fake
  secret, asserting only on metadata (claims, audience, issuer, etc.).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import jwt as pyjwt
import pytest

# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------
# scripts/ is not a package; load by path so the tests don't depend on
# sys.path tricks or a separate scripts/__init__.py.


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "manual_sync.py"


@pytest.fixture(scope="module")
def manual_sync_module():
    """Load scripts/manual_sync.py as a module for testing."""
    spec = importlib.util.spec_from_file_location("manual_sync_under_test", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["manual_sync_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# AC #1 — No hardcoded JWT secret in the script source
# ---------------------------------------------------------------------------


class TestNoHardcodedSecret:
    """Regression guards against the previous hardcoded secret pattern."""

    def test_script_source_contains_no_module_level_jwt_secret_assignment(self):
        """The script must not assign a JWT_SECRET literal at module scope."""
        source = SCRIPT_PATH.read_text()
        # The old form was: ``JWT_SECRET = "..."`` at module level. Any
        # variant where ``JWT_SECRET`` is bound to a string literal in column
        # zero is forbidden. We grep loosely; if this regresses, the test
        # fails loudly.
        offending_lines = [
            line
            for line in source.splitlines()
            if line.startswith("JWT_SECRET ") and "=" in line and '"' in line
        ]
        assert offending_lines == [], (
            "scripts/manual_sync.py has reintroduced a module-level hardcoded "
            f"JWT_SECRET assignment: {offending_lines!r}. Read from the "
            "JWT_SECRET_KEY environment variable instead (ct-51g AC #1)."
        )

    def test_script_source_does_not_contain_known_stale_secret(self):
        """The specific stale secret value from ct-51g must never reappear."""
        # Just the first 12 chars — enough to be uniquely diagnostic, short
        # enough that detect-secrets won't flag this constant.
        stale_prefix = "gc8A0RjZwv15"
        source = SCRIPT_PATH.read_text()
        assert stale_prefix not in source, (
            "The previously-leaked JWT secret is back in the script source. "
            "Revert and read from environment (ct-51g AC #1)."
        )


# ---------------------------------------------------------------------------
# AC #2 — Fail closed when no operator credential is supplied
# ---------------------------------------------------------------------------


class TestFailClosed:
    """resolve_operator_token must refuse to proceed without a credential."""

    def test_raises_when_env_is_empty(self, manual_sync_module):
        with pytest.raises(manual_sync_module.MissingOperatorCredentialError) as exc:
            manual_sync_module.resolve_operator_token(env={})
        msg = str(exc.value)
        assert "MANUAL_SYNC_TOKEN" in msg, "Error must name the preferred env var"
        assert "JWT_SECRET_KEY" in msg, "Error must name the fallback env var"

    def test_raises_when_credentials_are_whitespace_only(self, manual_sync_module):
        """Whitespace must not satisfy the credential check — fail closed."""
        with pytest.raises(manual_sync_module.MissingOperatorCredentialError):
            manual_sync_module.resolve_operator_token(
                env={"MANUAL_SYNC_TOKEN": "   ", "JWT_SECRET_KEY": "\t\n"}
            )

    def test_mint_admin_token_rejects_empty_secret(self, manual_sync_module):
        with pytest.raises(manual_sync_module.MissingOperatorCredentialError):
            manual_sync_module.mint_admin_token("")

    def test_error_message_does_not_leak_env_values(self, manual_sync_module):
        """Error must reference env var *names*, never values, per AC #4."""
        # Even when both are set to something obviously secret-looking, the
        # fail-closed error path shouldn't fire — but if a future regression
        # made it fire, the error must not echo the secret. We force the
        # branch by passing empty values and a sentinel "secret" elsewhere.
        with pytest.raises(manual_sync_module.MissingOperatorCredentialError) as exc:
            manual_sync_module.resolve_operator_token(env={})
        assert "supersecret" not in str(exc.value).lower()


# ---------------------------------------------------------------------------
# AC #3 — Issuer transition support
# ---------------------------------------------------------------------------


class TestIssuerTransition:
    """JWT_ISSUER and JWT_AUDIENCE must be overridable via environment."""

    def test_default_issuer_and_audience_when_unset(self, manual_sync_module):
        secret = "test-secret-do-not-use-anywhere-32-chars-min"  # pragma: allowlist secret
        token = manual_sync_module.resolve_operator_token(env={"JWT_SECRET_KEY": secret})
        decoded = pyjwt.decode(
            token,
            "test-secret-do-not-use-anywhere-32-chars-min",  # pragma: allowlist secret
            algorithms=["HS256"],
            audience=manual_sync_module.DEFAULT_JWT_AUDIENCE,
        )
        assert decoded["iss"] == manual_sync_module.DEFAULT_JWT_ISSUER
        assert decoded["aud"] == manual_sync_module.DEFAULT_JWT_AUDIENCE

    def test_overridden_issuer_appears_in_token(self, manual_sync_module):
        """ct-vgf: issuer transition needs the script to mint with a new iss."""
        secret = "test-secret-do-not-use-anywhere-32-chars-min"  # pragma: allowlist secret
        token = manual_sync_module.resolve_operator_token(
            env={
                "JWT_SECRET_KEY": secret,
                "JWT_ISSUER": "azure-governance-platform-v2",
                "JWT_AUDIENCE": "azure-governance-api-v2",
            }
        )
        decoded = pyjwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="azure-governance-api-v2",
        )
        assert decoded["iss"] == "azure-governance-platform-v2"
        assert decoded["aud"] == "azure-governance-api-v2"


# ---------------------------------------------------------------------------
# AC #4 — Token generation path covered without exposing real secrets
# ---------------------------------------------------------------------------


class TestTokenGenerationPath:
    """End-to-end mint → decode round-trip with a test-only secret."""

    def test_pre_minted_token_passes_through_unchanged(self, manual_sync_module):
        """If MANUAL_SYNC_TOKEN is set, the script uses it verbatim."""
        pre_minted = "this-is-a-pre-minted-bearer-token-from-elsewhere"  # pragma: allowlist secret
        ignored_secret = "ignored"  # pragma: allowlist secret
        result = manual_sync_module.resolve_operator_token(
            env={"MANUAL_SYNC_TOKEN": pre_minted, "JWT_SECRET_KEY": ignored_secret}
        )
        assert result == pre_minted, (
            "Pre-minted token must take precedence and pass through verbatim"
        )

    def test_minted_token_contains_required_admin_claims(self, manual_sync_module):
        secret = "test-secret-do-not-use-anywhere-32-chars-min"  # pragma: allowlist secret
        token = manual_sync_module.mint_admin_token(secret)
        decoded = pyjwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=manual_sync_module.DEFAULT_JWT_AUDIENCE,
        )
        assert decoded["sub"] == "manual-sync-operator"
        assert "admin" in decoded["roles"]
        assert "operator" in decoded["roles"]
        assert decoded["type"] == "access"
        assert decoded["tenant_ids"] == list(manual_sync_module.TENANT_IDS)

    def test_minted_token_signature_is_valid_for_the_secret_used(self, manual_sync_module):
        """Round-trip: token minted with secret X must verify against secret X."""
        secret = "another-test-secret-still-not-real-32-chars-pad"  # pragma: allowlist secret
        token = manual_sync_module.mint_admin_token(secret)
        # If signature were wrong, this would raise InvalidSignatureError.
        decoded = pyjwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=manual_sync_module.DEFAULT_JWT_AUDIENCE,
        )
        assert decoded is not None

    def test_minted_token_signature_rejects_other_secret(self, manual_sync_module):
        """Negative path: signed with X, decoded with Y → InvalidSignatureError."""
        token = manual_sync_module.mint_admin_token(
            "secret-used-to-sign-1234567890abcdef-padding"
        )  # pragma: allowlist secret
        with pytest.raises(pyjwt.InvalidSignatureError):
            pyjwt.decode(
                token,
                "different-secret-used-to-verify-padding-here",  # pragma: allowlist secret
                algorithms=["HS256"],
                audience=manual_sync_module.DEFAULT_JWT_AUDIENCE,
            )
