"""Tests for app/core/oidc_client_assertion.py.

This module is the LAST place a runtime secret would be needed —
the OAuth authorization-code -> token exchange. By minting a federated
client_assertion JWT from the App Service Managed Identity instead of
sending a static client_secret, we eliminate the final runtime secret
dependency. These tests pin that behaviour.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.oidc_client_assertion import (
    ASSERTION_AUDIENCE,
    CLIENT_ASSERTION_TYPE,
    FederatedAssertionError,
    build_token_exchange_credentials,
    get_federated_client_assertion,
)


# ── Top-level dispatcher: build_token_exchange_credentials ─────────────────


class TestBuildTokenExchangeCredentials:
    """The single chokepoint that decides 'secret vs federated assertion'
    for every server-side token exchange. If this gets it wrong, EITHER
    we still send a secret in OIDC mode (silent migration regression)
    OR we send no credential at all (auth breaks)."""

    def test_secret_mode_returns_client_secret(self):
        fields = build_token_exchange_credentials(
            client_id="cid",
            client_secret="static-secret",  # noqa: S106 — test fixture
            use_oidc_federation=False,
        )
        assert fields == {"client_id": "cid", "client_secret": "static-secret"}
        assert "client_assertion" not in fields, (
            "ct-oidc-migration: secret-mode must NOT smuggle a federated "
            "assertion into the request"
        )

    def test_oidc_mode_returns_client_assertion(self, monkeypatch: pytest.MonkeyPatch):
        """In OIDC mode the function calls get_federated_client_assertion()
        and returns assertion fields. NO client_secret in the output."""
        from app.core import oidc_client_assertion as mod

        monkeypatch.setattr(
            mod, "get_federated_client_assertion", lambda: "fake.jwt.assertion"
        )

        fields = build_token_exchange_credentials(
            client_id="cid",
            client_secret="static-secret",  # noqa: S106 — should be ignored
            use_oidc_federation=True,
        )
        assert fields["client_id"] == "cid"
        assert fields["client_assertion"] == "fake.jwt.assertion"
        assert fields["client_assertion_type"] == CLIENT_ASSERTION_TYPE
        assert "client_secret" not in fields, (
            "ct-oidc-migration: OIDC mode must NEVER include client_secret "
            "in the token exchange — that defeats the purpose"
        )

    def test_oidc_mode_ignores_provided_secret(self, monkeypatch: pytest.MonkeyPatch):
        """A leftover AZURE_AD_CLIENT_SECRET env var during the migration
        must NOT cause us to fall back to secret mode if the flag is on.
        The flag is authoritative."""
        from app.core import oidc_client_assertion as mod

        monkeypatch.setattr(mod, "get_federated_client_assertion", lambda: "jwt")

        fields = build_token_exchange_credentials(
            client_id="cid",
            client_secret="leftover-secret",  # noqa: S106 — test fixture
            use_oidc_federation=True,
        )
        assert "client_secret" not in fields
        assert fields["client_assertion"] == "jwt"

    def test_secret_mode_raises_when_secret_missing(self):
        """Defensive: if neither path is properly configured, fail LOUD
        rather than sending a malformed (no-credential) request."""
        with pytest.raises(ValueError, match="USE_OIDC_FEDERATION"):
            build_token_exchange_credentials(
                client_id="cid",
                client_secret=None,
                use_oidc_federation=False,
            )

    def test_oidc_mode_propagates_assertion_error(self, monkeypatch: pytest.MonkeyPatch):
        """If MI is unreachable, FederatedAssertionError must propagate so
        the OAuth callback can return a distinct 503 (not a generic 5xx).
        The callers depend on this exception type to decide which runbook
        to surface."""
        from app.core import oidc_client_assertion as mod

        def _boom() -> str:
            raise FederatedAssertionError("MI not bound")

        monkeypatch.setattr(mod, "get_federated_client_assertion", _boom)

        with pytest.raises(FederatedAssertionError):
            build_token_exchange_credentials(
                client_id="cid",
                client_secret=None,
                use_oidc_federation=True,
            )


# ── get_federated_client_assertion: MI integration ─────────────────────────


class TestGetFederatedClientAssertion:
    """Direct tests for the MI -> assertion-JWT round trip."""

    def test_returns_token_from_mi(self, monkeypatch: pytest.MonkeyPatch):
        fake_token = MagicMock()
        fake_token.token = "header.payload.signature"  # noqa: S105 — test fixture

        fake_mi = MagicMock()
        fake_mi.get_token.return_value = fake_token

        fake_provider = MagicMock()
        fake_provider._get_mi_credential.return_value = fake_mi

        import app.core.oidc_credential as oidc_mod

        monkeypatch.setattr(oidc_mod, "get_oidc_provider", lambda: fake_provider)

        result = get_federated_client_assertion()
        assert result == "header.payload.signature"

        # Sanity: the assertion audience must be the constant. If this
        # gets mis-typed, Entra will silently reject every login.
        audience_arg = fake_mi.get_token.call_args.args[0]
        assert audience_arg == ASSERTION_AUDIENCE
        assert audience_arg == "api://AzureADTokenExchange", (
            "The MI assertion audience is contractual — DO NOT change it "
            "without coordinating an Azure AD app reg federated-credential "
            "update at the same time."
        )

    def test_raises_federated_assertion_error_when_mi_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Any exception from the MI path is re-wrapped as
        FederatedAssertionError so callers can distinguish OIDC-broken
        from Entra-rejection. NEVER let azure-identity exceptions escape."""

        class _ClientAuthErrorFake(Exception):
            pass

        fake_mi = MagicMock()
        fake_mi.get_token.side_effect = _ClientAuthErrorFake(
            "ManagedIdentityCredential authentication unavailable, "
            "no managed identity endpoint found."
        )

        fake_provider = MagicMock()
        fake_provider._get_mi_credential.return_value = fake_mi

        import app.core.oidc_credential as oidc_mod

        monkeypatch.setattr(oidc_mod, "get_oidc_provider", lambda: fake_provider)

        with pytest.raises(FederatedAssertionError) as excinfo:
            get_federated_client_assertion()

        # The wrapped message must include the original exception's class
        # name and message — otherwise operators have no clue what went
        # wrong at 3am.
        assert "_ClientAuthErrorFake" in str(excinfo.value)
        assert "endpoint found" in str(excinfo.value)

    def test_raises_when_mi_returns_empty_token(self, monkeypatch: pytest.MonkeyPatch):
        """The SDK has been observed to return AccessToken instances with
        empty .token strings during throttle events. We must fail LOUD
        rather than send an empty client_assertion to Entra."""
        fake_token = MagicMock()
        fake_token.token = ""

        fake_mi = MagicMock()
        fake_mi.get_token.return_value = fake_token

        fake_provider = MagicMock()
        fake_provider._get_mi_credential.return_value = fake_mi

        import app.core.oidc_credential as oidc_mod

        monkeypatch.setattr(oidc_mod, "get_oidc_provider", lambda: fake_provider)

        with pytest.raises(FederatedAssertionError, match="empty"):
            get_federated_client_assertion()

    def test_raises_when_mi_returns_none(self, monkeypatch: pytest.MonkeyPatch):
        fake_mi = MagicMock()
        fake_mi.get_token.return_value = None

        fake_provider = MagicMock()
        fake_provider._get_mi_credential.return_value = fake_mi

        import app.core.oidc_credential as oidc_mod

        monkeypatch.setattr(oidc_mod, "get_oidc_provider", lambda: fake_provider)

        with pytest.raises(FederatedAssertionError):
            get_federated_client_assertion()


# ── Constants pinning ──────────────────────────────────────────────────────


class TestConstants:
    """The two module-level constants are part of the Microsoft Entra
    contract. Pin them so a typo PR can't silently break logins."""

    def test_assertion_audience_constant(self):
        # If you change this, the federated credential on the app reg
        # has to change to match — these MUST be edited together.
        assert ASSERTION_AUDIENCE == "api://AzureADTokenExchange"

    def test_client_assertion_type_constant(self):
        # RFC 7521 fixed URN. Microsoft will reject anything else.
        assert (
            CLIENT_ASSERTION_TYPE
            == "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
        )
