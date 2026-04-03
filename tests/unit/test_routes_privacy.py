"""Unit tests for privacy consent API routes.

Tests all privacy/consent endpoints with FastAPI TestClient:
- GET  /api/v1/privacy/consent/categories
- GET  /api/v1/privacy/consent/preferences
- POST /api/v1/privacy/consent/preferences
- POST /api/v1/privacy/consent/accept-all
- POST /api/v1/privacy/consent/reject-all
- GET  /api/v1/privacy/consent/status

These endpoints do NOT require authentication — all tests use the
unauthenticated `client` fixture.
"""

from unittest.mock import patch

from app.core.privacy_config import ConsentPreferences, PrivacyConfig

PREFIX = "/api/v1/privacy"


# ============================================================================
# GET /consent/categories
# ============================================================================


class TestConsentCategoriesEndpoint:
    """Tests for GET /api/v1/privacy/consent/categories."""

    def test_get_categories_returns_list(self, client):
        """Categories endpoint returns all consent categories."""
        response = client.get(f"{PREFIX}/consent/categories")

        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert "cookie_name" in data
        assert data["cookie_name"] == PrivacyConfig.COOKIE_NAME
        assert data["version"] == "1.0"

    def test_get_categories_no_auth_required(self, client):
        """Categories endpoint is accessible without authentication."""
        response = client.get(f"{PREFIX}/consent/categories")
        # Should NOT be 401/403 — privacy endpoints are public
        assert response.status_code == 200


# ============================================================================
# GET /consent/preferences
# ============================================================================


class TestConsentPreferencesGetEndpoint:
    """Tests for GET /api/v1/privacy/consent/preferences."""

    @patch("app.api.routes.privacy.PrivacyService")
    def test_get_preferences_returns_defaults(self, mock_service, client):
        """Preferences endpoint returns default opt-out preferences."""
        mock_service.get_effective_consent.return_value = ConsentPreferences()

        response = client.get(f"{PREFIX}/consent/preferences")

        assert response.status_code == 200
        data = response.json()
        assert data["necessary"] is True
        assert data["functional"] is False
        assert data["analytics"] is False
        assert data["marketing"] is False


# ============================================================================
# POST /consent/preferences
# ============================================================================


class TestConsentPreferencesPostEndpoint:
    """Tests for POST /api/v1/privacy/consent/preferences."""

    @patch("app.api.routes.privacy.PrivacyService")
    def test_save_preferences_valid_body(self, mock_service, client):
        """Saving preferences with valid body returns saved status."""
        body = {
            "necessary": True,
            "functional": True,
            "analytics": False,
            "marketing": False,
        }

        response = client.post(f"{PREFIX}/consent/preferences", json=body)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "saved"
        assert data["preferences"]["functional"] is True
        assert data["preferences"]["analytics"] is False

    @patch("app.api.routes.privacy.PrivacyService")
    def test_save_preferences_forces_necessary_true(self, mock_service, client):
        """Necessary category is always forced to True even if client sends False."""
        body = {
            "necessary": False,  # Client tries to disable necessary
            "functional": False,
            "analytics": False,
            "marketing": False,
        }

        response = client.post(f"{PREFIX}/consent/preferences", json=body)

        assert response.status_code == 200
        data = response.json()
        assert data["preferences"]["necessary"] is True


# ============================================================================
# POST /consent/accept-all
# ============================================================================


class TestAcceptAllEndpoint:
    """Tests for POST /api/v1/privacy/consent/accept-all."""

    @patch("app.api.routes.privacy.PrivacyService")
    def test_accept_all_enables_everything(self, mock_service, client):
        """Accept-all endpoint sets all categories to True."""
        response = client.post(f"{PREFIX}/consent/accept-all")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted_all"
        prefs = data["preferences"]
        assert prefs["necessary"] is True
        assert prefs["functional"] is True
        assert prefs["analytics"] is True
        assert prefs["marketing"] is True


# ============================================================================
# POST /consent/reject-all
# ============================================================================


class TestRejectAllEndpoint:
    """Tests for POST /api/v1/privacy/consent/reject-all."""

    @patch("app.api.routes.privacy.PrivacyService")
    def test_reject_all_keeps_only_necessary(self, mock_service, client):
        """Reject-all endpoint disables all except necessary."""
        response = client.post(f"{PREFIX}/consent/reject-all")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected_non_essential"
        prefs = data["preferences"]
        assert prefs["necessary"] is True
        assert prefs["functional"] is False
        assert prefs["analytics"] is False
        assert prefs["marketing"] is False


# ============================================================================
# GET /consent/status
# ============================================================================


class TestConsentStatusEndpoint:
    """Tests for GET /api/v1/privacy/consent/status."""

    @patch("app.api.routes.privacy.PrivacyService")
    def test_status_returns_consent_state(self, mock_service, client):
        """Status endpoint returns structured consent state."""
        mock_service.get_effective_consent.return_value = ConsentPreferences(
            necessary=True,
            functional=True,
            analytics=False,
            marketing=False,
        )

        response = client.get(f"{PREFIX}/consent/status")

        assert response.status_code == 200
        data = response.json()
        assert "has_consented" in data
        assert "gpc_override" in data
        assert "categories" in data
        assert data["categories"]["necessary"] is True
        assert data["categories"]["functional"] is True
        assert data["categories"]["analytics"] is False
        assert data["categories"]["marketing"] is False

    @patch("app.api.routes.privacy.PrivacyService")
    def test_status_no_prior_consent(self, mock_service, client):
        """Status endpoint indicates no prior consent when timestamp is None."""
        mock_service.get_effective_consent.return_value = ConsentPreferences()

        response = client.get(f"{PREFIX}/consent/status")

        assert response.status_code == 200
        data = response.json()
        assert data["has_consented"] is False
        assert data["gpc_override"] is False
