"""
Tests for Privacy Service and Consent Management
"""

import json
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.core.privacy_config import ConsentPreferences, ConsentCategory, PrivacyConfig
from app.api.services.privacy_service import PrivacyService
from app.api.routes.privacy import router as privacy_router


class TestConsentPreferences:
    """Test ConsentPreferences model."""
    
    def test_default_values(self):
        """Default consent is opt-out except necessary."""
        prefs = ConsentPreferences()
        
        assert prefs.necessary is True
        assert prefs.functional is False
        assert prefs.analytics is False
        assert prefs.marketing is False
        assert prefs.gpc_override is False
        assert prefs.version == "1.0"
    
    def test_custom_values(self):
        """Can set custom consent values."""
        prefs = ConsentPreferences(
            necessary=True,
            functional=True,
            analytics=True,
            marketing=False
        )
        
        assert prefs.necessary is True
        assert prefs.functional is True
        assert prefs.analytics is True
        assert prefs.marketing is False
    
    def test_model_dump(self):
        """Model can be serialized to dict."""
        prefs = ConsentPreferences(functional=True)
        data = prefs.model_dump()
        
        assert data["necessary"] is True
        assert data["functional"] is True
        assert data["analytics"] is False
        assert "timestamp" in data


class TestPrivacyConfig:
    """Test PrivacyConfig static methods."""
    
    def test_get_categories(self):
        """Returns all consent categories."""
        categories = PrivacyConfig.get_categories()
        
        assert ConsentCategory.NECESSARY in categories
        assert ConsentCategory.FUNCTIONAL in categories
        assert ConsentCategory.ANALYTICS in categories
        assert ConsentCategory.MARKETING in categories
        
        # Check structure
        necessary = categories[ConsentCategory.NECESSARY]
        assert necessary["name"] == "Necessary"
        assert necessary["required"] is True
    
    def test_apply_gpc_override(self):
        """GPC override opts out of analytics and marketing."""
        prefs = ConsentPreferences(
            functional=True,
            analytics=True,
            marketing=True
        )
        
        result = PrivacyConfig.apply_gpc_override(prefs)
        
        assert result.analytics is False
        assert result.marketing is False
        assert result.gpc_override is True
        assert result.functional is True  # Unchanged


class TestPrivacyService:
    """Test PrivacyService methods."""
    
    def test_get_consent_from_cookie_valid(self):
        """Parses valid consent cookie."""
        prefs = ConsentPreferences(functional=True)
        cookie_value = prefs.model_dump_json()
        
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {"consent_preferences": cookie_value}
        
        result = PrivacyService.get_consent_from_cookie(mock_request)
        
        assert result is not None
        assert result.functional is True
    
    def test_get_consent_from_cookie_missing(self):
        """Returns None when cookie missing."""
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {}
        
        result = PrivacyService.get_consent_from_cookie(mock_request)
        
        assert result is None
    
    def test_get_consent_from_cookie_invalid(self):
        """Returns None when cookie invalid."""
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {"consent_preferences": "invalid json"}
        
        result = PrivacyService.get_consent_from_cookie(mock_request)
        
        assert result is None
    
    def test_save_consent_to_cookie(self):
        """Saves consent to cookie with timestamp."""
        prefs = ConsentPreferences(analytics=True)
        mock_response = MagicMock()
        
        PrivacyService.save_consent_to_cookie(mock_response, prefs)
        
        # Check set_cookie was called
        assert mock_response.set_cookie.called
        call_args = mock_response.set_cookie.call_args
        
        assert call_args.kwargs["key"] == "consent_preferences"
        assert call_args.kwargs["secure"] is True
        assert call_args.kwargs["samesite"] == "Lax"
        
        # Check timestamp was added
        saved_data = json.loads(call_args.kwargs["value"])
        assert "timestamp" in saved_data
        assert saved_data["analytics"] is True
    
    def test_get_effective_consent_defaults(self):
        """Returns defaults when no cookie and no GPC."""
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {}
        mock_request.state = MagicMock()
        mock_request.state.gpc_enabled = False
        
        result = PrivacyService.get_effective_consent(mock_request)
        
        assert result.necessary is True
        assert result.analytics is False
        assert result.gpc_override is False
    
    def test_get_effective_consent_from_cookie(self):
        """Returns saved preferences when cookie exists."""
        prefs = ConsentPreferences(analytics=True, marketing=True)
        
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {"consent_preferences": prefs.model_dump_json()}
        mock_request.state = MagicMock()
        mock_request.state.gpc_enabled = False
        
        result = PrivacyService.get_effective_consent(mock_request)
        
        assert result.analytics is True
        assert result.marketing is True
    
    def test_get_effective_consent_gpc_override(self):
        """GPC signal overrides saved preferences."""
        prefs = ConsentPreferences(analytics=True, marketing=True)
        
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {"consent_preferences": prefs.model_dump_json()}
        mock_request.state = MagicMock()
        mock_request.state.gpc_enabled = True
        
        result = PrivacyService.get_effective_consent(mock_request)
        
        assert result.analytics is False  # GPC override
        assert result.marketing is False  # GPC override
        assert result.gpc_override is True
    
    def test_has_consent_for_true(self):
        """Returns True when consent granted."""
        prefs = ConsentPreferences(analytics=True)
        
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {"consent_preferences": prefs.model_dump_json()}
        mock_request.state = MagicMock()
        mock_request.state.gpc_enabled = False
        
        result = PrivacyService.has_consent_for(mock_request, ConsentCategory.ANALYTICS)
        
        assert result is True
    
    def test_has_consent_for_false(self):
        """Returns False when consent not granted."""
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {}
        mock_request.state = MagicMock()
        mock_request.state.gpc_enabled = False
        
        result = PrivacyService.has_consent_for(mock_request, ConsentCategory.MARKETING)
        
        assert result is False
    
    def test_can_track_true(self):
        """Returns True when tracking allowed."""
        prefs = ConsentPreferences(analytics=True)
        
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {"consent_preferences": prefs.model_dump_json()}
        mock_request.state = MagicMock()
        mock_request.state.gpc_enabled = False
        
        assert PrivacyService.can_track(mock_request) is True
    
    def test_can_track_false(self):
        """Returns False when tracking not allowed."""
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {}
        mock_request.state = MagicMock()
        mock_request.state.gpc_enabled = False
        
        assert PrivacyService.can_track(mock_request) is False


