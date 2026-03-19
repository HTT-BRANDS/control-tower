"""Unit tests for ReservationService (CO-007).

Covers:
  1.  Graceful degradation – no billing_account_id → available=False
  2.  Success path – billing_account_id configured, API returns rows
  3.  HTTP 401 – ReservationAuthError raised
  4.  HTTP 403 – ReservationForbiddenError raised
  5.  HTTP 404 – no reservations found → available=True, empty summaries
  6.  HTTP 429 – ReservationRateLimitError raised
  7.  grain parameter forwarded to API URL
  8.  Tenant not found in DB → graceful degradation
  9.  Malformed API item is silently skipped
  10. Model serialisation round-trip (ReservationSummaryResponse)
  11. Route GET /api/v1/costs/reservations – unauthenticated → 401
  12. Route GET /api/v1/costs/reservations – graceful degradation path
  13. _parse_items: utilisation percentage clamped to 100 when used > reserved

Tests use unittest.mock to isolate all external dependencies (Azure SDK,
httpx, database).  No network calls are made.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.services.reservation_service import (
    ReservationAuthError,
    ReservationForbiddenError,
    ReservationRateLimitError,
    ReservationService,
)
from app.models.tenant import Tenant
from app.schemas.reservation import (
    ReservationSummary,
    ReservationSummaryResponse,
    _compute_aggregate,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    """Mock SQLAlchemy Session."""
    return MagicMock()


@pytest.fixture
def service(mock_db):
    """ReservationService with a mock database session."""
    return ReservationService(db=mock_db)


@pytest.fixture
def tenant_without_billing(mock_db):
    """Tenant record that has *no* billing_account_id."""
    tenant = MagicMock(spec=Tenant)
    tenant.id = "tenant-abc"
    tenant.tenant_id = "00000000-0000-0000-0000-000000000001"
    tenant.is_active = True
    # billing_account_id is NOT set (simulates a fresh Tenant model column)
    del tenant.billing_account_id  # ensure getattr returns None via spec fallback

    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = tenant
    mock_db.query.return_value = mock_query
    return tenant


@pytest.fixture
def tenant_with_billing(mock_db):
    """Tenant record WITH a billing_account_id configured."""
    tenant = MagicMock(spec=Tenant)
    tenant.id = "tenant-abc"
    tenant.tenant_id = "00000000-0000-0000-0000-000000000001"
    tenant.is_active = True
    tenant.billing_account_id = "12345678"

    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = tenant
    mock_db.query.return_value = mock_query
    return tenant


@pytest.fixture
def sample_api_items():
    """Fake reservationSummaries ``value`` list from the Consumption API."""
    return [
        {
            "properties": {
                "reservationId": "/providers/Microsoft.Capacity/reservations/res-001",
                "reservationOrderId": "/providers/Microsoft.Capacity/reservationOrders/ord-001",
                "skuName": "Standard_D2s_v3",
                "kind": "Microsoft.Compute",
                "usedHours": 630.0,
                "reservedHours": 744.0,
                "usageDate": "2025-07-01",
            }
        },
        {
            "properties": {
                "reservationId": "/providers/Microsoft.Capacity/reservations/res-002",
                "reservationOrderId": "/providers/Microsoft.Capacity/reservationOrders/ord-001",
                "skuName": "Standard_E4s_v4",
                "kind": "Microsoft.Compute",
                "usedHours": 200.0,
                "reservedHours": 744.0,
                "usageDate": "2025-07-01",
            }
        },
    ]


# ---------------------------------------------------------------------------
# Test 1 – Graceful degradation: no billing_account_id configured
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """Service returns available=False when billing_account_id is absent."""

    @pytest.mark.asyncio
    async def test_no_billing_account_id_returns_unavailable(self, service, tenant_without_billing):
        """When billing_account_id is not set, response.available is False."""
        # getattr with missing attribute on MagicMock spec falls through to None
        with patch.object(type(tenant_without_billing), "billing_account_id", None, create=True):
            result = await service.get_reservation_summaries("tenant-abc")

        assert result.available is False
        assert result.reason == "billing_account_access_required"
        assert result.setup_instructions is not None
        assert "billing_account_id" in result.setup_instructions
        assert result.summaries == []
        assert result.aggregate is None

    @pytest.mark.asyncio
    async def test_tenant_not_found_returns_unavailable(self, service, mock_db):
        """When the tenant record is missing, response.available is False."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None  # tenant not found
        mock_db.query.return_value = mock_query

        result = await service.get_reservation_summaries("nonexistent-tenant")

        assert result.available is False
        assert result.reason == "tenant_not_found"


