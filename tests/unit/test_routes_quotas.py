"""Unit tests for quota utilization API routes.

Tests all quota endpoints with FastAPI TestClient:
- GET /api/v1/resources/quotas (compute provider)
- GET /api/v1/resources/quotas (network provider)
- GET /api/v1/resources/quotas with subscription_id filter
- GET /api/v1/resources/quotas/summary
- Authentication required
- Error handling when lighthouse client fails
"""

from unittest.mock import MagicMock, patch

import pytest

from app.api.services.quota_service import QuotaItem, QuotaSummary

# ---------------------------------------------------------------------------
# Helpers — reusable mock data builders
# ---------------------------------------------------------------------------

_MOCK_PATCH_LIGHTHOUSE = "app.services.lighthouse_client.get_lighthouse_client"
_MOCK_PATCH_QUOTA_SVC = "app.api.routes.quotas.QuotaService"


def _make_compute_summary(
    sub_id: str = "00000000-0000-0000-0000-000000000000",
    tenant_id: str = "all",
    location: str = "eastus",
) -> QuotaSummary:
    """Build a realistic compute QuotaSummary for testing."""
    return QuotaSummary(
        subscription_id=sub_id,
        tenant_id=tenant_id,
        location=location,
        quotas=[
            QuotaItem(
                name="Total Regional vCPUs",
                current_value=40,
                limit=100,
                unit="Count",
                provider="compute",
                location=location,
            ),
            QuotaItem(
                name="Standard DSv3 Family vCPUs",
                current_value=16,
                limit=100,
                unit="Count",
                provider="compute",
                location=location,
            ),
        ],
    )


def _make_network_summary(
    sub_id: str = "00000000-0000-0000-0000-000000000000",
    tenant_id: str = "all",
    location: str = "eastus",
) -> QuotaSummary:
    """Build a realistic network QuotaSummary for testing."""
    return QuotaSummary(
        subscription_id=sub_id,
        tenant_id=tenant_id,
        location=location,
        quotas=[
            QuotaItem(
                name="Virtual Networks",
                current_value=8,
                limit=50,
                unit="Count",
                provider="network",
                location=location,
            ),
            QuotaItem(
                name="Network Security Groups",
                current_value=12,
                limit=100,
                unit="Count",
                provider="network",
                location=location,
            ),
        ],
    )


def _mock_lighthouse_client() -> MagicMock:
    """Return a MagicMock that mimics LighthouseAzureClient."""
    client = MagicMock()
    client.credential = MagicMock()
    return client


# ============================================================================
# GET /api/v1/resources/quotas Tests
# ============================================================================


