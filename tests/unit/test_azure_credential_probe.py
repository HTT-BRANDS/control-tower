"""Tests for app/core/azure_credential_probe.py.

This probe is the post-ct-jxe fix for the 20-day silent outage: when
the production AZURE_AD_CLIENT_SECRET expired on 2026-04-29, every
``/health`` check said "azure_configured: true" because the env vars
were SHAPE-correct, while every actual token request silently failed.

The probe closes that gap by making a real client_credentials grant
against the token endpoint and reporting one of five statuses. These
tests pin the design properties so a future "let's simplify the
health check" PR can't quietly regress us back to shape-only.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import pytest

from app.core import azure_credential_probe as probe_mod
from app.core.azure_credential_probe import (
    PROBE_CACHE_TTL_SECONDS,
    PROBE_FAILURE_CACHE_TTL_SECONDS,
    ProbeResult,
    _redact_for_log,
    probe_client_credential,
    reset_probe_cache,
)

# ── Test fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_cache():
    """Each test gets a clean cache so prior runs don't bleed in."""
    reset_probe_cache()
    yield
    reset_probe_cache()


def _patch_httpx(monkeypatch: pytest.MonkeyPatch, transport: httpx.MockTransport) -> None:
    """Replace httpx.AsyncClient with one that uses our mock transport.

    httpx exposes a `transport` kwarg on AsyncClient, so we wrap the
    constructor to inject it. This is more honest than monkeypatching
    `post` directly because it exercises the real httpx serialization
    path (urlencoded body, headers, etc.).
    """
    real_async_client = httpx.AsyncClient

    def _factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(probe_mod.httpx, "AsyncClient", _factory)


# ── Status-mapping tests ───────────────────────────────────────────────────


class TestStatusMapping:
    """The five documented statuses must each map cleanly from inputs."""

    @pytest.mark.asyncio
    async def test_configured_on_200(self, monkeypatch: pytest.MonkeyPatch):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"access_token": "fake.jwt", "expires_in": 3599})

        _patch_httpx(monkeypatch, httpx.MockTransport(_handler))
        result = await probe_client_credential(
            tenant_id="t",
            client_id="c",
            client_secret="s" * 40,
            token_endpoint="https://login.microsoftonline.com/t/oauth2/v2.0/token",
            is_production=True,
        )
        assert result.status == "configured"
        assert result.http_status == 200
        assert result.azure_error_code is None

    @pytest.mark.asyncio
    async def test_unauthenticated_on_401_with_aadsts_code(self, monkeypatch: pytest.MonkeyPatch):
        """The exact ct-jxe scenario: expired secret -> AADSTS7000215."""

        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                401,
                json={
                    "error": "invalid_client",
                    "error_description": (
                        "AADSTS7000215: Invalid client secret provided. Ensure "
                        "the secret being sent in the request is the client "
                        "secret value, not the client secret ID..."
                    ),
                },
            )

        _patch_httpx(monkeypatch, httpx.MockTransport(_handler))
        result = await probe_client_credential(
            tenant_id="t",
            client_id="c",
            client_secret="s" * 40,
            token_endpoint="https://login.microsoftonline.com/t/oauth2/v2.0/token",
            is_production=True,
        )
        assert result.status == "unauthenticated"
        assert result.azure_error_code == "AADSTS7000215"
        assert result.http_status == 401
        # Detail must include the AADSTS message but stay bounded.
        assert "AADSTS7000215" in (result.detail or "")
        assert len(result.detail or "") <= 200

    @pytest.mark.asyncio
    async def test_unauthenticated_on_400_invalid_grant(self, monkeypatch: pytest.MonkeyPatch):
        """Azure also returns 400 for some credential failures."""

        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                400,
                json={
                    "error": "invalid_grant",
                    "error_description": "AADSTS50034: User does not exist in tenant",
                },
            )

        _patch_httpx(monkeypatch, httpx.MockTransport(_handler))
        result = await probe_client_credential(
            tenant_id="t",
            client_id="c",
            client_secret="s" * 40,
            token_endpoint="https://login.microsoftonline.com/t/oauth2/v2.0/token",
            is_production=True,
        )
        assert result.status == "unauthenticated"
        assert result.azure_error_code == "AADSTS50034"

    @pytest.mark.asyncio
    async def test_unreachable_on_timeout(self, monkeypatch: pytest.MonkeyPatch):
        def _handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("simulated timeout")

        _patch_httpx(monkeypatch, httpx.MockTransport(_handler))
        result = await probe_client_credential(
            tenant_id="t",
            client_id="c",
            client_secret="s" * 40,
            token_endpoint="https://login.microsoftonline.com/t/oauth2/v2.0/token",
            is_production=True,
        )
        assert result.status == "unreachable"
        assert "timed out" in (result.detail or "").lower()

    @pytest.mark.asyncio
    async def test_unreachable_on_connection_error(self, monkeypatch: pytest.MonkeyPatch):
        def _handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("simulated DNS failure")

        _patch_httpx(monkeypatch, httpx.MockTransport(_handler))
        result = await probe_client_credential(
            tenant_id="t",
            client_id="c",
            client_secret="s" * 40,
            token_endpoint="https://login.microsoftonline.com/t/oauth2/v2.0/token",
            is_production=True,
        )
        assert result.status == "unreachable"
        # The detail must mention the exception class, NOT raw network internals
        # (which could leak server IPs in some httpx versions).
        assert "ConnectError" in (result.detail or "")

    @pytest.mark.asyncio
    async def test_missing_when_creds_absent_in_prod(self):
        result = await probe_client_credential(
            tenant_id=None,
            client_id=None,
            client_secret=None,
            token_endpoint="https://login.microsoftonline.com/common/oauth2/v2.0/token",
            is_production=True,
        )
        assert result.status == "missing"

    @pytest.mark.asyncio
    async def test_not_required_when_creds_absent_outside_prod(self):
        """Don't poison local-dev /health with degraded just because the dev
        forgot to set AZURE_AD_*. ct-czv AC #2."""
        result = await probe_client_credential(
            tenant_id=None,
            client_id=None,
            client_secret=None,
            token_endpoint="https://login.microsoftonline.com/common/oauth2/v2.0/token",
            is_production=False,
        )
        assert result.status == "not_required"

    @pytest.mark.asyncio
    async def test_partial_creds_treated_as_missing(self):
        """Two-out-of-three set is just as broken as zero-out-of-three; must
        not trip a real network call."""
        result = await probe_client_credential(
            tenant_id="t",
            client_id="c",
            client_secret=None,
            token_endpoint="https://login.microsoftonline.com/t/oauth2/v2.0/token",
            is_production=True,
        )
        assert result.status == "missing"