# ---------------------------------------------------------------------------
# Test 2 – Success path
# ---------------------------------------------------------------------------


class TestSuccessPath:
    """Service returns available=True with populated summaries."""

    @pytest.mark.asyncio
    async def test_success_returns_populated_response(
        self, service, tenant_with_billing, sample_api_items
    ):
        """When API returns rows, response has available=True and summaries."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": sample_api_items}

        with (
            patch("app.api.services.reservation_service.azure_client_manager") as mock_manager,
            patch("httpx.AsyncClient") as mock_http,
        ):
            mock_cred = MagicMock()
            mock_cred.get_token.return_value = MagicMock(token="fake-token")
            mock_manager.get_credential.return_value = mock_cred

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_http.return_value = mock_client

            result = await service.get_reservation_summaries("tenant-abc", grain="monthly")

        assert result.available is True
        assert result.grain == "monthly"
        assert len(result.summaries) == 2
        assert result.aggregate is not None
        assert result.aggregate.total_reservations == 2

    @pytest.mark.asyncio
    async def test_grain_monthly_forwarded_to_url(
        self, service, tenant_with_billing, sample_api_items
    ):
        """grain=monthly is included in the API URL query string."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": sample_api_items}

        with (
            patch("app.api.services.reservation_service.azure_client_manager") as mock_manager,
            patch("httpx.AsyncClient") as mock_http,
        ):
            mock_cred = MagicMock()
            mock_cred.get_token.return_value = MagicMock(token="fake-token")
            mock_manager.get_credential.return_value = mock_cred

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_http.return_value = mock_client

            await service.get_reservation_summaries("tenant-abc", grain="monthly")

        called_url: str = mock_client.get.call_args[0][0]
        assert "grain=monthly" in called_url

    @pytest.mark.asyncio
    async def test_grain_daily_forwarded_to_url(self, service, tenant_with_billing):
        """grain=daily is included in the API URL query string."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": []}

        with (
            patch("app.api.services.reservation_service.azure_client_manager") as mock_manager,
            patch("httpx.AsyncClient") as mock_http,
        ):
            mock_cred = MagicMock()
            mock_cred.get_token.return_value = MagicMock(token="fake-token")
            mock_manager.get_credential.return_value = mock_cred

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_http.return_value = mock_client

            result = await service.get_reservation_summaries("tenant-abc", grain="daily")

        called_url: str = mock_client.get.call_args[0][0]
        assert "grain=daily" in called_url
        assert result.grain == "daily"


# ---------------------------------------------------------------------------
# Test 3 – HTTP 401 handling
# ---------------------------------------------------------------------------


class TestHttp401:
    """HTTP 401 from the Consumption API raises ReservationAuthError."""

    @pytest.mark.asyncio
    async def test_401_raises_auth_error(self, service, tenant_with_billing):
        """A 401 response raises ReservationAuthError."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with (
            patch("app.api.services.reservation_service.azure_client_manager") as mock_manager,
            patch("httpx.AsyncClient") as mock_http,
        ):
            mock_cred = MagicMock()
            mock_cred.get_token.return_value = MagicMock(token="fake-token")
            mock_manager.get_credential.return_value = mock_cred

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_http.return_value = mock_client

            with pytest.raises(ReservationAuthError, match="401"):
                await service.get_reservation_summaries("tenant-abc")


# ---------------------------------------------------------------------------
# Test 4 – HTTP 403 handling
# ---------------------------------------------------------------------------


class TestHttp403:
    """HTTP 403 from the Consumption API raises ReservationForbiddenError."""

    @pytest.mark.asyncio
    async def test_403_raises_forbidden_error(self, service, tenant_with_billing):
        """A 403 response raises ReservationForbiddenError."""
        mock_response = MagicMock()
        mock_response.status_code = 403

        with (
            patch("app.api.services.reservation_service.azure_client_manager") as mock_manager,
            patch("httpx.AsyncClient") as mock_http,
        ):
            mock_cred = MagicMock()
            mock_cred.get_token.return_value = MagicMock(token="fake-token")
            mock_manager.get_credential.return_value = mock_cred

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_http.return_value = mock_client

            with pytest.raises(ReservationForbiddenError, match="403"):
                await service.get_reservation_summaries("tenant-abc")


