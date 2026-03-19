"""Unit tests for LicenseService and license route endpoints.

Tests cover:
- get_user_licenses success path (single + multiple SKUs)
- get_user_licenses with empty response
- get_user_licenses 404 (user not found) returns empty list
- list_tenant_licenses aggregation and SKU name enrichment
- list_tenant_licenses skips unlicensed users
- Pagination handling (_paginate exhausts nextLink chains)
- Graph API error 401 raises LicenseServiceError
- Graph API error 429 raises LicenseServiceError with status_code
- Model serialisation (UserLicense, UserLicenseSummary, ServicePlanDetail)
- LicenseServiceError attributes
- Route: GET /api/v1/identity/licenses (list)
- Route: GET /api/v1/identity/licenses/{user_id} (per-user)
- Route: GET /api/v1/identity/licenses propagates 401 as 401
- Route: GET /api/v1/identity/licenses/{user_id} auth guard
"""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# ---------------------------------------------------------------------------
# Suppress Azure SDK imports so the service file can be imported in CI
# without real Azure credentials.
# ---------------------------------------------------------------------------
_azure_mock = MagicMock()
sys.modules.setdefault("azure", _azure_mock)
sys.modules.setdefault("azure.identity", _azure_mock)
sys.modules.setdefault("azure.core", _azure_mock)
sys.modules.setdefault("azure.core.exceptions", _azure_mock)

from app.api.services.license_service import (  # noqa: E402
    LicenseService,
    LicenseServiceError,
)
from app.schemas.license import ServicePlanDetail, UserLicense, UserLicenseSummary  # noqa: E402

# ---------------------------------------------------------------------------
# Shared sample data
# ---------------------------------------------------------------------------

_TENANT_ID = "test-tenant-123"
_USER_ID = "user-abc-123"
_UPN = "alice@contoso.com"
_DISPLAY_NAME = "Alice Smith"

_SAMPLE_USER_RESPONSE = {
    "id": _USER_ID,
    "displayName": _DISPLAY_NAME,
    "userPrincipalName": _UPN,
}

_SAMPLE_LICENSE_DETAIL = {
    "id": "detail-1",
    "skuId": "sku-e5-guid",
    "skuPartNumber": "ENTERPRISEPREMIUM",
    "servicePlans": [
        {
            "servicePlanId": "plan-exchange-guid",
            "servicePlanName": "EXCHANGE_S_ENTERPRISE",
            "provisioningStatus": "Success",
            "appliesTo": "User",
        },
        {
            "servicePlanId": "plan-teams-guid",
            "servicePlanName": "TEAMS1",
            "provisioningStatus": "Success",
            "appliesTo": "User",
        },
    ],
}

_SAMPLE_SKU_LIST = {
    "value": [
        {"skuId": "sku-e5-guid", "skuPartNumber": "ENTERPRISEPREMIUM"},
        {"skuId": "sku-e3-guid", "skuPartNumber": "ENTERPRISEPACK"},
    ]
}

_SAMPLE_USER_WITH_LICENSE = {
    "id": _USER_ID,
    "displayName": _DISPLAY_NAME,
    "userPrincipalName": _UPN,
    "assignedLicenses": [{"skuId": "sku-e5-guid"}],
}

_SAMPLE_USER_NO_LICENSE = {
    "id": "user-no-lic",
    "displayName": "Bob Bloggs",
    "userPrincipalName": "bob@contoso.com",
    "assignedLicenses": [],
}


# ---------------------------------------------------------------------------
# Helper: build a fake httpx response with a given status code
# ---------------------------------------------------------------------------