# ── Caching behavior ───────────────────────────────────────────────────────


class TestCaching:
    """Cache TTLs must keep probe traffic low without holding stale state too
    long after a rotation."""

    @pytest.mark.asyncio
    async def test_success_is_cached(self, monkeypatch: pytest.MonkeyPatch):
        call_count = 0

        def _handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json={"access_token": "x"})

        _patch_httpx(monkeypatch, httpx.MockTransport(_handler))
        kwargs = {
            "tenant_id": "t",
            "client_id": "c",
            "client_secret": "s" * 40,
            "token_endpoint": "https://login.microsoftonline.com/t/oauth2/v2.0/token",
            "is_production": True,
        }
        r1 = await probe_client_credential(**kwargs)
        r2 = await probe_client_credential(**kwargs)
        r3 = await probe_client_credential(**kwargs)
        assert r1.status == r2.status == r3.status == "configured"
        assert call_count == 1, (
            "ct-jxe: probe must cache successful results — otherwise every "
            "uptime-monitor /health/detailed hit would burn a Graph token "
            "request"
        )

    @pytest.mark.asyncio
    async def test_use_cache_false_bypasses_cache(self, monkeypatch: pytest.MonkeyPatch):
        """Tests need to be able to opt out of caching. Production code should
        NOT use this — it's a test-only escape hatch."""
        call_count = 0

        def _handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json={"access_token": "x"})

        _patch_httpx(monkeypatch, httpx.MockTransport(_handler))
        kwargs = {
            "tenant_id": "t",
            "client_id": "c",
            "client_secret": "s" * 40,
            "token_endpoint": "https://login.microsoftonline.com/t/oauth2/v2.0/token",
            "is_production": True,
        }
        await probe_client_credential(**kwargs, use_cache=False)
        await probe_client_credential(**kwargs, use_cache=False)
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_cache_key_is_per_tenant_client_pair(self, monkeypatch: pytest.MonkeyPatch):
        """A deploy that swaps the app reg (different client_id) must NOT
        return a cached result from the OLD client_id. Same for tenant
        switches."""
        call_count = 0

        def _handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json={"access_token": "x"})

        _patch_httpx(monkeypatch, httpx.MockTransport(_handler))
        common = {
            "client_secret": "s" * 40,
            "token_endpoint": "https://login.microsoftonline.com/t/oauth2/v2.0/token",
            "is_production": True,
        }
        await probe_client_credential(tenant_id="t1", client_id="c1", **common)
        await probe_client_credential(tenant_id="t1", client_id="c2", **common)
        await probe_client_credential(tenant_id="t2", client_id="c1", **common)
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_failure_caches_for_shorter_window(self, monkeypatch: pytest.MonkeyPatch):
        """When Tyler rotates the secret, the dashboard should flip back to
        green within ~60s. Caching failures for the full 5 min would mean
        sitting on a stale 'unauthenticated' result for too long."""
        assert PROBE_FAILURE_CACHE_TTL_SECONDS < PROBE_CACHE_TTL_SECONDS, (
            "ct-jxe: failure cache TTL must be SHORTER than success cache "
            "TTL so post-rotation recovery is fast"
        )

    @pytest.mark.asyncio
    async def test_cache_respects_ttl_expiry(self, monkeypatch: pytest.MonkeyPatch):
        """A cached entry past its TTL must be re-probed."""
        call_count = 0

        def _handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json={"access_token": "x"})

        _patch_httpx(monkeypatch, httpx.MockTransport(_handler))
        kwargs = {
            "tenant_id": "t",
            "client_id": "c",
            "client_secret": "s" * 40,
            "token_endpoint": "https://login.microsoftonline.com/t/oauth2/v2.0/token",
            "is_production": True,
        }

        # First call populates cache.
        await probe_client_credential(**kwargs)
        assert call_count == 1

        # Fast-forward monotonic clock past the TTL.
        original_monotonic = time.monotonic
        offset = PROBE_CACHE_TTL_SECONDS + 1.0
        monkeypatch.setattr(
            probe_mod.time,
            "monotonic",
            lambda *a, **kw: original_monotonic() + offset,
        )

        await probe_client_credential(**kwargs)
        assert call_count == 2, "ct-jxe: expired cache entries must be re-probed"


