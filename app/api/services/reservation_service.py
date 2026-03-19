"""Reserved Instance Utilisation Service (CO-007).

Calls the Azure Consumption API reservationSummaries endpoint when a
billing_account_id is configured on the tenant record.  Otherwise returns
a structured "unavailable" response so callers can display a helpful
onboarding message instead of an error.

Architecture note (see docs/decisions/co007-scope-assessment.md):
    The Consumption reservationSummaries endpoint requires *billing account*
    scope which is outside Azure Lighthouse's delegation reach (subscription
    scope only).  The service therefore implements graceful degradation:

    • billing_account_id configured → call the real API
    • billing_account_id absent      → return available=False with setup guide

API reference:
    GET https://management.azure.com/providers/Microsoft.Billing/
        billingAccounts/{billingAccountId}/providers/
        Microsoft.Consumption/reservationSummaries
        ?grain={grain}&api-version=2024-08-01
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Literal

import httpx
from sqlalchemy.orm import Session

from app.api.services.azure_client import azure_client_manager
from app.models.tenant import Tenant
from app.schemas.reservation import (
    SETUP_INSTRUCTIONS,
    ReservationSummary,
    ReservationSummaryResponse,
)

logger = logging.getLogger(__name__)

# Azure Consumption API version that includes reservationSummaries at
# billing-account scope (confirmed 2025-07).
RESERVATION_API_VERSION = "2024-08-01"


class ReservationServiceError(Exception):
    """Base exception for reservation service failures."""


class ReservationAuthError(ReservationServiceError):
    """Raised on HTTP 401 – credential is invalid or expired."""


class ReservationForbiddenError(ReservationServiceError):
    """Raised on HTTP 403 – service principal lacks billing account access."""


class ReservationRateLimitError(ReservationServiceError):
    """Raised on HTTP 429 – Consumption API rate limit hit."""


class ReservationService:
    """Fetch Azure Reserved Instance utilisation data for a tenant.

    Parameters
    ----------
    db:
        SQLAlchemy session used to look up tenant configuration.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_reservation_summaries(
        self,
        tenant_id: str,
        grain: Literal["daily", "monthly"] = "monthly",
    ) -> ReservationSummaryResponse:
        """Return reservation utilisation summaries for *tenant_id*.

        Parameters
        ----------
        tenant_id:
            The internal tenant record ID (``Tenant.id``).
        grain:
            Granularity of the returned data; either ``"daily"`` or
            ``"monthly"``.

        Returns
        -------
        ReservationSummaryResponse
            ``available=True`` with populated ``summaries`` when the
            billing account is configured and reachable.
            ``available=False`` with ``reason`` and ``setup_instructions``
            when billing account scope is not configured.
        """
        tenant = self._db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant is None:
            logger.warning("ReservationService: tenant %s not found in database", tenant_id)
            return ReservationSummaryResponse.unavailable(
                reason="tenant_not_found",
                setup_instructions="The requested tenant was not found.",
            )

        billing_account_id: str | None = getattr(tenant, "billing_account_id", None)
        if not billing_account_id:
            logger.info(
                "ReservationService: no billing_account_id for tenant %s – "
                "returning graceful degradation response",
                tenant_id,
            )
            return ReservationSummaryResponse.unavailable(
                setup_instructions=SETUP_INSTRUCTIONS,
            )

        # Billing account is configured – fetch live data.
        return await self._fetch_summaries(
            azure_tenant_id=tenant.tenant_id,
            billing_account_id=billing_account_id,
            grain=grain,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _fetch_summaries(
        self,
        azure_tenant_id: str,
        billing_account_id: str,
        grain: Literal["daily", "monthly"],
    ) -> ReservationSummaryResponse:
        """Call the Consumption API and return a parsed response envelope."""
        url = (
            "https://management.azure.com"
            f"/providers/Microsoft.Billing/billingAccounts/{billing_account_id}"
            "/providers/Microsoft.Consumption/reservationSummaries"
            f"?grain={grain}&api-version={RESERVATION_API_VERSION}"
        )

        try:
            token = self._get_bearer_token(azure_tenant_id)
            raw_items = await self._call_api(url=url, bearer_token=token)
        except (ReservationAuthError, ReservationForbiddenError, ReservationRateLimitError):
            raise
        except Exception as exc:
            logger.error(
                "ReservationService: unexpected error fetching summaries for "
                "billing account %s: %s",
                billing_account_id,
                exc,
                exc_info=True,
            )
            raise ReservationServiceError(f"Failed to fetch reservation summaries: {exc}") from exc

        summaries = self._parse_items(raw_items)
        return ReservationSummaryResponse.from_api_rows(summaries, grain=grain)

    def _get_bearer_token(self, azure_tenant_id: str) -> str:
        """Obtain a bearer token for the Azure management plane."""
        credential = azure_client_manager.get_credential(azure_tenant_id)
        token = credential.get_token("https://management.azure.com/.default")
        return token.token

    async def _call_api(self, url: str, bearer_token: str) -> list[dict[str, Any]]:
        """Execute the HTTP GET and handle error status codes.

        Returns
        -------
        list[dict]
            The ``value`` array from the JSON response (may be empty).

        Raises
        ------
        ReservationAuthError
            On HTTP 401.
        ReservationForbiddenError
            On HTTP 403.
        ReservationServiceError
            On HTTP 404 (no reservations – returns empty list instead).
        ReservationRateLimitError
            On HTTP 429.
        httpx.HTTPStatusError
            On other 4xx/5xx.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {bearer_token}"},
            )

            if resp.status_code == 401:
                logger.error(
                    "ReservationService: 401 Unauthorized – token may be expired "
                    "or lacking billing scope"
                )
                raise ReservationAuthError(
                    "Azure returned 401 Unauthorized for reservationSummaries"
                )

            if resp.status_code == 403:
                logger.error(
                    "ReservationService: 403 Forbidden – service principal lacks "
                    "Cost Management Reader at billing account scope"
                )
                raise ReservationForbiddenError(
                    "Azure returned 403 Forbidden for reservationSummaries. "
                    "Ensure Cost Management Reader is granted at billing account scope."
                )

            if resp.status_code == 404:
                # No reservations exist for this billing account – treat as empty.
                logger.info(
                    "ReservationService: 404 – no reservations found for this billing account"
                )
                return []

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After", "unknown")
                logger.warning(
                    "ReservationService: 429 Rate Limited (Retry-After: %s)", retry_after
                )
                raise ReservationRateLimitError(
                    f"Consumption API rate limit exceeded (Retry-After: {retry_after})"
                )

            resp.raise_for_status()

            payload: dict[str, Any] = resp.json()
            return payload.get("value", [])

    @staticmethod
    def _parse_items(items: list[dict[str, Any]]) -> list[ReservationSummary]:
        """Convert raw Consumption API items into ``ReservationSummary`` objects."""
        result: list[ReservationSummary] = []

        for item in items:
            props: dict[str, Any] = item.get("properties", item)
            try:
                # The Consumption API returns properties with PascalCase keys.
                reserved_hours = float(props.get("reservedHours", 0) or 0)
                used_hours = float(props.get("usedHours", 0) or 0)

                utilization: float
                if reserved_hours > 0:
                    utilization = min(used_hours / reserved_hours * 100.0, 100.0)
                else:
                    utilization = 0.0

                # Parse ISO-8601 date string (may be just YYYY-MM-DD or full datetime).
                raw_date: str = str(props.get("usageDate", "") or "")
                usage_date = date.fromisoformat(raw_date[:10]) if raw_date else date.today()

                result.append(
                    ReservationSummary(
                        reservation_id=str(props.get("reservationId", "")),
                        reservation_order_id=str(props.get("reservationOrderId", "")),
                        sku_name=str(props.get("skuName", "Unknown")),
                        kind=props.get("kind"),
                        used_hours=used_hours,
                        reserved_hours=reserved_hours,
                        utilization_percentage=round(utilization, 4),
                        usage_date=usage_date,
                    )
                )
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning("ReservationService: skipping malformed reservation item: %s", exc)
                continue

        return result
