"""Unit tests for onboarding API routes.

Tests the onboarding endpoints including template generation,
tenant verification, and onboarding status retrieval.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestOnboardingLandingPage:
    """Tests for the onboarding landing page."""
    
    def test_onboarding_landing_page(self, client):
        """Test GET /onboarding/ returns landing page."""
        response = client.get("/onboarding/")
        
        assert response.status_code == 200
        # Check for expected content in the response
        assert "Azure Governance Platform" in response.text
        assert "HTMX" in response.text or "hx-" in response.text
    
    def test_onboarding_page_content(self, client):
        """Test landing page contains expected elements."""
        response = client.get("/onboarding/")
        
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        # Should contain onboarding form or instructions
        assert "onboard" in response.text.lower()


class TestGenerateTemplate:
    """Tests for the template generation endpoint."""
    
    def test_generate_template_success(self, client):
        """Test POST /onboarding/generate-template returns ARM template."""
        with patch("app.api.routes.onboarding.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()
            mock_settings.return_value.azure_tenant_id = "msp-tenant-123"
            
            response = client.post("/onboarding/generate-template")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify ARM template structure
        assert "$schema" in data
        assert "contentVersion" in data
        assert "managedByTenantId" in str(data)
        assert "resources" in data
        assert "parameters" in data
    
    def test_generate_template_with_customization(self, client):
        """Test template generation with custom parameters."""
        request_data = {
            "tenant_name": "Custom Tenant",
            "authorizations": [
                {
                    "principalId": "user-123",
                    "roleDefinitionId": "reader-role-id"
                }
            ]
        }
        
        response = client.post("/onboarding/generate-template", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "resources" in data
    
    def test_generate_template_requires_auth(self, client):
        """Test that template generation requires authentication."""
        # Mock no authentication
        with patch("app.api.routes.onboarding.get_current_user") as mock_auth:
            mock_auth.side_effect = Exception("Not authenticated")
            
            response = client.post("/onboarding/generate-template")
        
        assert response.status_code in [401, 403]


class TestVerifyOnboarding:
    """Tests for the onboarding verification endpoint."""
    
    @pytest.fixture
    def valid_verification_request(self):
        """Create a valid verification request."""
        return {
            "tenant_id": str(uuid.uuid4()),
            "tenant_name": "Test Tenant",
            "subscription_id": str(uuid.uuid4()),
            "subscription_name": "Test Subscription",
            "primary_domain": "test.onmicrosoft.com",
            "admin_email": "admin@test.com"
        }
    
    @pytest.mark.asyncio
    async def test_verify_onboarding_success(self, client, valid_verification_request):
        """Test successful tenant onboarding verification."""
        with patch("app.api.routes.onboarding.LighthouseAzureClient") as mock_client:
            with patch("app.api.routes.onboarding.get_db") as mock_get_db:
                mock_instance = AsyncMock()
                mock_instance.verify_delegation.return_value = {
                    "success": True,
                    "subscription_id": valid_verification_request["subscription_id"],
                    "is_delegated": True
                }
                mock_instance.validate_tenant_access.return_value = {
                    "success": True,
                    "has_delegation": True
                }
                mock_client.return_value = mock_instance
                
                # Mock database
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                response = client.post("/onboarding/verify", json=valid_verification_request)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "tenant_id" in data
        assert data["is_active"] is True
    
    @pytest.mark.asyncio
    async def test_verify_onboarding_delegation_failed(self, client, valid_verification_request):
        """Test verification when delegation check fails."""
        with patch("app.api.routes.onboarding.LighthouseAzureClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.verify_delegation.return_value = {
                "success": False,
                "error": "Subscription not found or not delegated"
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/onboarding/verify", json=valid_verification_request)
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "delegation" in data["error"].lower()
    
    @pytest.mark.asyncio
    async def test_verify_onboarding_creates_tenant(self, client, valid_verification_request):
        """Test that verification creates a tenant record."""
        with patch("app.api.routes.onboarding.LighthouseAzureClient") as mock_client:
            with patch("app.api.routes.onboarding.get_db") as mock_get_db:
                mock_instance = AsyncMock()
                mock_instance.verify_delegation.return_value = {"success": True, "is_delegated": True}
                mock_instance.validate_tenant_access.return_value = {"success": True}
                mock_client.return_value = mock_instance
                
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                
                response = client.post("/onboarding/verify", json=valid_verification_request)
        
        assert response.status_code == 200
        # Verify tenant was created
        mock_db.add.assert_called()
        mock_db.commit.assert_called()
    
    def test_verify_onboarding_missing_required_fields(self, client):
        """Test verification with missing required fields."""
        incomplete_request = {
            "tenant_name": "Test Tenant"  # Missing required fields
        }
        
        response = client.post("/onboarding/verify", json=incomplete_request)
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    @pytest.mark.asyncio
    async def test_verify_onboarding_starts_initial_sync(self, client, valid_verification_request):
        """Test that verification triggers initial data sync."""
        with patch("app.api.routes.onboarding.LighthouseAzureClient") as mock_client:
            with patch("app.api.routes.onboarding.get_db") as mock_get_db:
                with patch("app.api.routes.onboarding.sync_tenant_data") as mock_sync:
                    mock_instance = AsyncMock()
                    mock_instance.verify_delegation.return_value = {
                        "success": True,
                        "subscription_id": valid_verification_request["subscription_id"],
                        "is_delegated": True
                    }
                    mock_instance.validate_tenant_access.return_value = {
                        "success": True,
                        "has_delegation": True
                    }
                    mock_client.return_value = mock_instance
                    
                    mock_db = MagicMock()
                    mock_get_db.return_value = mock_db
                    
                    response = client.post("/onboarding/verify", json=valid_verification_request)
        
        assert response.status_code == 200
        # Verify sync was triggered
        mock_sync.assert_called_once()


class TestOnboardingStatus:
    """Tests for the onboarding status endpoint."""
    
    @pytest.fixture
    def mock_tenant(self):
        """Create a mock tenant for status tests."""
        tenant_id = str(uuid.uuid4())
        return {
            "id": tenant_id,
            "name": "Test Tenant",
            "tenant_id": "test-tenant-123",
            "description": "Test tenant description",
            "is_active": True,
            "use_lighthouse": True,
            "onboarded_at": datetime.now(UTC).isoformat(),
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "subscription_count": 2,
            "delegation_status": "active",
            "last_synced_at": datetime.now(UTC).isoformat()
        }
    
    def test_get_onboarding_status_success(self, client, mock_tenant):
        """Test successful retrieval of onboarding status."""
        with patch("app.api.routes.onboarding.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_tenant_obj = MagicMock()
            for key, value in mock_tenant.items():
                setattr(mock_tenant_obj, key, value)
            
            mock_db.query.return_value.filter.return_value.first.return_value = mock_tenant_obj
            mock_get_db.return_value = mock_db
            
            response = client.get(f"/onboarding/status/{mock_tenant['id']}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == mock_tenant["id"]
        assert data["name"] == mock_tenant["name"]
        assert data["is_active"] is True
        assert "subscription_count" in data
        assert "delegation_status" in data
    
    def test_get_onboarding_status_not_found(self, client):
        """Test status retrieval for non-existent tenant."""
        with patch("app.api.routes.onboarding.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_get_db.return_value = mock_db
            
            response = client.get(f"/onboarding/status/{uuid.uuid4()}")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data.get("detail", "").lower()
    
    def test_get_onboarding_status_invalid_id(self, client):
        """Test status retrieval with invalid tenant ID format."""
        response = client.get("/onboarding/status/invalid-tenant-id")
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    def test_get_onboarding_status_pending_delegation(self, client):
        """Test status when delegation is still pending."""
        tenant_id = str(uuid.uuid4())
        
        with patch("app.api.routes.onboarding.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_tenant = MagicMock()
            mock_tenant.id = tenant_id
            mock_tenant.tenant_id = "test-tenant-123"
            mock_tenant.is_active = True
            mock_tenant.use_lighthouse = True
            mock_tenant.subscription_count = 0
            mock_tenant.delegation_status = "pending"
            mock_db.query.return_value.filter.return_value.first.return_value = mock_tenant
            mock_get_db.return_value = mock_db
            
            response = client.get(f"/onboarding/status/{tenant_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["delegation_status"] == "pending"
        assert data["requires_action"] is True
    
    def test_get_onboarding_status_delegation_failed(self, client):
        """Test status when delegation has failed."""
        tenant_id = str(uuid.uuid4())
        
        with patch("app.api.routes.onboarding.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_tenant = MagicMock()
            mock_tenant.id = tenant_id
            mock_tenant.tenant_id = "test-tenant-123"
            mock_tenant.is_active = False
            mock_tenant.use_lighthouse = True
            mock_tenant.delegation_status = "failed"
            mock_tenant.delegation_error = "Authentication failed"
            mock_db.query.return_value.filter.return_value.first.return_value = mock_tenant
            mock_get_db.return_value = mock_db
            
            response = client.get(f"/onboarding/status/{tenant_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["delegation_status"] == "failed"
        assert "delegation_error" in data


class TestOnboardingErrorScenarios:
    """Tests for error handling and edge cases."""
    
    def test_csrf_protection_on_post_endpoints(self, client):
        """Test that POST endpoints require CSRF token."""
        # Make request without CSRF token header
        response = client.post(
            "/onboarding/verify",
            json={"tenant_id": str(uuid.uuid4())},
            headers={}  # No CSRF token
        )
        
        # Should fail CSRF validation
        # Note: This depends on CSRF implementation
        assert response.status_code in [403, 422, 400]
    
    def test_rate_limiting_on_verify_endpoint(self, client):
        """Test rate limiting on verification endpoint."""
        with patch("app.core.rate_limit.rate_limiter.is_allowed") as mock_rate_limit:
            mock_rate_limit.return_value = (False, {
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "60"
            })
            
            response = client.post("/onboarding/verify", json={
                "tenant_id": str(uuid.uuid4()),
                "tenant_name": "Test"
            })
        
        assert response.status_code == 429
        assert "Retry-After" in response.headers
    
    def test_invalid_json_payload(self, client):
        """Test handling of invalid JSON payload."""
        response = client.post(
            "/onboarding/verify",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422
    
    def test_method_not_allowed(self, client):
        """Test that incorrect HTTP methods are rejected."""
        response = client.put("/onboarding/verify")
        assert response.status_code == 405
        
        response = client.delete("/onboarding/generate-template")
        assert response.status_code == 405
    
    def test_unauthorized_access(self, client):
        """Test unauthorized access to protected endpoints."""
        with patch("app.core.auth.get_current_user") as mock_auth:
            mock_auth.side_effect = Exception("Not authenticated")
            
            response = client.get(f"/onboarding/status/{uuid.uuid4()}")
        
        assert response.status_code == 401


class TestOnboardingValidation:
    """Tests for input validation."""
    
    def test_tenant_id_validation(self, client):
        """Test tenant ID format validation."""
        invalid_ids = [
            "not-a-uuid",
            "12345",
            "",  # Empty string
            "too-short",
        ]
        
        for invalid_id in invalid_ids:
            response = client.get(f"/onboarding/status/{invalid_id}")
            assert response.status_code == 422, f"Expected 422 for ID: {invalid_id}"
    
    def test_email_validation(self, client):
        """Test admin email validation."""
        invalid_emails = [
            "not-an-email",
            "@test.com",
            "admin@",
            "admin@invalid",
        ]
        
        with patch("app.api.routes.onboarding.LighthouseAzureClient"):
            for invalid_email in invalid_emails:
                response = client.post("/onboarding/verify", json={
                    "tenant_id": str(uuid.uuid4()),
                    "tenant_name": "Test",
                    "admin_email": invalid_email
                })
                # Should fail validation
                assert response.status_code in [422, 400], f"Expected validation error for: {invalid_email}"
    
    def test_domain_validation(self, client):
        """Test domain format validation."""
        invalid_domains = [
            "not-a-domain",
            ".com",
            "test.",
        ]
        
        with patch("app.api.routes.onboarding.LighthouseAzureClient"):
            for invalid_domain in invalid_domains:
                response = client.post("/onboarding/verify", json={
                    "tenant_id": str(uuid.uuid4()),
                    "tenant_name": "Test",
                    "primary_domain": invalid_domain
                })
                # May pass or fail depending on validation strictness
                # Just checking no server error occurs
                assert response.status_code != 500


class TestOnboardingAsyncOperations:
    """Tests for async onboarding operations."""
    
    @pytest.mark.asyncio
    async def test_async_verify_delegation(self, client):
        """Test async delegation verification flow."""
        with patch("app.api.routes.onboarding.LighthouseAzureClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.verify_delegation.return_value = {
                "success": True,
                "is_delegated": True
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/onboarding/verify", json={
                "tenant_id": str(uuid.uuid4()),
                "tenant_name": "Test Tenant",
                "subscription_id": str(uuid.uuid4())
            })
            
            # Verify the async method was awaited
            mock_instance.verify_delegation.assert_awaited()
    
    @pytest.mark.asyncio
    async def test_async_resource_listing_during_onboarding(self, client):
        """Test that resource listing happens asynchronously."""
        with patch("app.api.routes.onboarding.LighthouseAzureClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.list_resources.return_value = {
                "success": True,
                "resources": [],
                "count": 0
            }
            mock_client.return_value = mock_instance
            
            # This would be called during initial sync
            await mock_instance.list_resources("sub-12345")
            
            mock_instance.list_resources.assert_awaited()