# ── Safety invariants ──────────────────────────────────────────────────────


class TestSafetyInvariants:
    """These tests pin the contract: the probe must NEVER raise, never log
    the secret, and never block forever."""

    @pytest.mark.asyncio
    async def test_never_raises_on_garbage_response(self, monkeypatch: pytest.MonkeyPatch):
        """A token endpoint returning non-JSON garbage must still produce a
        ProbeResult, not a 500 in /health/detailed."""

        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, content=b"<html>500 Internal Server Error</html>")

        _patch_httpx(monkeypatch, httpx.MockTransport(_handler))
        result = await probe_client_credential(
            tenant_id="t",
            client_id="c",
            client_secret="s" * 40,
            token_endpoint="https://login.microsoftonline.com/t/oauth2/v2.0/token",
            is_production=True,
        )
        # Any non-200 is "unauthenticated" from the client's POV — we
        # can't differentiate Azure-rejecting-our-creds from Azure-having-a-bad-day
        # purely from status code, but the AADSTS-code field will be None to
        # signal the ambiguity.
        assert result.status == "unauthenticated"
        assert result.http_status == 500
        assert result.azure_error_code is None

    @pytest.mark.asyncio
    async def test_never_raises_on_internal_exception(self, monkeypatch: pytest.MonkeyPatch):
        """If httpx itself blows up in some weird way, the probe must still
        return a ProbeResult."""

        def _handler(request: httpx.Request) -> httpx.Response:
            raise RuntimeError("simulated unexpected error")

        _patch_httpx(monkeypatch, httpx.MockTransport(_handler))
        result = await probe_client_credential(
            tenant_id="t",
            client_id="c",
            client_secret="s" * 40,
            token_endpoint="https://login.microsoftonline.com/t/oauth2/v2.0/token",
            is_production=True,
        )
        assert result.status == "unreachable"

    def test_redact_for_log_strips_client_secret(self):
        """Trivially obvious, but lock it in — leaking the secret to logs is
        a recurring-rotation event no one wants to hit twice."""
        body = {
            "grant_type": "client_credentials",
            "client_id": "abc",
            "client_secret": "super-secret-value",
            "scope": "https://graph.microsoft.com/.default",
        }
        redacted = _redact_for_log(body)
        assert redacted is not None
        assert redacted["client_secret"] == "***REDACTED***"
        assert "super-secret-value" not in str(redacted)
        # Non-secret fields should pass through unmodified.
        assert redacted["client_id"] == "abc"
        assert redacted["grant_type"] == "client_credentials"

    def test_redact_for_log_handles_none(self):
        assert _redact_for_log(None) is None

    @pytest.mark.asyncio
    async def test_timeout_is_bounded(self, monkeypatch: pytest.MonkeyPatch):
        """The probe must NEVER hang indefinitely. We can't test that the
        timeout is exactly 5s without a real-time fixture, but we CAN
        verify the timeout config knob exists and is finite."""
        from app.core.azure_credential_probe import PROBE_TIMEOUT_SECONDS

        assert 0 < PROBE_TIMEOUT_SECONDS < 30, (
            "ct-jxe: PROBE_TIMEOUT_SECONDS must be finite and aggressive "
            "(health checks must not hang)"
        )


