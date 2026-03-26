"""
Tests for Global Privacy Control (GPC) middleware.
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from app.core.gpc_middleware import GPCMiddleware, get_gpc_status, GPCConsentManager


class TestGPCMiddleware:
    """Test GPC signal detection and handling."""
    
    def setup_method(self):
        """Create test app with GPC middleware."""
        self.app = FastAPI()
        self.app.add_middleware(GPCMiddleware, log_all_requests=True)
        
        @self.app.get("/test")
        async def test_route(request: Request):
            return {
                "gpc_enabled": get_gpc_status(request),
                "path": str(request.url.path)
            }
        
        self.client = TestClient(self.app)
    
    def test_gpc_header_detected(self):
        """GPC signal (Sec-GPC:1) is correctly detected."""
        response = self.client.get("/test", headers={"Sec-GPC": "1"})
        
        assert response.status_code == 200
        assert response.json()["gpc_enabled"] is True
        assert response.headers["X-GPC-Detected"] == "1"
    
    def test_gpc_header_not_present(self):
        """When GPC header absent, gpc_enabled is False."""
        response = self.client.get("/test")
        
        assert response.status_code == 200
        assert response.json()["gpc_enabled"] is False
        assert response.headers["X-GPC-Detected"] == "0"
    
    def test_gpc_header_zero(self):
        """GPC header value 0 means not enabled."""
        response = self.client.get("/test", headers={"Sec-GPC": "0"})
        
        assert response.status_code == 200
        assert response.json()["gpc_enabled"] is False
    
    def test_gpc_permissions_policy_header(self):
        """When GPC enabled, Permissions-Policy header is restrictive."""
        response = self.client.get("/test", headers={"Sec-GPC": "1"})
        
        assert "Permissions-Policy" in response.headers
        policy = response.headers["Permissions-Policy"]
        assert "interest-cohort=()" in policy  # No FLoC
        assert "geolocation=()" in policy
    
    def test_gpc_no_permissions_policy_when_disabled(self):
        """When GPC not enabled, no restrictive Permissions-Policy added."""
        response = self.client.get("/test", headers={"Sec-GPC": "0"})
        
        # Header may or may not be present, but shouldn't have restrictive values
        if "Permissions-Policy" in response.headers:
            assert "interest-cohort=()" not in response.headers["Permissions-Policy"]


class TestGPCConsentManager:
    """Test GPC consent management."""
    
    def test_gpc_consent_categories(self):
        """GPC users are opted out of analytics and marketing by default."""
        consent = GPCConsentManager.get_consent_for_gpc_user()
        
        assert consent["analytics"] is False
        assert consent["marketing"] is False
        assert consent["functional"] is True
        assert consent["necessary"] is True
    
    def test_should_track_with_gpc_enabled(self):
        """When GPC enabled, should_track returns False."""
        assert GPCConsentManager.should_track(gpc_enabled=True) is False
    
    def test_should_track_with_gpc_disabled(self):
        """When GPC disabled, should_track returns True."""
        assert GPCConsentManager.should_track(gpc_enabled=False) is True
    
    def test_should_share_data_with_gpc_enabled(self):
        """When GPC enabled, should_share_data returns False."""
        assert GPCConsentManager.should_share_data(gpc_enabled=True) is False
    
    def test_should_share_data_with_gpc_disabled(self):
        """When GPC disabled, should_share_data returns True."""
        assert GPCConsentManager.should_share_data(gpc_enabled=False) is True


class TestGPCLogging:
    """Test GPC event logging."""
    
    def test_gpc_detection_logged(self, caplog):
        """GPC detection is logged for audit trail."""
        import logging
        
        app = FastAPI()
        app.add_middleware(GPCMiddleware)
        
        @app.get("/")
        async def root(request: Request):
            return {"ok": True}
        
        client = TestClient(app)
        
        with caplog.at_level(logging.INFO):
            client.get("/", headers={"Sec-GPC": "1"})
        
        # Should have logged GPC detection
        gpc_logs = [r for r in caplog.records if "GPC" in r.message]
        assert len(gpc_logs) > 0
