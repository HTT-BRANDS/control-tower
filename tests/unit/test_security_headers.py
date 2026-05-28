"""Tests for security headers middleware.

Covers SecurityHeadersMiddleware, SecurityHeadersConfig presets,
convenience classes, and the create_security_middleware factory.
"""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.security_headers import (
    DEFAULT_PERMISSIONS_POLICY,
    BalancedSecurityHeadersMiddleware,
    RelaxedSecurityHeadersMiddleware,
    SecurityHeadersConfig,
    SecurityHeadersMiddleware,
    StrictSecurityHeadersMiddleware,
    create_security_middleware,
)


def _make_settings(*, is_development: bool = True):
    """Create a mock settings object."""
    settings = MagicMock()
    settings.is_development = is_development
    return settings


def _make_app(middleware_cls=None, middleware_kwargs=None, *, is_development: bool = True):
    """Create a minimal FastAPI app with SecurityHeadersMiddleware.

    Patches get_settings so the middleware sees the mock.
    The patch is started (not stopped) so it stays active when Starlette
    defers middleware __init__ to the first request.  Each test creates a
    fresh patcher, and pytest teardown handles cleanup.
    """
    mock_settings = _make_settings(is_development=is_development)
    patcher = patch(
        "app.core.security_headers.get_settings",
        return_value=mock_settings,
    )
    patcher.start()  # remains active through request processing

    app = FastAPI()
    kwargs = middleware_kwargs or {}
    if middleware_cls is None:
        app.add_middleware(SecurityHeadersMiddleware, **kwargs)
    else:
        app.add_middleware(middleware_cls, **kwargs)

    @app.get("/test")
    async def test_route(request: Request):
        return {"nonce": request.state.csp_nonce}

    @app.get("/metrics")
    async def metrics_route():
        return {"metrics": True}

    @app.get("/health")
    async def health_route():
        return {"ok": True}

    client = TestClient(app)
    # Trigger a request to force middleware __init__ while patch is active.
    # After init, self.settings is captured; the patch is no longer needed.
    client.get("/test")
    patcher.stop()
    return client


# ---------------------------------------------------------------------------
# Core security headers presence
# ---------------------------------------------------------------------------


class TestSecurityHeadersPresence:
    """Verify all expected security headers are present on responses."""

    def test_x_frame_options_present(self):
        client = _make_app()
        resp = client.get("/test")
        assert "X-Frame-Options" in resp.headers

    def test_x_frame_options_is_deny(self):
        client = _make_app()
        resp = client.get("/test")
        assert resp.headers["X-Frame-Options"] == "DENY"

    def test_x_content_type_options_present(self):
        client = _make_app()
        resp = client.get("/test")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"

    def test_x_xss_protection_present(self):
        client = _make_app()
        resp = client.get("/test")
        assert resp.headers["X-XSS-Protection"] == "1; mode=block"

    def test_referrer_policy_present(self):
        client = _make_app()
        resp = client.get("/test")
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_permissions_policy_present(self):
        client = _make_app()
        resp = client.get("/test")
        assert "Permissions-Policy" in resp.headers
        policy = resp.headers["Permissions-Policy"]
        assert "camera=()" in policy
        assert "microphone=()" in policy
        assert "geolocation=()" in policy

    def test_cross_origin_resource_policy(self):
        client = _make_app()
        resp = client.get("/test")
        assert resp.headers["Cross-Origin-Resource-Policy"] == "same-origin"

    def test_cross_origin_opener_policy(self):
        client = _make_app()
        resp = client.get("/test")
        assert resp.headers["Cross-Origin-Opener-Policy"] == "same-origin-allow-popups"

    def test_cross_origin_embedder_policy(self):
        client = _make_app()
        resp = client.get("/test")
        assert resp.headers["Cross-Origin-Embedder-Policy"] == "require-corp"

    def test_document_policy(self):
        client = _make_app()
        resp = client.get("/test")
        assert resp.headers["Document-Policy"] == "force-load-at-top"

    def test_content_security_policy_present(self):
        client = _make_app()
        resp = client.get("/test")
        assert "Content-Security-Policy" in resp.headers

    def test_server_header_minimized(self):
        client = _make_app()
        resp = client.get("/test")
        assert resp.headers["Server"] == "Azure-Governance-Platform"


# ---------------------------------------------------------------------------
# CSP nonce
# ---------------------------------------------------------------------------


class TestCSPNonce:
    """Verify CSP nonce generation and uniqueness."""

    def test_csp_contains_nonce(self):
        client = _make_app()
        resp = client.get("/test")
        csp = resp.headers["Content-Security-Policy"]
        assert "'nonce-" in csp

    def test_nonce_unique_per_request(self):
        client = _make_app()
        nonces = set()
        for _ in range(5):
            resp = client.get("/test")
            csp = resp.headers["Content-Security-Policy"]
            # Extract nonce value from CSP
            for part in csp.split():
                if part.startswith("'nonce-"):
                    nonces.add(part)
        # All 5 should be unique
        assert len(nonces) == 5

    def test_nonce_available_on_request_state(self):
        client = _make_app()
        resp = client.get("/test")
        nonce = resp.json()["nonce"]
        assert nonce  # non-empty
        assert len(nonce) > 20  # secrets.token_urlsafe(32) is ~43 chars

    def test_nonce_in_csp_matches_request_state(self):
        client = _make_app()
        resp = client.get("/test")
        nonce_from_state = resp.json()["nonce"]
        csp = resp.headers["Content-Security-Policy"]
        assert f"'nonce-{nonce_from_state}'" in csp