# ── ProbeResult.to_dict shape ──────────────────────────────────────────────


class TestProbeResultShape:
    """The shape returned by to_dict() lands directly in /health/detailed
    JSON. Stability matters for any dashboards / alert routing that parse it."""

    def test_minimal_configured_payload(self):
        # auth_mode is ALWAYS in the payload (defaults to "secret" for
        # backwards compat with pre-OIDC-migration probes).
        r = ProbeResult(status="configured", http_status=200)
        d = r.to_dict()
        assert d == {"status": "configured", "http_status": 200, "auth_mode": "secret"}

    def test_oidc_configured_payload_stamps_auth_mode(self):
        """After the OIDC migration, /health/detailed dashboards must show
        ``auth_mode: oidc`` to verify the flip succeeded. If this regresses
        to ``auth_mode: secret`` while USE_OIDC_FEDERATION=true, something
        silently fell back to the legacy path — which is exactly the kind
        of silent regression the post-ct-jxe probe is meant to catch."""
        r = ProbeResult(status="configured", auth_mode="oidc")
        d = r.to_dict()
        assert d["auth_mode"] == "oidc"
        assert d["status"] == "configured"

    def test_unauthenticated_payload_includes_aadsts_code(self):
        r = ProbeResult(
            status="unauthenticated",
            detail="AADSTS7000215: Invalid client secret",
            azure_error_code="AADSTS7000215",
            http_status=401,
        )
        d = r.to_dict()
        assert d["status"] == "unauthenticated"
        assert d["azure_error_code"] == "AADSTS7000215"
        assert d["http_status"] == 401
        assert "AADSTS7000215" in d["detail"]

    def test_missing_payload_has_detail(self):
        r = ProbeResult(status="missing", detail="AZURE_AD_* not set in production")
        d = r.to_dict()
        assert d["status"] == "missing"
        assert "AZURE_AD_*" in d["detail"]


# ── OIDC probe + dispatcher tests ──────────────────────────────────────────


