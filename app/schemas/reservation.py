"""Pydantic schemas for Reserved Instance Utilization (CO-007).

These models capture the Azure Consumption API reservationSummaries
response and the graceful-degradation envelope used when billing account
scope is not configured.
"""

from __future__ import annotations

from datetime import date as DateType
from typing import Literal

from pydantic import BaseModel, Field

# Single source of truth for the billing-account onboarding message.
# The ReservationService imports this constant so the schema's unavailable()
# classmethod and the service use exactly the same string.
SETUP_INSTRUCTIONS: str = (
    "To enable Reserved Instance utilisation tracking, provide a "
    "billing_account_id in the tenant configuration. "
    "The billing account must be an Enterprise Agreement (EA) or "
    "Microsoft Customer Agreement (MCA) account. "
    "Grant the platform service principal 'Cost Management Reader' at the "
    "billing account scope, then update the tenant record with the billing "
    "account ID (found under Cost Management \u2192 Billing accounts in the "
    "Azure portal)."
)

# ---------------------------------------------------------------------------
# Individual reservation summary entry
# ---------------------------------------------------------------------------


class ReservationSummary(BaseModel):
    """A single reservation utilisation data point from the Consumption API.

    Maps to one item in the ``value`` array of the reservationSummaries
    REST response.
    """

    reservation_id: str = Field(..., description="Azure reservation resource ID")
    reservation_order_id: str = Field(..., description="Reservation order GUID")
    sku_name: str = Field(..., description="Azure SKU name (e.g. Standard_D2s_v3)")
    kind: str | None = Field(None, description="Reservation kind (e.g. Microsoft.Compute)")
    used_hours: float = Field(..., description="Actual consumed hours in the period")
    reserved_hours: float = Field(..., description="Total reserved hours in the period")
    utilization_percentage: float = Field(
        ..., ge=0.0, le=100.0, description="used_hours / reserved_hours × 100"
    )
    usage_date: DateType = Field(
        ..., description="Date of the utilisation record (daily) or period start (monthly)"
    )


# ---------------------------------------------------------------------------
# Aggregate utilisation summary (attached to the response envelope)
# ---------------------------------------------------------------------------


class ReservationUtilizationSummary(BaseModel):
    """Aggregate statistics computed over all returned reservation summaries."""

    total_reservations: int = Field(..., description="Number of distinct reservations")
    avg_utilization_percent: float = Field(..., description="Mean utilisation across all records")
    underutilized_count: int = Field(
        ..., description="Reservations below the underutilisation threshold"
    )
    underutilization_threshold: float = Field(
        default=80.0, description="Threshold (%) below which a reservation is underutilised"
    )


# ---------------------------------------------------------------------------
# Top-level response envelope
# ---------------------------------------------------------------------------


class ReservationSummaryResponse(BaseModel):
    """Reservation utilisation API response.

    ``available`` is the primary signal:
    - ``True``  → billing account scope was reachable; ``summaries`` is populated
    - ``False`` → scope is unavailable; ``reason`` and ``setup_instructions`` explain why
    """

    available: bool = Field(
        ...,
        description="Whether reservation utilisation data is accessible for this tenant",
    )
    grain: Literal["daily", "monthly"] | None = Field(
        None, description="Granularity of the returned summaries"
    )
    summaries: list[ReservationSummary] = Field(
        default_factory=list,
        description="Reservation utilisation records returned by the Consumption API",
    )
    aggregate: ReservationUtilizationSummary | None = Field(
        None, description="Computed aggregate statistics; None when available=False"
    )
    reason: str | None = Field(
        None,
        description="Machine-readable reason code when available=False",
    )
    setup_instructions: str | None = Field(
        None,
        description="Human-readable onboarding guidance when available=False",
    )

    # --- convenience constructors -------------------------------------------

    @classmethod
    def unavailable(
        cls,
        reason: str = "billing_account_access_required",
        setup_instructions: str = SETUP_INSTRUCTIONS,
    ) -> ReservationSummaryResponse:
        """Return a graceful-degradation response with available=False."""
        return cls(
            available=False,
            summaries=[],
            aggregate=None,
            reason=reason,
            setup_instructions=setup_instructions,
        )

    @classmethod
    def from_api_rows(
        cls,
        summaries: list[ReservationSummary],
        grain: Literal["daily", "monthly"],
    ) -> ReservationSummaryResponse:
        """Build a successful response from a list of API rows."""
        agg = _compute_aggregate(summaries)
        return cls(
            available=True,
            grain=grain,
            summaries=summaries,
            aggregate=agg,
        )


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _compute_aggregate(
    summaries: list[ReservationSummary],
    threshold: float = 80.0,
) -> ReservationUtilizationSummary:
    """Compute aggregate statistics over *summaries*."""
    if not summaries:
        return ReservationUtilizationSummary(
            total_reservations=0,
            avg_utilization_percent=0.0,
            underutilized_count=0,
            underutilization_threshold=threshold,
        )

    # Count distinct reservation IDs (not just rows, which may have daily grain)
    distinct_reservations = len({s.reservation_id for s in summaries})
    avg_util = sum(s.utilization_percentage for s in summaries) / len(summaries)
    underutilized = sum(1 for s in summaries if s.utilization_percentage < threshold)

    return ReservationUtilizationSummary(
        total_reservations=distinct_reservations,
        avg_utilization_percent=round(avg_util, 2),
        underutilized_count=underutilized,
        underutilization_threshold=threshold,
    )
