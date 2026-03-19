"""Chargeback and showback reporting schemas.

Pydantic models for per-tenant cost allocation reports that can be
exported as JSON or CSV.  CO-010.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class CostAllocation(BaseModel):
    """A single cost allocation record for a tenant."""

    tenant_id: str = Field(..., description="Internal tenant ID (FK to tenants.id)")
    resource_type: str | None = Field(None, description="Azure service / meter category")
    resource_group: str | None = Field(None, description="Azure resource group")
    cost_amount: float = Field(..., ge=0, description="Cost amount in the reporting currency")
    currency: str = Field(default="USD", description="ISO 4217 currency code")
    cost_date: date = Field(..., description="Date of the cost record")


class ResourceTypeCost(BaseModel):
    """Cost breakdown for a single resource type (service)."""

    resource_type: str = Field(..., description="Azure service name / meter category")
    cost_amount: float = Field(..., ge=0)
    percentage: float = Field(..., ge=0, le=100, description="Percentage of tenant total")


class ResourceGroupCost(BaseModel):
    """Cost breakdown for a single resource group."""

    resource_group: str = Field(..., description="Azure resource group name")
    cost_amount: float = Field(..., ge=0)
    percentage: float = Field(..., ge=0, le=100, description="Percentage of tenant total")


class ChargebackReport(BaseModel):
    """Complete chargeback report for a single tenant over a date range."""

    tenant_id: str = Field(..., description="Internal tenant ID")
    tenant_name: str = Field(..., description="Human-readable tenant name")
    period_start: date = Field(..., description="Inclusive start of reporting period")
    period_end: date = Field(..., description="Inclusive end of reporting period")
    total_cost: float = Field(..., ge=0, description="Total cost for the period")
    currency: str = Field(default="USD")
    by_resource_type: list[ResourceTypeCost] = Field(
        default_factory=list,
        description="Cost breakdown by Azure service / resource type",
    )
    by_resource_group: list[ResourceGroupCost] = Field(
        default_factory=list,
        description="Cost breakdown by Azure resource group",
    )


class ExportedReport(BaseModel):
    """Container for a chargeback report in a specific export format.

    The ``content`` field holds either:
    * A JSON string (when ``format == "json"``) representing the
      :class:`ChargebackReport` for the tenant, or
    * A UTF-8 CSV string (when ``format == "csv"``) with one row per
      allocation line.

    ``report`` is populated for JSON exports so callers can consume the
    structured data without re-parsing ``content``.
    """

    format: Literal["json", "csv"] = Field(..., description="Export format")
    filename: str = Field(..., description="Suggested download filename")
    content: str = Field(..., description="Serialised report (JSON string or CSV text)")
    report: ChargebackReport | None = Field(
        None,
        description="Structured report object; populated for JSON exports",
    )