# ---------------------------------------------------------------------------
# HSTS (production vs development)
# ---------------------------------------------------------------------------


class TestHSTS:
    """Strict-Transport-Security in all environments with environment-specific max-age."""

    def test_hsts_present_in_development_with_short_max_age(self):
        """HSTS is now present in development with short max-age (5 minutes)."""
        client = _make_app(is_development=True)
        resp = client.get("/test")
        assert "Strict-Transport-Security" in resp.headers
        hsts = resp.headers["Strict-Transport-Security"]
        assert "max-age=300" in hsts
        assert "includeSubDomains" in hsts

    def test_hsts_present_in_production(self):
        client = _make_app(is_development=False)
        resp = client.get("/test")
        assert "Strict-Transport-Security" in resp.headers
        hsts = resp.headers["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts

    def test_hsts_preload_flag(self):
        client = _make_app(
            middleware_kwargs={"hsts_preload": True},
            is_development=False,
        )
        resp = client.get("/test")
        hsts = resp.headers["Strict-Transport-Security"]
        assert "preload" in hsts

    def test_hsts_without_subdomains(self):
        client = _make_app(
            middleware_kwargs={"hsts_include_subdomains": False},
            is_development=False,
        )
        resp = client.get("/test")
        hsts = resp.headers["Strict-Transport-Security"]
        assert "includeSubDomains" not in hsts

    def test_hsts_custom_max_age(self):
        client = _make_app(
            middleware_kwargs={"hsts_max_age": 86400},
            is_development=False,
        )
        resp = client.get("/test")
        hsts = resp.headers["Strict-Transport-Security"]
        assert "max-age=86400" in hsts


# ---------------------------------------------------------------------------
# skip_paths
# ---------------------------------------------------------------------------


class TestSkipPaths:
    """Paths in skip_paths receive MINIMAL security headers (no CSP).

    Rationale: CSP can break text/plain Prometheus scrapers, but
    X-Frame-Options, HSTS, etc. are safe and required for defense-in-depth.
    """

    def test_metrics_path_gets_minimal_headers(self):
        client = _make_app()
        resp = client.get("/metrics")
        # Minimal headers present
        assert "X-Frame-Options" in resp.headers
        assert "Strict-Transport-Security" in resp.headers
        assert "Server" in resp.headers
        # CSP NOT present (would break scrapers)
        assert "Content-Security-Policy" not in resp.headers

    def test_custom_skip_paths(self):
        client = _make_app(
            middleware_kwargs={"skip_paths": ("/health", "/metrics")},
        )
        for path in ("/health", "/metrics"):
            resp = client.get(path)
            assert "X-Frame-Options" in resp.headers
            assert "Strict-Transport-Security" in resp.headers
            assert "Content-Security-Policy" not in resp.headers

        # Non-skipped path still gets full headers including CSP
        resp_test = client.get("/test")
        assert "X-Frame-Options" in resp_test.headers
        assert "Content-Security-Policy" in resp_test.headers

    def test_non_skipped_path_gets_headers(self):
        client = _make_app()
        resp = client.get("/test")
        assert "X-Frame-Options" in resp.headers
        assert "Content-Security-Policy" in resp.headers


# ---------------------------------------------------------------------------
# SecurityHeadersConfig presets
# ---------------------------------------------------------------------------


class TestSecurityHeadersConfigPresets:
    """Test strict / balanced / relaxed presets."""

    def test_strict_preset_returns_dict(self):
        config = SecurityHeadersConfig.strict()
        assert isinstance(config, dict)
        assert "csp_directives" in config
        assert "permissions_policy" in config

    def test_strict_csp_no_external_scripts(self):
        config = SecurityHeadersConfig.strict()
        script_src = config["csp_directives"]["script-src"]
        # Strict should NOT allow CDN origins
        assert "unpkg.com" not in script_src
        assert "cdn.jsdelivr.net" not in script_src

    def test_strict_coop_is_same_origin(self):
        config = SecurityHeadersConfig.strict()
        assert config["coop_policy"] == "same-origin"

    def test_balanced_preset_allows_cdn(self):
        config = SecurityHeadersConfig.balanced()
        script_src = config["csp_directives"]["script-src"]
        assert "unpkg.com" in script_src or "cdn.jsdelivr.net" in script_src

    def test_balanced_uses_default_permissions(self):
        config = SecurityHeadersConfig.balanced()
        assert config["permissions_policy"] == DEFAULT_PERMISSIONS_POLICY

    def test_relaxed_preset_allows_eval(self):
        config = SecurityHeadersConfig.relaxed()
        script_src = config["csp_directives"]["script-src"]
        assert "'unsafe-eval'" in script_src

    def test_relaxed_corp_is_cross_origin(self):
        config = SecurityHeadersConfig.relaxed()
        assert config["corp_policy"] == "cross-origin"

    def test_relaxed_coop_is_unsafe_none(self):
        config = SecurityHeadersConfig.relaxed()
        assert config["coop_policy"] == "unsafe-none"

    def test_strict_middleware_applies_strict_headers(self):
        """StrictSecurityHeadersMiddleware uses strict preset."""
        with patch(
            "app.core.security_headers.get_settings",
            return_value=_make_settings(is_development=False),
        ):
            app = FastAPI()
            app.add_middleware(StrictSecurityHeadersMiddleware)

            @app.get("/test")
            async def root():
                return {"ok": True}

        client = TestClient(app)
        resp = client.get("/test")
        csp = resp.headers["Content-Security-Policy"]
        # Strict: no CDN sources
        assert "unpkg.com" not in csp

    def test_balanced_middleware_class(self):
        """BalancedSecurityHeadersMiddleware uses balanced preset."""
        with patch(
            "app.core.security_headers.get_settings",
            return_value=_make_settings(is_development=True),
        ):
            app = FastAPI()
            app.add_middleware(BalancedSecurityHeadersMiddleware)

            @app.get("/test")
            async def root():
                return {"ok": True}

        client = TestClient(app)
        resp = client.get("/test")
        csp = resp.headers["Content-Security-Policy"]
        assert "cdn.jsdelivr.net" in csp

    def test_relaxed_middleware_class(self):
        """RelaxedSecurityHeadersMiddleware uses relaxed preset."""
        with patch(
            "app.core.security_headers.get_settings",
            return_value=_make_settings(is_development=True),
        ):
            app = FastAPI()
            app.add_middleware(RelaxedSecurityHeadersMiddleware)

            @app.get("/test")
            async def root():
                return {"ok": True}

        client = TestClient(app)
        resp = client.get("/test")
        assert resp.headers["Cross-Origin-Resource-Policy"] == "cross-origin"


# ---------------------------------------------------------------------------
# create_security_middleware factory
# ---------------------------------------------------------------------------


class TestCreateSecurityMiddleware:
    """Test the create_security_middleware factory function."""

    def test_factory_returns_callable(self):
        factory = create_security_middleware("strict")
        assert callable(factory)

    def test_factory_unknown_level_falls_back_to_balanced(self):
        """Unknown security level falls back to balanced config."""
        with patch(
            "app.core.security_headers.get_settings",
            return_value=_make_settings(),
        ):
            app = FastAPI()
            factory = create_security_middleware("nonexistent")
            app.add_middleware(factory)

            @app.get("/test")
            async def root():
                return {"ok": True}

        client = TestClient(app)
        resp = client.get("/test")
        # Balanced allows CDN
        csp = resp.headers["Content-Security-Policy"]
        assert "cdn.jsdelivr.net" in csp


# ---------------------------------------------------------------------------
# Custom middleware parameters
# ---------------------------------------------------------------------------


class TestCustomParameters:
    """Test passing custom values to the middleware constructor."""

    def test_custom_referrer_policy(self):
        client = _make_app(middleware_kwargs={"referrer_policy": "no-referrer"})
        resp = client.get("/test")
        assert resp.headers["Referrer-Policy"] == "no-referrer"

    def test_custom_permissions_policy(self):
        custom = "camera=(self), microphone=()"
        client = _make_app(middleware_kwargs={"permissions_policy": custom})
        resp = client.get("/test")
        assert resp.headers["Permissions-Policy"] == custom

    def test_custom_csp_directives(self):
        custom_csp = {
            "default-src": "'none'",
            "script-src": "'nonce-{nonce}'",
        }
        client = _make_app(middleware_kwargs={"csp_directives": custom_csp})
        resp = client.get("/test")
        csp = resp.headers["Content-Security-Policy"]
        assert "default-src 'none'" in csp
        assert "'nonce-" in csp


# ---------------------------------------------------------------------------
# CSP directive building
# ---------------------------------------------------------------------------


class TestCSPBuilding:
    """Test _build_csp edge cases."""

    def test_csp_upgrade_insecure_requests_no_value(self):
        """Directives with empty values appear without a value."""
        client = _make_app()
        resp = client.get("/test")
        csp = resp.headers["Content-Security-Policy"]
        # upgrade-insecure-requests should appear alone (no value)
        assert "upgrade-insecure-requests" in csp

    def test_default_csp_has_frame_ancestors_none(self):
        client = _make_app()
        resp = client.get("/test")
        csp = resp.headers["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in csp

    def test_default_csp_has_object_src_none(self):
        client = _make_app()
        resp = client.get("/test")
        csp = resp.headers["Content-Security-Policy"]
        assert "object-src 'none'" in csp