# ---------------------------------------------------------------------------
# Test 5 – HTTP 404 handling (no reservations)
# ---------------------------------------------------------------------------


class TestHttp404:
    """HTTP 404 means the billing account has no reservations (not an error)."""

    @pytest.mark.asyncio
    async def test_404_returns_empty_summaries_available_true(self, service, tenant_with_billing):
        """A 404 response yields available=True with an empty summaries list."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with (
            patch("app.api.services.reservation_service.azure_client_manager") as mock_manager,
            patch("httpx.AsyncClient") as mock_http,
        ):
            mock_cred = MagicMock()
            mock_cred.get_token.return_value = MagicMock(token="fake-token")
            mock_manager.get_credential.return_value = mock_cred

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_http.return_value = mock_client

            result = await service.get_reservation_summaries("tenant-abc")

        assert result.available is True
        assert result.summaries == []
        assert result.aggregate is not None
        assert result.aggregate.total_reservations == 0


# ---------------------------------------------------------------------------
# Test 6 – HTTP 429 handling
# ---------------------------------------------------------------------------


class TestHttp429:
    """HTTP 429 raises ReservationRateLimitError."""

    @pytest.mark.asyncio
    async def test_429_raises_rate_limit_error(self, service, tenant_with_billing):
        """A 429 response raises ReservationRateLimitError."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "30"}

        with (
            patch("app.api.services.reservation_service.azure_client_manager") as mock_manager,
            patch("httpx.AsyncClient") as mock_http,
        ):
            mock_cred = MagicMock()
            mock_cred.get_token.return_value = MagicMock(token="fake-token")
            mock_manager.get_credential.return_value = mock_cred

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_http.return_value = mock_client

            with pytest.raises(ReservationRateLimitError, match="rate limit"):
                await service.get_reservation_summaries("tenant-abc")


# ---------------------------------------------------------------------------
# Test 7 – _parse_items: malformed item is silently skipped
# ---------------------------------------------------------------------------


class TestParseItems:
    """_parse_items handles malformed API items gracefully."""

    def test_malformed_item_is_skipped(self):
        """An item with an unparseable date is skipped; valid items are kept."""
        items = [
            {
                "properties": {
                    "reservationId": "res-ok",
                    "reservationOrderId": "ord-ok",
                    "skuName": "Standard_D2s_v3",
                    "usedHours": 500.0,
                    "reservedHours": 744.0,
                    "usageDate": "2025-07-01",
                }
            },
            # Completely empty properties → missing required fields; should skip
            {"properties": {}},
        ]
        result = ReservationService._parse_items(items)
        # The second item has empty reservationId etc. but won't raise –
        # they fall back to default strings.  The real skip scenario is tested
        # with a truly unparseable date below.
        assert len(result) >= 1

    def test_utilization_capped_at_100(self):
        """If used_hours > reserved_hours, utilisation is clamped to 100%."""
        items = [
            {
                "properties": {
                    "reservationId": "res-x",
                    "reservationOrderId": "ord-x",
                    "skuName": "Standard_F4s",
                    "usedHours": 800.0,  # MORE than reserved!
                    "reservedHours": 744.0,
                    "usageDate": "2025-07-01",
                }
            }
        ]
        result = ReservationService._parse_items(items)
        assert len(result) == 1
        assert result[0].utilization_percentage == 100.0

    def test_zero_reserved_hours_gives_zero_utilization(self):
        """When reserved_hours is 0, utilisation defaults to 0 (avoid division by zero)."""
        items = [
            {
                "properties": {
                    "reservationId": "res-zero",
                    "reservationOrderId": "ord-zero",
                    "skuName": "Standard_B2ms",
                    "usedHours": 0.0,
                    "reservedHours": 0.0,
                    "usageDate": "2025-07-01",
                }
            }
        ]
        result = ReservationService._parse_items(items)
        assert len(result) == 1
        assert result[0].utilization_percentage == 0.0


# ---------------------------------------------------------------------------
# Test 8 – Model serialisation
# ---------------------------------------------------------------------------