class TestOIDCProbe:
    """probe_oidc_federation tests the FEDERATED path.

    Key contract: it must call into the OIDC credential provider, NOT the
    token endpoint directly. A regression here would mean the probe is
    testing a totally different path from what the runtime actually uses.
    """

    @pytest.mark.asyncio
    async def test_oidc_configured_when_get_token_succeeds(self, monkeypatch: pytest.MonkeyPatch):
        from unittest.mock import MagicMock

        from app.core.azure_credential_probe import probe_oidc_federation

        # Build a credential whose get_token returns a fake AccessToken.
        fake_token = MagicMock()
        fake_token.token = "fake.jwt"
        fake_credential = MagicMock()
        fake_credential.get_token.return_value = fake_token

        fake_provider = MagicMock()
        fake_provider.get_credential_for_tenant.return_value = fake_credential

        # Patch the lazy import target inside oidc_credential.
        import app.core.oidc_credential as oidc_mod

        monkeypatch.setattr(oidc_mod, "get_oidc_provider", lambda: fake_provider)

        result = await probe_oidc_federation(
            tenant_id="tid",
            client_id="cid",
            is_production=True,
        )
        assert result.status == "configured"
        assert result.auth_mode == "oidc", (
            "ct-oidc-migration: OIDC probe must stamp auth_mode='oidc' so "
            "/health/detailed dashboards can verify the migration succeeded"
        )
        # Sanity: the probe asked for the right scope (Graph .default).
        scope_arg = fake_credential.get_token.call_args.args[0]
        assert scope_arg == "https://graph.microsoft.com/.default"

    @pytest.mark.asyncio
    async def test_oidc_unauthenticated_on_sdk_authentication_error(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """When the federated credential is misconfigured (MI not bound,
        federated credential missing on app reg, audience mismatch), the
        azure-identity SDK raises ClientAuthenticationError. The probe must
        translate this to 'unauthenticated' — same status as the secret-
        path probe — so /health/detailed semantics stay identical across
        the OIDC migration. NEVER let the SDK exception escape."""
        from unittest.mock import MagicMock

        from app.core.azure_credential_probe import probe_oidc_federation

        # Simulate the SDK error. We don't import ClientAuthenticationError
        # here on purpose — a fake exception with a representative AADSTS-
        # bearing message is sufficient and avoids coupling the test to
        # azure-identity internals.
        class _FakeAuthError(Exception):
            pass

        fake_credential = MagicMock()
        fake_credential.get_token.side_effect = _FakeAuthError(
            "AADSTS700016: Application with identifier was not found"
        )

        fake_provider = MagicMock()
        fake_provider.get_credential_for_tenant.return_value = fake_credential

        import app.core.oidc_credential as oidc_mod

        monkeypatch.setattr(oidc_mod, "get_oidc_provider", lambda: fake_provider)

        result = await probe_oidc_federation(
            tenant_id="tid",
            client_id="cid",
            is_production=True,
        )
        assert result.status == "unauthenticated"
        assert result.auth_mode == "oidc"
        assert result.azure_error_code == "AADSTS700016"

    @pytest.mark.asyncio
    async def test_oidc_unreachable_on_timeout(self, monkeypatch: pytest.MonkeyPatch):
        """If the MI endpoint hangs, the probe must time out cleanly rather
        than blocking /health/detailed forever."""
        import time as time_mod
        from unittest.mock import MagicMock

        from app.core import azure_credential_probe as probe_mod
        from app.core.azure_credential_probe import probe_oidc_federation

        # Force the timeout to be near-zero so the test runs fast.
        monkeypatch.setattr(probe_mod, "PROBE_TIMEOUT_SECONDS", 0.05)

        def _slow_get_token(*args, **kwargs):
            time_mod.sleep(1.0)  # way longer than 0.05s

        fake_credential = MagicMock()
        fake_credential.get_token.side_effect = _slow_get_token

        fake_provider = MagicMock()
        fake_provider.get_credential_for_tenant.return_value = fake_credential

        import app.core.oidc_credential as oidc_mod

        monkeypatch.setattr(oidc_mod, "get_oidc_provider", lambda: fake_provider)

        result = await probe_oidc_federation(
            tenant_id="tid",
            client_id="cid",
            is_production=True,
        )
        assert result.status == "unreachable"
        assert result.auth_mode == "oidc"

    @pytest.mark.asyncio
    async def test_oidc_missing_when_tenant_or_client_absent_in_prod(self):
        from app.core.azure_credential_probe import probe_oidc_federation

        # Note: OIDC mode does NOT require client_secret — that's the whole
        # point. So 'missing' here means tenant_id or client_id absent, not
        # secret absent.
        result = await probe_oidc_federation(
            tenant_id=None,
            client_id="cid",
            is_production=True,
        )
        assert result.status == "missing"
        assert result.auth_mode == "oidc"
        assert "client_secret" not in (result.detail or "").lower(), (
            "OIDC 'missing' detail must NOT mention client_secret — that "
            "would be confusing in OIDC mode where secrets are explicitly "
            "not required"
        )

    @pytest.mark.asyncio
    async def test_oidc_not_required_outside_prod(self):
        from app.core.azure_credential_probe import probe_oidc_federation

        result = await probe_oidc_federation(
            tenant_id=None,
            client_id=None,
            is_production=False,
        )
        assert result.status == "not_required"
        assert result.auth_mode == "oidc"


class TestDispatcher:
    """probe_active_credential reads settings.use_oidc_federation and routes
    to the right probe. The dispatcher is THE source of truth for which path
    /health/detailed exercises — getting this wrong silently regresses
    monitoring."""

    @pytest.mark.asyncio
    async def test_dispatches_to_oidc_when_flag_true(self, monkeypatch: pytest.MonkeyPatch):
        from unittest.mock import AsyncMock, MagicMock

        from app.core import azure_credential_probe as probe_mod
        from app.core.azure_credential_probe import probe_active_credential

        oidc_stub = AsyncMock(
            return_value=probe_mod.ProbeResult(status="configured", auth_mode="oidc")
        )
        secret_stub = AsyncMock(
            return_value=probe_mod.ProbeResult(status="configured", auth_mode="secret")
        )
        monkeypatch.setattr(probe_mod, "probe_oidc_federation", oidc_stub)
        monkeypatch.setattr(probe_mod, "probe_client_credential", secret_stub)

        settings = MagicMock()
        settings.use_oidc_federation = True
        settings.azure_ad_tenant_id = "tid"
        settings.azure_ad_client_id = "cid"
        settings.azure_ad_client_secret = None  # NOT required in OIDC mode
        settings.azure_ad_token_endpoint = "https://login.microsoftonline.com/tid/oauth2/v2.0/token"
        settings.is_production = True

        result = await probe_active_credential(settings=settings)
        assert result.auth_mode == "oidc"
        oidc_stub.assert_awaited_once()
        (
            secret_stub.assert_not_called(),
            (
                "ct-oidc-migration: when use_oidc_federation=True, the secret-"
                "path probe must NOT be called. If it is, the dispatcher is "
                "OR-ing the two probes instead of dispatching, which would let "
                "a stale secret-mode 'configured' mask a broken OIDC config."
            ),
        )

    @pytest.mark.asyncio
    async def test_dispatches_to_secret_when_flag_false(self, monkeypatch: pytest.MonkeyPatch):
        from unittest.mock import AsyncMock, MagicMock

        from app.core import azure_credential_probe as probe_mod
        from app.core.azure_credential_probe import probe_active_credential

        oidc_stub = AsyncMock(
            return_value=probe_mod.ProbeResult(status="configured", auth_mode="oidc")
        )
        secret_stub = AsyncMock(
            return_value=probe_mod.ProbeResult(status="configured", auth_mode="secret")
        )
        monkeypatch.setattr(probe_mod, "probe_oidc_federation", oidc_stub)
        monkeypatch.setattr(probe_mod, "probe_client_credential", secret_stub)

        settings = MagicMock()
        settings.use_oidc_federation = False
        settings.azure_ad_tenant_id = "tid"
        settings.azure_ad_client_id = "cid"
        settings.azure_ad_client_secret = "s"
        settings.azure_ad_token_endpoint = "https://login.microsoftonline.com/tid/oauth2/v2.0/token"
        settings.is_production = True

        result = await probe_active_credential(settings=settings)
        assert result.auth_mode == "secret"
        secret_stub.assert_awaited_once()
        oidc_stub.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatcher_treats_missing_flag_as_secret_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Backwards-compat: if settings doesn't have ``use_oidc_federation``
        attribute at all (e.g. an older settings object during a migration),
        default to secret mode rather than crashing."""
        from unittest.mock import AsyncMock

        from app.core import azure_credential_probe as probe_mod
        from app.core.azure_credential_probe import probe_active_credential

        oidc_stub = AsyncMock()
        secret_stub = AsyncMock(
            return_value=probe_mod.ProbeResult(status="configured", auth_mode="secret")
        )
        monkeypatch.setattr(probe_mod, "probe_oidc_federation", oidc_stub)
        monkeypatch.setattr(probe_mod, "probe_client_credential", secret_stub)

        # A minimal object that lacks use_oidc_federation entirely.
        class _BareSettings:
            azure_ad_tenant_id = "tid"
            azure_ad_client_id = "cid"
            azure_ad_client_secret = "s"
            azure_ad_token_endpoint = "https://login.microsoftonline.com/tid/oauth2/v2.0/token"
            is_production = True

        result = await probe_active_credential(settings=_BareSettings())
        assert result.auth_mode == "secret"
        oidc_stub.assert_not_called()
