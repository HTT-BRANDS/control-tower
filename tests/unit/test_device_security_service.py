"""Unit tests for device security service.

Tests the DeviceSecurityService and API routes for device security features.

Traces: RC-031 (EDR coverage), RC-032 (Device encryption), RC-033 (Asset inventory),
        RC-034 (Device compliance), RC-035 (Non-compliant devices)
"""

class TestDeviceSecurityService:
    """Tests for DeviceSecurityService."""

    def test_get_edr_coverage_returns_dict(self):
        """Service returns dict with expected status."""
        from app.api.services.device_security_service import DeviceSecurityService

        service = DeviceSecurityService()
        result = service.get_edr_coverage()

        assert isinstance(result, dict)
        assert result["status"] == "coming_soon"
        assert "features" in result
        assert "endpoint protection status" in result["features"]

    def test_get_edr_coverage_with_tenant_id(self):
        """Service accepts and returns tenant ID."""
        from app.api.services.device_security_service import DeviceSecurityService

        service = DeviceSecurityService()
        result = service.get_edr_coverage(tenant_id="tenant-123")

        assert result["tenant_id"] == "tenant-123"

    def test_get_device_encryption_returns_dict(self):
        """Service returns dict with expected status."""
        from app.api.services.device_security_service import DeviceSecurityService

        service = DeviceSecurityService()
        result = service.get_device_encryption()

        assert isinstance(result, dict)
        assert result["status"] == "coming_soon"
        assert "features" in result
        assert "BitLocker status" in result["features"]

    def test_get_device_encryption_with_tenant_id(self):
        """Service accepts and returns tenant ID."""
        from app.api.services.device_security_service import DeviceSecurityService

        service = DeviceSecurityService()
        result = service.get_device_encryption(tenant_id="tenant-456")

        assert result["tenant_id"] == "tenant-456"

    def test_get_asset_inventory_returns_dict(self):
        """Service returns dict with expected status."""
        from app.api.services.device_security_service import DeviceSecurityService

        service = DeviceSecurityService()
        result = service.get_asset_inventory()

        assert isinstance(result, dict)
        assert result["status"] == "coming_soon"
        assert "features" in result
        assert "device list" in result["features"]

    def test_get_asset_inventory_with_tenant_id(self):
        """Service accepts and returns tenant ID."""
        from app.api.services.device_security_service import DeviceSecurityService

        service = DeviceSecurityService()
        result = service.get_asset_inventory(tenant_id="tenant-789")

        assert result["tenant_id"] == "tenant-789"

    def test_get_device_compliance_score_returns_dict(self):
        """Service returns dict with expected status."""
        from app.api.services.device_security_service import DeviceSecurityService

        service = DeviceSecurityService()
        result = service.get_device_compliance_score()

        assert isinstance(result, dict)
        assert result["status"] == "coming_soon"
        assert "features" in result
        assert "overall score" in result["features"]

    def test_get_device_compliance_score_with_tenant_id(self):
        """Service accepts and returns tenant ID."""
        from app.api.services.device_security_service import DeviceSecurityService

        service = DeviceSecurityService()
        result = service.get_device_compliance_score(tenant_id="tenant-abc")

        assert result["tenant_id"] == "tenant-abc"

    def test_get_non_compliant_devices_returns_dict(self):
        """Service returns dict with expected status."""
        from app.api.services.device_security_service import DeviceSecurityService

        service = DeviceSecurityService()
        result = service.get_non_compliant_devices()

        assert isinstance(result, dict)
        assert result["status"] == "coming_soon"
        assert "features" in result
        assert "alert list" in result["features"]

    def test_get_non_compliant_devices_with_tenant_id(self):
        """Service accepts and returns tenant ID."""
        from app.api.services.device_security_service import DeviceSecurityService

        service = DeviceSecurityService()
        result = service.get_non_compliant_devices(tenant_id="tenant-xyz")

        assert result["tenant_id"] == "tenant-xyz"

    def test_get_device_security_service_singleton(self):
        """get_device_security_service returns singleton instance."""
        from app.api.services.device_security_service import (
            DeviceSecurityService,
            get_device_security_service,
        )

        service1 = get_device_security_service()
        service2 = get_device_security_service()

        assert isinstance(service1, DeviceSecurityService)
        assert service1 is service2


class TestDeviceSecurityRoutes:
    """Tests for Device Security API routes."""

    def test_edr_coverage_route_returns_200(self, authed_client):
        """EDR coverage endpoint returns 200 with valid auth."""
        response = authed_client.get("/api/v1/device-security/edr-coverage")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "coming_soon"

    def test_edr_coverage_route_with_tenant_param(self, authed_client):
        """EDR coverage endpoint accepts tenant_id parameter."""
        response = authed_client.get(
            "/api/v1/device-security/edr-coverage?tenant_id=test-tenant"
        )

        assert response.status_code == 200

    def test_encryption_route_returns_200(self, authed_client):
        """Encryption endpoint returns 200 with valid auth."""
        response = authed_client.get("/api/v1/device-security/encryption")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "coming_soon"

    def test_encryption_route_with_tenant_param(self, authed_client):
        """Encryption endpoint accepts tenant_id parameter."""
        response = authed_client.get(
            "/api/v1/device-security/encryption?tenant_id=test-tenant"
        )

        assert response.status_code == 200

    def test_inventory_route_returns_200(self, authed_client):
        """Inventory endpoint returns 200 with valid auth."""
        response = authed_client.get("/api/v1/device-security/inventory")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "coming_soon"

    def test_inventory_route_with_tenant_param(self, authed_client):
        """Inventory endpoint accepts tenant_id parameter."""
        response = authed_client.get(
            "/api/v1/device-security/inventory?tenant_id=test-tenant"
        )

        assert response.status_code == 200

    def test_compliance_score_route_returns_200(self, authed_client):
        """Compliance score endpoint returns 200 with valid auth."""
        response = authed_client.get("/api/v1/device-security/compliance-score")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "coming_soon"

    def test_compliance_score_route_with_tenant_param(self, authed_client):
        """Compliance score endpoint accepts tenant_id parameter."""
        response = authed_client.get(
            "/api/v1/device-security/compliance-score?tenant_id=test-tenant"
        )

        assert response.status_code == 200

    def test_non_compliant_route_returns_200(self, authed_client):
        """Non-compliant endpoint returns 200 with valid auth."""
        response = authed_client.get("/api/v1/device-security/non-compliant")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "coming_soon"

    def test_non_compliant_route_with_tenant_param(self, authed_client):
        """Non-compliant endpoint accepts tenant_id parameter."""
        response = authed_client.get(
            "/api/v1/device-security/non-compliant?tenant_id=test-tenant"
        )

        assert response.status_code == 200

    def test_routes_require_auth(self, client):
        """All device security endpoints return 401 without auth."""
        endpoints = [
            "/api/v1/device-security/edr-coverage",
            "/api/v1/device-security/encryption",
            "/api/v1/device-security/inventory",
            "/api/v1/device-security/compliance-score",
            "/api/v1/device-security/non-compliant",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401, f"Expected 401 for {endpoint}"