def _fake_http_error(status_code: int, headers: dict | None = None) -> httpx.HTTPStatusError:
    """Build an httpx.HTTPStatusError with the given status code."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.headers = headers or {}
    return httpx.HTTPStatusError("fake error", request=MagicMock(), response=mock_response)


# ===========================================================================
# 1. Model serialisation tests
# ===========================================================================


class TestLicenseModels:
    """Verify Pydantic model construction and serialisation."""

    def test_service_plan_detail_creation(self):
        """ServicePlanDetail stores all fields correctly."""
        plan = ServicePlanDetail(
            service_plan_id="plan-guid",
            service_plan_name="EXCHANGE_S_ENTERPRISE",
            provisioning_status="Success",
            applies_to="User",
        )
        assert plan.service_plan_id == "plan-guid"
        assert plan.service_plan_name == "EXCHANGE_S_ENTERPRISE"
        assert plan.provisioning_status == "Success"
        assert plan.applies_to == "User"

    def test_user_license_serialises_to_dict(self):
        """UserLicense round-trips through model_dump without data loss."""
        lic = UserLicense(
            user_id=_USER_ID,
            user_principal_name=_UPN,
            display_name=_DISPLAY_NAME,
            sku_id="sku-e5-guid",
            sku_part_number="ENTERPRISEPREMIUM",
            service_plans=[
                ServicePlanDetail(
                    service_plan_id="p1",
                    service_plan_name="TEAMS1",
                    provisioning_status="Success",
                )
            ],
        )
        data = lic.model_dump()
        assert data["user_id"] == _USER_ID
        assert data["sku_part_number"] == "ENTERPRISEPREMIUM"
        assert len(data["service_plans"]) == 1
        assert data["service_plans"][0]["service_plan_name"] == "TEAMS1"

    def test_user_license_summary_default_lists(self):
        """UserLicenseSummary initialises with empty lists by default."""
        summary = UserLicenseSummary(
            tenant_id=_TENANT_ID,
            user_id=_USER_ID,
            user_principal_name=_UPN,
            display_name=_DISPLAY_NAME,
        )
        assert summary.assigned_sku_ids == []
        assert summary.assigned_sku_part_numbers == []
        assert summary.license_count == 0


# ===========================================================================
# 2. LicenseServiceError tests
# ===========================================================================


class TestLicenseServiceError:
    """LicenseServiceError stores context attributes correctly."""

    def test_error_message_and_attrs(self):
        """LicenseServiceError exposes tenant_id and status_code."""
        err = LicenseServiceError("boom", tenant_id=_TENANT_ID, status_code=401)
        assert str(err) == "boom"
        assert err.tenant_id == _TENANT_ID
        assert err.status_code == 401

    def test_error_optional_attrs(self):
        """LicenseServiceError works with no tenant_id or status_code."""
        err = LicenseServiceError("oops")
        assert err.tenant_id is None
        assert err.status_code is None


# ===========================================================================
# 3. get_user_licenses tests
# ===========================================================================


class TestGetUserLicenses:
    """Tests for LicenseService.get_user_licenses."""

    @pytest.fixture
    def svc(self):
        """Fresh LicenseService instance for each test."""
        return LicenseService()

    @pytest.fixture
    def mock_client(self):
        """Mock GraphClient whose _request can be configured per test."""
        return MagicMock()

    async def _make_request_side_effect(self, user_resp, license_resp):
        """Factory: returns an async side_effect for client._request."""

        async def _side_effect(method, endpoint, params=None):
            if "/licenseDetails" in endpoint:
                return license_resp
            return user_resp

        return _side_effect

    @pytest.mark.asyncio
    async def test_get_user_licenses_success_single_sku(self, svc, mock_client):
        """get_user_licenses returns one UserLicense per assigned SKU."""
        license_page = {"value": [_SAMPLE_LICENSE_DETAIL], "@odata.nextLink": None}

        async def _request(method, endpoint, params=None):
            if "/licenseDetails" in endpoint:
                return license_page
            return _SAMPLE_USER_RESPONSE

        mock_client._request = _request
        svc._clients[_TENANT_ID] = mock_client

        result = await svc.get_user_licenses(_TENANT_ID, _USER_ID)

        assert len(result) == 1
        lic = result[0]
        assert isinstance(lic, UserLicense)
        assert lic.user_id == _USER_ID
        assert lic.sku_part_number == "ENTERPRISEPREMIUM"
        assert len(lic.service_plans) == 2
        assert lic.service_plans[0].service_plan_name == "EXCHANGE_S_ENTERPRISE"

    @pytest.mark.asyncio
    async def test_get_user_licenses_empty_response(self, svc, mock_client):
        """get_user_licenses returns empty list when user has no licenses."""

        async def _request(method, endpoint, params=None):
            if "/licenseDetails" in endpoint:
                return {"value": []}
            return _SAMPLE_USER_RESPONSE

        mock_client._request = _request
        svc._clients[_TENANT_ID] = mock_client

        result = await svc.get_user_licenses(_TENANT_ID, _USER_ID)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_user_licenses_user_not_found_returns_empty(self, svc, mock_client):
        """get_user_licenses returns [] when user endpoint returns 404."""

        async def _request(method, endpoint, params=None):
            if "/licenseDetails" not in endpoint:
                raise _fake_http_error(404)
            return {"value": []}

        mock_client._request = _request
        svc._clients[_TENANT_ID] = mock_client

        result = await svc.get_user_licenses(_TENANT_ID, "unknown-user-id")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_user_licenses_401_raises(self, svc, mock_client):
        """get_user_licenses raises LicenseServiceError(status_code=401) on 401."""

        async def _request(method, endpoint, params=None):
            raise _fake_http_error(401)

        mock_client._request = _request
        svc._clients[_TENANT_ID] = mock_client

        with pytest.raises(LicenseServiceError) as exc_info:
            await svc.get_user_licenses(_TENANT_ID, _USER_ID)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_user_licenses_429_raises(self, svc, mock_client):
        """get_user_licenses raises LicenseServiceError(status_code=429) on 429."""

        async def _request(method, endpoint, params=None):
            raise _fake_http_error(429, headers={"Retry-After": "10"})

        mock_client._request = _request
        svc._clients[_TENANT_ID] = mock_client

        with pytest.raises(LicenseServiceError) as exc_info:
            await svc.get_user_licenses(_TENANT_ID, _USER_ID)

        assert exc_info.value.status_code == 429
        assert "429" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_user_licenses_pagination(self, svc, mock_client):
        """get_user_licenses fetches all pages when nextLink is present."""
        call_count = 0

        async def _request(method, endpoint, params=None):
            nonlocal call_count
            call_count += 1
            if "/licenseDetails" not in endpoint:
                return _SAMPLE_USER_RESPONSE
            # First page has nextLink; second page has data.
            if call_count == 2:
                return {
                    "value": [_SAMPLE_LICENSE_DETAIL],
                    "@odata.nextLink": "https://graph.microsoft.com/v1.0/users/x/licenseDetails?$skiptoken=abc",
                }
            return {"value": [_SAMPLE_LICENSE_DETAIL]}  # page 2 — no nextLink

        mock_client._request = _request
        svc._clients[_TENANT_ID] = mock_client

        result = await svc.get_user_licenses(_TENANT_ID, _USER_ID)

        # Two pages × 1 item each = 2 UserLicense objects.
        assert len(result) == 2
        assert call_count == 3  # 1 user fetch + 2 license pages

    @pytest.mark.asyncio
    async def test_get_user_licenses_multiple_skus(self, svc, mock_client):
        """get_user_licenses returns one UserLicense per SKU when user has several."""
        second_sku = {
            "id": "detail-2",
            "skuId": "sku-e3-guid",
            "skuPartNumber": "ENTERPRISEPACK",
            "servicePlans": [],
        }

        async def _request(method, endpoint, params=None):
            if "/licenseDetails" in endpoint:
                return {"value": [_SAMPLE_LICENSE_DETAIL, second_sku]}
            return _SAMPLE_USER_RESPONSE

        mock_client._request = _request
        svc._clients[_TENANT_ID] = mock_client

        result = await svc.get_user_licenses(_TENANT_ID, _USER_ID)

        assert len(result) == 2
        part_numbers = {r.sku_part_number for r in result}
        assert part_numbers == {"ENTERPRISEPREMIUM", "ENTERPRISEPACK"}


# ===========================================================================
# 4. list_tenant_licenses tests
# ===========================================================================


class TestListTenantLicenses:
    """Tests for LicenseService.list_tenant_licenses."""

    @pytest.fixture
    def svc(self):
        return LicenseService()

    @pytest.fixture
    def mock_client(self):
        return MagicMock()

    @pytest.mark.asyncio
    async def test_list_tenant_licenses_aggregation(self, svc, mock_client):
        """list_tenant_licenses returns one summary per licensed user, enriched with SKU name."""

        async def _request(method, endpoint, params=None):
            if "/subscribedSkus" in endpoint:
                return _SAMPLE_SKU_LIST
            return {"value": [_SAMPLE_USER_WITH_LICENSE, _SAMPLE_USER_NO_LICENSE]}

        mock_client._request = _request
        svc._clients[_TENANT_ID] = mock_client

        result = await svc.list_tenant_licenses(_TENANT_ID)

        # Only the licensed user should appear.
        assert len(result) == 1
        summary = result[0]
        assert isinstance(summary, UserLicenseSummary)
        assert summary.user_id == _USER_ID
        assert summary.license_count == 1
        assert "ENTERPRISEPREMIUM" in summary.assigned_sku_part_numbers
        assert summary.tenant_id == _TENANT_ID

    @pytest.mark.asyncio
    async def test_list_tenant_licenses_skips_unlicensed_users(self, svc, mock_client):
        """list_tenant_licenses excludes users with no assignedLicenses."""

        async def _request(method, endpoint, params=None):
            if "/subscribedSkus" in endpoint:
                return {"value": []}
            # Two unlicensed users.
            return {"value": [_SAMPLE_USER_NO_LICENSE, {**_SAMPLE_USER_NO_LICENSE, "id": "u2"}]}

        mock_client._request = _request
        svc._clients[_TENANT_ID] = mock_client

        result = await svc.list_tenant_licenses(_TENANT_ID)

        assert result == []

    @pytest.mark.asyncio
    async def test_list_tenant_licenses_pagination(self, svc, mock_client):
        """list_tenant_licenses follows @odata.nextLink for /users pagination."""
        page_call_count = 0

        async def _request(method, endpoint, params=None):
            nonlocal page_call_count
            if "/subscribedSkus" in endpoint:
                return _SAMPLE_SKU_LIST
            page_call_count += 1
            if page_call_count == 1:
                return {
                    "value": [_SAMPLE_USER_WITH_LICENSE],
                    "@odata.nextLink": "https://graph.microsoft.com/v1.0/users?$skiptoken=xyz",
                }
            return {"value": [_SAMPLE_USER_WITH_LICENSE]}  # page 2, no nextLink

        mock_client._request = _request
        svc._clients[_TENANT_ID] = mock_client

        result = await svc.list_tenant_licenses(_TENANT_ID)

        # 2 pages × 1 licensed user each = 2 summaries.
        assert len(result) == 2
        assert page_call_count == 2

    @pytest.mark.asyncio
    async def test_list_tenant_licenses_401_raises(self, svc, mock_client):
        """list_tenant_licenses raises LicenseServiceError on 401."""

        async def _request(method, endpoint, params=None):
            raise _fake_http_error(401)

        mock_client._request = _request
        svc._clients[_TENANT_ID] = mock_client

        with pytest.raises(LicenseServiceError) as exc_info:
            await svc.list_tenant_licenses(_TENANT_ID)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_list_tenant_licenses_429_raises(self, svc, mock_client):
        """list_tenant_licenses raises LicenseServiceError(status_code=429) on 429."""

        async def _request(method, endpoint, params=None):
            raise _fake_http_error(429, headers={"Retry-After": "5"})

        mock_client._request = _request
        svc._clients[_TENANT_ID] = mock_client

        with pytest.raises(LicenseServiceError) as exc_info:
            await svc.list_tenant_licenses(_TENANT_ID)

        assert exc_info.value.status_code == 429
        assert "429" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_list_tenant_licenses_sku_fallback_on_unknown_sku(self, svc, mock_client):
        """list_tenant_licenses falls back to skuId when skuId not in the catalogue."""

        async def _request(method, endpoint, params=None):
            if "/subscribedSkus" in endpoint:
                return {"value": []}  # Empty SKU catalogue.
            user_with_unknown_sku = {
                **_SAMPLE_USER_WITH_LICENSE,
                "assignedLicenses": [{"skuId": "unknown-sku-guid"}],
            }
            return {"value": [user_with_unknown_sku]}

        mock_client._request = _request
        svc._clients[_TENANT_ID] = mock_client

        result = await svc.list_tenant_licenses(_TENANT_ID)

        assert len(result) == 1
        # Falls back to the raw skuId when not in the catalogue.
        assert result[0].assigned_sku_part_numbers == ["unknown-sku-guid"]


# ===========================================================================
# 5. Route-level tests
# ===========================================================================


class TestLicenseRoutes:
    """Route-level tests for GET /api/v1/identity/licenses endpoints."""

    @patch("app.api.routes.identity.license_service")
    def test_list_tenant_licenses_route_success(self, mock_svc, authed_client):
        """GET /api/v1/identity/licenses returns 200 with a list of summaries."""
        mock_svc.list_tenant_licenses = AsyncMock(
            return_value=[
                UserLicenseSummary(
                    tenant_id=_TENANT_ID,
                    user_id=_USER_ID,
                    user_principal_name=_UPN,
                    display_name=_DISPLAY_NAME,
                    assigned_sku_ids=["sku-e5-guid"],
                    assigned_sku_part_numbers=["ENTERPRISEPREMIUM"],
                    license_count=1,
                )
            ]
        )

        response = authed_client.get(f"/api/v1/identity/licenses?tenant_id={_TENANT_ID}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["user_id"] == _USER_ID
        assert data[0]["assigned_sku_part_numbers"] == ["ENTERPRISEPREMIUM"]
        assert data[0]["license_count"] == 1

    @patch("app.api.routes.identity.license_service")
    def test_get_user_licenses_route_success(self, mock_svc, authed_client):
        """GET /api/v1/identity/licenses/{user_id} returns 200 with license list."""
        mock_svc.get_user_licenses = AsyncMock(
            return_value=[
                UserLicense(
                    user_id=_USER_ID,
                    user_principal_name=_UPN,
                    display_name=_DISPLAY_NAME,
                    sku_id="sku-e5-guid",
                    sku_part_number="ENTERPRISEPREMIUM",
                    service_plans=[
                        ServicePlanDetail(
                            service_plan_id="plan-1",
                            service_plan_name="TEAMS1",
                            provisioning_status="Success",
                        )
                    ],
                )
            ]
        )

        response = authed_client.get(f"/api/v1/identity/licenses/{_USER_ID}?tenant_id={_TENANT_ID}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["sku_part_number"] == "ENTERPRISEPREMIUM"
        assert data[0]["service_plans"][0]["service_plan_name"] == "TEAMS1"

    @patch("app.api.routes.identity.license_service")
    def test_list_tenant_licenses_route_returns_empty_list(self, mock_svc, authed_client):
        """GET /api/v1/identity/licenses returns 200 with [] when no users are licensed."""
        mock_svc.list_tenant_licenses = AsyncMock(return_value=[])

        response = authed_client.get(f"/api/v1/identity/licenses?tenant_id={_TENANT_ID}")

        assert response.status_code == 200
        assert response.json() == []

    @patch("app.api.routes.identity.license_service")
    def test_get_user_licenses_route_401_propagated(self, mock_svc, authed_client):
        """GET /api/v1/identity/licenses/{user_id} converts LicenseServiceError(401) to HTTP 401."""
        mock_svc.get_user_licenses = AsyncMock(
            side_effect=LicenseServiceError("Unauthorized", status_code=401)
        )

        response = authed_client.get(f"/api/v1/identity/licenses/{_USER_ID}?tenant_id={_TENANT_ID}")

        assert response.status_code == 401

    def test_list_tenant_licenses_route_requires_auth(self, client):
        """GET /api/v1/identity/licenses returns 401 without authentication."""
        response = client.get(f"/api/v1/identity/licenses?tenant_id={_TENANT_ID}")
        assert response.status_code == 401

    def test_get_user_licenses_route_requires_auth(self, client):
        """GET /api/v1/identity/licenses/{user_id} returns 401 without authentication."""
        response = client.get(f"/api/v1/identity/licenses/{_USER_ID}?tenant_id={_TENANT_ID}")
        assert response.status_code == 401

    @patch("app.api.routes.identity.license_service")
    def test_list_tenant_licenses_route_429_propagated(self, mock_svc, authed_client):
        """GET /api/v1/identity/licenses converts LicenseServiceError(429) to HTTP 429."""
        mock_svc.list_tenant_licenses = AsyncMock(
            side_effect=LicenseServiceError("Rate limit hit", status_code=429)
        )

        response = authed_client.get(f"/api/v1/identity/licenses?tenant_id={_TENANT_ID}")

        assert response.status_code == 429