class TestGetQuotaUtilization:
    """Tests for GET /api/v1/resources/quotas endpoint."""

    @patch(_MOCK_PATCH_QUOTA_SVC)
    @patch(_MOCK_PATCH_LIGHTHOUSE)
    def test_get_quotas_compute_provider(self, mock_get_client, mock_svc_cls, authed_client):
        """Returns compute quota data with default parameters."""
        mock_get_client.return_value = _mock_lighthouse_client()
        mock_svc = MagicMock()
        summary = _make_compute_summary()
        mock_svc.get_compute_quotas.return_value = summary
        mock_svc_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/resources/quotas?provider=compute")

        assert response.status_code == 200
        data = response.json()
        assert data["overall_status"] == "ok"
        assert data["subscription_id"] == "00000000-0000-0000-0000-000000000000"
        assert data["location"] == "eastus"
        assert len(data["quotas"]) == 2
        assert data["quotas"][0]["name"] == "Total Regional vCPUs"
        mock_svc.get_compute_quotas.assert_called_once()

    @patch(_MOCK_PATCH_QUOTA_SVC)
    @patch(_MOCK_PATCH_LIGHTHOUSE)
    def test_get_quotas_network_provider(self, mock_get_client, mock_svc_cls, authed_client):
        """Returns network quota data when provider=network."""
        mock_get_client.return_value = _mock_lighthouse_client()
        mock_svc = MagicMock()
        summary = _make_network_summary()
        mock_svc.get_network_quotas.return_value = summary
        mock_svc_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/resources/quotas?provider=network")

        assert response.status_code == 200
        data = response.json()
        assert data["overall_status"] == "ok"
        assert len(data["quotas"]) == 2
        assert data["quotas"][0]["provider"] == "network"
        mock_svc.get_network_quotas.assert_called_once()

    @patch(_MOCK_PATCH_QUOTA_SVC)
    @patch(_MOCK_PATCH_LIGHTHOUSE)
    def test_get_quotas_with_subscription_id(self, mock_get_client, mock_svc_cls, authed_client):
        """Uses the provided subscription_id instead of the placeholder."""
        mock_get_client.return_value = _mock_lighthouse_client()
        mock_svc = MagicMock()
        custom_sub = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        summary = _make_compute_summary(sub_id=custom_sub)
        mock_svc.get_compute_quotas.return_value = summary
        mock_svc_cls.return_value = mock_svc

        response = authed_client.get(
            f"/api/v1/resources/quotas?subscription_id={custom_sub}&provider=compute"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["subscription_id"] == custom_sub
        # Verify the service was called with the custom subscription
        call_args = mock_svc.get_compute_quotas.call_args
        assert call_args[0][0] == custom_sub

    def test_get_quotas_requires_auth(self, client):
        """Quota endpoint returns 401 without authentication."""
        response = client.get("/api/v1/resources/quotas")
        assert response.status_code == 401

    @patch(_MOCK_PATCH_QUOTA_SVC)
    @patch(_MOCK_PATCH_LIGHTHOUSE)
    def test_get_quotas_lighthouse_client_error(self, mock_get_client, mock_svc_cls, authed_client):
        """Raises when lighthouse client is unavailable (500 in production)."""
        mock_get_client.side_effect = RuntimeError("Azure credentials unavailable")

        # TestClient re-raises server-side exceptions by default;
        # in production FastAPI returns HTTP 500.
        with pytest.raises(RuntimeError, match="Azure credentials unavailable"):
            authed_client.get("/api/v1/resources/quotas?provider=compute")


# ============================================================================
# GET /api/v1/resources/quotas/summary Tests
# ============================================================================


class TestGetQuotaSummary:
    """Tests for GET /api/v1/resources/quotas/summary endpoint."""

    @patch(_MOCK_PATCH_QUOTA_SVC)
    @patch(_MOCK_PATCH_LIGHTHOUSE)
    def test_get_quota_summary_success(self, mock_get_client, mock_svc_cls, authed_client):
        """Summary endpoint returns aggregated quota health data."""
        mock_get_client.return_value = _mock_lighthouse_client()
        mock_svc = MagicMock()
        mock_svc.get_compute_quotas.return_value = _make_compute_summary()
        mock_svc.aggregate_quotas.return_value = {
            "overall_status": "ok",
            "subscriptions_checked": 1,
            "critical_subscriptions": [],
            "warning_subscriptions": [],
            "top_quotas_by_utilization": [
                {
                    "name": "Total Regional vCPUs",
                    "utilization_pct": 40.0,
                    "status": "ok",
                }
            ],
            "total_quota_metrics": 2,
        }
        mock_svc_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/resources/quotas/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["overall_status"] == "ok"
        assert data["subscriptions_checked"] == 1
        assert data["total_quota_metrics"] == 2
        assert len(data["critical_subscriptions"]) == 0
        mock_svc.aggregate_quotas.assert_called_once()

    def test_get_quota_summary_requires_auth(self, client):
        """Summary endpoint returns 401 without authentication."""
        response = client.get("/api/v1/resources/quotas/summary")
        assert response.status_code == 401

    @patch(_MOCK_PATCH_QUOTA_SVC)
    @patch(_MOCK_PATCH_LIGHTHOUSE)
    def test_get_quota_summary_with_location(self, mock_get_client, mock_svc_cls, authed_client):
        """Summary endpoint passes the location query parameter through."""
        mock_get_client.return_value = _mock_lighthouse_client()
        mock_svc = MagicMock()
        mock_svc.get_compute_quotas.return_value = _make_compute_summary(location="westus2")
        mock_svc.aggregate_quotas.return_value = {
            "overall_status": "ok",
            "subscriptions_checked": 1,
            "critical_subscriptions": [],
            "warning_subscriptions": [],
            "top_quotas_by_utilization": [],
            "total_quota_metrics": 2,
        }
        mock_svc_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/resources/quotas/summary?location=westus2")

        assert response.status_code == 200
        # Verify the service was called with the custom location
        call_args = mock_svc.get_compute_quotas.call_args
        assert call_args[0][2] == "westus2"  # 3rd positional arg = location
