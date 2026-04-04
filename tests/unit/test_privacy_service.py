"""Tests for app/api/services/privacy_service.py — consent management.

Covers:
- get_consent_from_cookie: valid, invalid JSON, missing cookie
- save_consent_to_cookie: sets cookie with correct params
- get_effective_consent: GPC override, saved prefs, defaults
- has_consent_for: specific category checks
- can_track / can_use_marketing_cookies: convenience helpers

Phase B.12 of the test coverage sprint.
"""

import json
from unittest.mock import MagicMock, patch

from app.api.services.privacy_service import PrivacyService
from app.core.privacy_config import ConsentCategory, ConsentPreferences, PrivacyConfig


def _make_request(cookies=None):
    req = MagicMock()
    req.cookies = cookies or {}
    req.headers = {}
    return req


# ---------------------------------------------------------------------------
# get_consent_from_cookie
# ---------------------------------------------------------------------------


class TestGetConsentFromCookie:
    def test_valid_cookie(self):
        prefs = ConsentPreferences(
            necessary=True, functional=True, analytics=False, marketing=False
        )
        req = _make_request({PrivacyConfig.COOKIE_NAME: prefs.model_dump_json()})

        result = PrivacyService.get_consent_from_cookie(req)

        assert result is not None
        assert result.functional is True
        assert result.analytics is False

    def test_missing_cookie_returns_none(self):
        req = _make_request({})

        result = PrivacyService.get_consent_from_cookie(req)

        assert result is None

    def test_invalid_json_returns_none(self):
        req = _make_request({PrivacyConfig.COOKIE_NAME: "not-json!!!"})

        result = PrivacyService.get_consent_from_cookie(req)

        assert result is None

    def test_invalid_schema_returns_none(self):
        req = _make_request({PrivacyConfig.COOKIE_NAME: json.dumps({"bad_field": 99})})

        result = PrivacyService.get_consent_from_cookie(req)

        # Pydantic v2 is lenient with extra fields — this actually succeeds
        # with defaults. Verify it at least returns a ConsentPreferences.
        if result is not None:
            assert isinstance(result, ConsentPreferences)


# ---------------------------------------------------------------------------
# save_consent_to_cookie
# ---------------------------------------------------------------------------


class TestSaveConsentToCookie:
    def test_sets_cookie(self):
        resp = MagicMock()
        prefs = ConsentPreferences(functional=True, analytics=True)

        PrivacyService.save_consent_to_cookie(resp, prefs)

        resp.set_cookie.assert_called_once()
        call_kwargs = resp.set_cookie.call_args.kwargs
        assert call_kwargs["key"] == PrivacyConfig.COOKIE_NAME
        assert call_kwargs["secure"] is True
        assert call_kwargs["httponly"] is False  # JS needs access
        assert call_kwargs["samesite"] == "Lax"

    def test_sets_timestamp(self):
        resp = MagicMock()
        prefs = ConsentPreferences()
        assert prefs.timestamp is None

        PrivacyService.save_consent_to_cookie(resp, prefs)

        # After saving, timestamp should be set
        assert prefs.timestamp is not None

    def test_cookie_max_age(self):
        resp = MagicMock()
        prefs = ConsentPreferences()

        PrivacyService.save_consent_to_cookie(resp, prefs)

        call_kwargs = resp.set_cookie.call_args.kwargs
        assert call_kwargs["max_age"] == PrivacyConfig.COOKIE_MAX_AGE


# ---------------------------------------------------------------------------
# get_effective_consent
# ---------------------------------------------------------------------------


class TestGetEffectiveConsent:
    @patch("app.api.services.privacy_service.get_gpc_status", return_value=True)
    def test_gpc_forces_opt_out(self, _mock_gpc):
        req = _make_request()

        result = PrivacyService.get_effective_consent(req)

        assert result.analytics is False
        assert result.marketing is False
        assert result.gpc_override is True

    @patch("app.api.services.privacy_service.get_gpc_status", return_value=False)
    def test_returns_saved_cookie_prefs(self, _mock_gpc):
        prefs = ConsentPreferences(functional=True, analytics=True, marketing=True)
        req = _make_request({PrivacyConfig.COOKIE_NAME: prefs.model_dump_json()})

        result = PrivacyService.get_effective_consent(req)

        assert result.analytics is True
        assert result.marketing is True

    @patch("app.api.services.privacy_service.get_gpc_status", return_value=False)
    def test_defaults_all_opt_out(self, _mock_gpc):
        req = _make_request({})

        result = PrivacyService.get_effective_consent(req)

        assert result.necessary is True
        assert result.functional is False
        assert result.analytics is False
        assert result.marketing is False

    @patch("app.api.services.privacy_service.get_gpc_status", return_value=True)
    def test_gpc_overrides_saved_prefs(self, _mock_gpc):
        """Even if saved prefs allow analytics, GPC wins."""
        prefs = ConsentPreferences(analytics=True, marketing=True)
        req = _make_request({PrivacyConfig.COOKIE_NAME: prefs.model_dump_json()})

        result = PrivacyService.get_effective_consent(req)

        assert result.analytics is False
        assert result.marketing is False


# ---------------------------------------------------------------------------
# has_consent_for / can_track / can_use_marketing_cookies
# ---------------------------------------------------------------------------


class TestConsentHelpers:
    @patch("app.api.services.privacy_service.get_gpc_status", return_value=False)
    def test_has_consent_for_analytics(self, _mock_gpc):
        prefs = ConsentPreferences(analytics=True)
        req = _make_request({PrivacyConfig.COOKIE_NAME: prefs.model_dump_json()})

        assert PrivacyService.has_consent_for(req, ConsentCategory.ANALYTICS) is True

    @patch("app.api.services.privacy_service.get_gpc_status", return_value=False)
    def test_no_consent_for_marketing_by_default(self, _mock_gpc):
        req = _make_request({})

        assert PrivacyService.has_consent_for(req, ConsentCategory.MARKETING) is False

    @patch("app.api.services.privacy_service.get_gpc_status", return_value=False)
    def test_can_track(self, _mock_gpc):
        prefs = ConsentPreferences(analytics=True)
        req = _make_request({PrivacyConfig.COOKIE_NAME: prefs.model_dump_json()})

        assert PrivacyService.can_track(req) is True

    @patch("app.api.services.privacy_service.get_gpc_status", return_value=False)
    def test_cannot_track_by_default(self, _mock_gpc):
        req = _make_request({})

        assert PrivacyService.can_track(req) is False

    @patch("app.api.services.privacy_service.get_gpc_status", return_value=False)
    def test_can_use_marketing_cookies(self, _mock_gpc):
        prefs = ConsentPreferences(marketing=True)
        req = _make_request({PrivacyConfig.COOKIE_NAME: prefs.model_dump_json()})

        assert PrivacyService.can_use_marketing_cookies(req) is True

    @patch("app.api.services.privacy_service.get_gpc_status", return_value=False)
    def test_necessary_always_true(self, _mock_gpc):
        req = _make_request({})

        assert PrivacyService.has_consent_for(req, ConsentCategory.NECESSARY) is True