class TestPrivacyRoutes:
    """Test privacy API routes."""
    
    def setup_method(self):
        """Create test app with privacy routes."""
        self.app = FastAPI()
        self.app.include_router(privacy_router)
        self.client = TestClient(self.app)
    
    def test_get_consent_categories(self):
        """Returns all consent categories."""
        response = self.client.get("/api/v1/privacy/consent/categories")
        
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert "cookie_name" in data
    
    def test_get_consent_preferences_default(self):
        """Returns default preferences."""
        response = self.client.get("/api/v1/privacy/consent/preferences")
        
        assert response.status_code == 200
        data = response.json()
        assert data["necessary"] is True
        assert data["analytics"] is False
    
    def test_save_consent_preferences(self):
        """Saves custom preferences."""
        response = self.client.post(
            "/api/v1/privacy/consent/preferences",
            json={"necessary": True, "functional": True, "analytics": False}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "saved"
        assert data["preferences"]["functional"] is True
        
        # Check cookie was set
        assert "consent_preferences" in response.cookies
    
    def test_save_consent_ensures_necessary(self):
        """Necessary cookies always True even if sent as False."""
        response = self.client.post(
            "/api/v1/privacy/consent/preferences",
            json={"necessary": False, "analytics": True}
        )
        
        data = response.json()
        assert data["preferences"]["necessary"] is True  # Forced to True
    
    def test_accept_all_cookies(self):
        """Accept all sets all categories to True."""
        response = self.client.post("/api/v1/privacy/consent/accept-all")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted_all"
        assert data["preferences"]["analytics"] is True
        assert data["preferences"]["marketing"] is True
    
    def test_reject_all_cookies(self):
        """Reject all sets non-essential to False."""
        response = self.client.post("/api/v1/privacy/consent/reject-all")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected_non_essential"
        assert data["preferences"]["necessary"] is True
        assert data["preferences"]["analytics"] is False
        assert data["preferences"]["marketing"] is False
    
    def test_get_consent_status_no_cookie(self):
        """Status shows no consent when cookie missing."""
        response = self.client.get("/api/v1/privacy/consent/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["has_consented"] is False
        assert data["gpc_override"] is False
    
    def test_get_consent_status_with_explicit_cookie(self):
        """Status shows consent when cookie explicitly provided."""
        # Create a consent cookie manually
        prefs = ConsentPreferences(
            necessary=True,
            functional=True,
            analytics=True,
            marketing=True,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        # Set cookie manually on client
        self.client.cookies.set("consent_preferences", prefs.model_dump_json())
        
        # Check status
        response = self.client.get("/api/v1/privacy/consent/status")
        
        data = response.json()
        assert data["has_consented"] is True
        assert data["categories"]["analytics"] is True