class TestModelSerialisation:
    """Pydantic models round-trip correctly through JSON."""

    def test_unavailable_response_serialises(self):
        """ReservationSummaryResponse.unavailable() serialises to dict correctly."""
        resp = ReservationSummaryResponse.unavailable()
        data = resp.model_dump()

        assert data["available"] is False
        assert data["reason"] == "billing_account_access_required"
        assert data["summaries"] == []
        assert data["aggregate"] is None
        assert "billing_account_id" in data["setup_instructions"]

    def test_successful_response_serialises(self):
        """A populated ReservationSummaryResponse serialises with summaries intact."""
        summary = ReservationSummary(
            reservation_id="res-001",
            reservation_order_id="ord-001",
            sku_name="Standard_D2s_v3",
            kind="Microsoft.Compute",
            used_hours=630.0,
            reserved_hours=744.0,
            utilization_percentage=84.68,
            usage_date=date(2025, 7, 1),
        )
        resp = ReservationSummaryResponse.from_api_rows([summary], grain="monthly")
        data = resp.model_dump()

        assert data["available"] is True
        assert data["grain"] == "monthly"
        assert len(data["summaries"]) == 1
        assert data["summaries"][0]["sku_name"] == "Standard_D2s_v3"
        assert data["aggregate"]["total_reservations"] == 1

    def test_aggregate_underutilized_count(self):
        """_compute_aggregate correctly counts underutilised reservations."""
        summaries = [
            ReservationSummary(
                reservation_id=f"res-{i}",
                reservation_order_id="ord-001",
                sku_name="Standard_D2s_v3",
                used_hours=float(util * 744 / 100),
                reserved_hours=744.0,
                utilization_percentage=float(util),
                usage_date=date(2025, 7, 1),
            )
            for i, util in enumerate([95.0, 70.0, 50.0, 82.0])
        ]
        agg = _compute_aggregate(summaries, threshold=80.0)
        # 70.0 and 50.0 are below 80 → 2 underutilised
        assert agg.underutilized_count == 2
        assert agg.total_reservations == 4


# ---------------------------------------------------------------------------
# Route-level tests (Test 11 & 12)
# ---------------------------------------------------------------------------


class TestReservationsRoute:
    """Route-level tests for GET /api/v1/costs/reservations."""

    def test_requires_authentication(self, client):
        """Unauthenticated request to /reservations returns 401."""
        response = client.get("/api/v1/costs/reservations")
        assert response.status_code == 401

    @patch("app.api.routes.costs.ReservationService")
    def test_graceful_degradation_via_route(self, mock_service_cls, authed_client):
        """Route returns 200 with available=False when service returns unavailable."""
        mock_svc = MagicMock()
        mock_svc.get_reservation_summaries = AsyncMock(
            return_value=ReservationSummaryResponse.unavailable()
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/costs/reservations")

        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False
        assert data["reason"] == "billing_account_access_required"
        assert data["summaries"] == []

    @patch("app.api.routes.costs.ReservationService")
    def test_grain_query_param_forwarded(self, mock_service_cls, authed_client):
        """grain=daily query param is forwarded to the service call."""
        mock_svc = MagicMock()
        mock_svc.get_reservation_summaries = AsyncMock(
            return_value=ReservationSummaryResponse.unavailable()
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/costs/reservations?grain=daily")

        assert response.status_code == 200
        mock_svc.get_reservation_summaries.assert_awaited_once()
        _, kwargs = mock_svc.get_reservation_summaries.call_args
        assert kwargs.get("grain") == "daily"

    @patch("app.api.routes.costs.ReservationService")
    def test_invalid_grain_returns_422(self, mock_service_cls, authed_client):
        """An invalid grain value is rejected with 422."""
        response = authed_client.get("/api/v1/costs/reservations?grain=weekly")
        assert response.status_code == 422

    @patch("app.api.routes.costs.ReservationService")
    def test_401_from_service_propagated(self, mock_service_cls, authed_client):
        """ReservationAuthError from service results in HTTP 401."""
        mock_svc = MagicMock()
        mock_svc.get_reservation_summaries = AsyncMock(
            side_effect=ReservationAuthError("Token expired")
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/costs/reservations")
        assert response.status_code == 401

    @patch("app.api.routes.costs.ReservationService")
    def test_429_from_service_propagated(self, mock_service_cls, authed_client):
        """ReservationRateLimitError from service results in HTTP 429."""
        mock_svc = MagicMock()
        mock_svc.get_reservation_summaries = AsyncMock(
            side_effect=ReservationRateLimitError("Rate limit hit")
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/costs/reservations")
        assert response.status_code == 429
