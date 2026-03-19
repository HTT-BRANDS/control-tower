"""Chargeback / showback reporting service.

Builds per-tenant cost allocation reports from the existing
:class:`~app.models.cost.CostSnapshot` data that has already been
synchronised from Azure Cost Management.  Does **not** re-call Azure —
it operates entirely on the local database.

CO-010: Chargeback/Showback Reporting.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date

from sqlalchemy.orm import Session

from app.models.cost import CostSnapshot
from app.models.tenant import Tenant
from app.schemas.chargeback import (
    ChargebackReport,
    ExportedReport,
    ResourceGroupCost,
    ResourceTypeCost,
)

logger = logging.getLogger(__name__)

_UNKNOWN_TENANT = "Unknown Tenant"
_UNKNOWN_SERVICE = "Unknown"
_UNKNOWN_RG = "Unknown"


class ChargebackServiceError(Exception):
    """Raised when a chargeback operation cannot be completed."""


class ChargebackService:
    """Service for generating chargeback and showback reports.

    Args:
        db: SQLAlchemy synchronous session (injected via FastAPI ``Depends``).
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_tenant_report(
        self,
        tenant_id: str,
        start_date: date,
        end_date: date,
    ) -> ChargebackReport:
        """Aggregate CostSnapshot records into a chargeback report.

        Queries the local database for all :class:`~app.models.cost.CostSnapshot`
        rows that belong to *tenant_id* and fall within [*start_date*, *end_date*]
        (both inclusive), then groups costs by resource type and resource group.

        Args:
            tenant_id: Internal tenant identifier (``tenants.id`` FK value).
            start_date: Inclusive start of the reporting period.
            end_date: Inclusive end of the reporting period.

        Returns:
            A fully populated :class:`~app.schemas.chargeback.ChargebackReport`.
        """
        if start_date > end_date:
            raise ChargebackServiceError(
                f"start_date ({start_date}) must not be after end_date ({end_date})"
            )

        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        tenant_name = tenant.name if tenant else _UNKNOWN_TENANT

        snapshots = (
            self.db.query(CostSnapshot)
            .filter(
                CostSnapshot.tenant_id == tenant_id,
                CostSnapshot.date >= start_date,
                CostSnapshot.date <= end_date,
            )
            .all()
        )

        total_cost = sum(s.total_cost for s in snapshots)
        currency = snapshots[0].currency if snapshots else "USD"

        by_resource_type = self._aggregate_by_resource_type(snapshots, total_cost)
        by_resource_group = self._aggregate_by_resource_group(snapshots, total_cost)

        return ChargebackReport(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            period_start=start_date,
            period_end=end_date,
            total_cost=round(total_cost, 6),
            currency=currency,
            by_resource_type=by_resource_type,
            by_resource_group=by_resource_group,
        )

    async def export_report(
        self,
        tenant_id: str,
        start_date: date,
        end_date: date,
        format: str = "json",  # noqa: A002  — matches the API parameter name
    ) -> ExportedReport:
        """Return a chargeback report serialised to *format* (``"json"`` or ``"csv"``).

        For ``"json"``: the ``content`` field is a compact JSON string of the
        :class:`~app.schemas.chargeback.ChargebackReport`, and ``report`` is
        also populated for convenient programmatic access.

        For ``"csv"``: the ``content`` field is a CSV string with one allocation
        row per (resource_type, resource_group) combination, suitable for
        spreadsheet import.  ``report`` is set to ``None`` to keep the response
        lean.

        Args:
            tenant_id: Internal tenant identifier.
            start_date: Inclusive period start.
            end_date: Inclusive period end.
            format: ``"json"`` (default) or ``"csv"``.

        Returns:
            :class:`~app.schemas.chargeback.ExportedReport`.

        Raises:
            :class:`ChargebackServiceError`: When *format* is not supported.
        """
        if format not in {"json", "csv"}:
            raise ChargebackServiceError(
                f"Unsupported export format: {format!r}. Must be 'json' or 'csv'."
            )

        report = await self.get_tenant_report(tenant_id, start_date, end_date)
        period_tag = f"{start_date.isoformat()}_{end_date.isoformat()}"
        filename_stem = f"chargeback-{tenant_id}-{period_tag}"

        if format == "json":
            content = report.model_dump_json(indent=2)
            return ExportedReport(
                format="json",
                filename=f"{filename_stem}.json",
                content=content,
                report=report,
            )

        # CSV export
        content = self._build_csv(report)
        return ExportedReport(
            format="csv",
            filename=f"{filename_stem}.csv",
            content=content,
            report=None,
        )

    async def get_multi_tenant_report(
        self,
        tenant_ids: list[str],
        start_date: date,
        end_date: date,
    ) -> list[ChargebackReport]:
        """Produce chargeback reports for multiple tenants (showback view).

        Intended for admin users who need a cross-tenant cost overview.
        Each tenant is processed independently so per-tenant breakdowns
        remain intact.

        Args:
            tenant_ids: List of internal tenant IDs to include.
            start_date: Inclusive period start.
            end_date: Inclusive period end.

        Returns:
            List of :class:`~app.schemas.chargeback.ChargebackReport` sorted by
            *total_cost* descending (highest spender first).
        """
        reports: list[ChargebackReport] = []
        for tid in tenant_ids:
            try:
                report = await self.get_tenant_report(tid, start_date, end_date)
                reports.append(report)
            except ChargebackServiceError:
                logger.warning("Skipping tenant %s during multi-tenant report", tid)

        return sorted(reports, key=lambda r: r.total_cost, reverse=True)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _aggregate_by_resource_type(
        snapshots: list[CostSnapshot],
        total_cost: float,
    ) -> list[ResourceTypeCost]:
        """Group snapshots by service_name and compute percentages."""
        buckets: dict[str, float] = {}
        for snap in snapshots:
            key = snap.service_name or _UNKNOWN_SERVICE
            buckets[key] = buckets.get(key, 0.0) + snap.total_cost

        return sorted(
            [
                ResourceTypeCost(
                    resource_type=name,
                    cost_amount=round(cost, 6),
                    percentage=round((cost / total_cost * 100) if total_cost > 0 else 0.0, 4),
                )
                for name, cost in buckets.items()
            ],
            key=lambda x: x.cost_amount,
            reverse=True,
        )

    @staticmethod
    def _aggregate_by_resource_group(
        snapshots: list[CostSnapshot],
        total_cost: float,
    ) -> list[ResourceGroupCost]:
        """Group snapshots by resource_group and compute percentages."""
        buckets: dict[str, float] = {}
        for snap in snapshots:
            key = snap.resource_group or _UNKNOWN_RG
            buckets[key] = buckets.get(key, 0.0) + snap.total_cost

        return sorted(
            [
                ResourceGroupCost(
                    resource_group=name,
                    cost_amount=round(cost, 6),
                    percentage=round((cost / total_cost * 100) if total_cost > 0 else 0.0, 4),
                )
                for name, cost in buckets.items()
            ],
            key=lambda x: x.cost_amount,
            reverse=True,
        )

    @staticmethod
    def _build_csv(report: ChargebackReport) -> str:
        """Serialise a ChargebackReport to a CSV string.

        Columns: tenant_id, tenant_name, period_start, period_end,
                 dimension, name, cost_amount, percentage, currency.

        Each ``by_resource_type`` and ``by_resource_group`` breakdown item
        becomes its own row.  When there are no breakdowns a single summary
        row is emitted instead.
        """
        output = io.StringIO()
        fieldnames = [
            "tenant_id",
            "tenant_name",
            "period_start",
            "period_end",
            "dimension",
            "name",
            "cost_amount",
            "percentage",
            "currency",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()

        base = {
            "tenant_id": report.tenant_id,
            "tenant_name": report.tenant_name,
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "currency": report.currency,
        }

        if not report.by_resource_type and not report.by_resource_group:
            # Emit a summary-only row when no breakdowns exist
            writer.writerow(
                {
                    **base,
                    "dimension": "total",
                    "name": "total",
                    "cost_amount": report.total_cost,
                    "percentage": 100.0,
                }
            )
        else:
            for item in report.by_resource_type:
                writer.writerow(
                    {
                        **base,
                        "dimension": "resource_type",
                        "name": item.resource_type,
                        "cost_amount": item.cost_amount,
                        "percentage": item.percentage,
                    }
                )
            for item in report.by_resource_group:
                writer.writerow(
                    {
                        **base,
                        "dimension": "resource_group",
                        "name": item.resource_group,
                        "cost_amount": item.cost_amount,
                        "percentage": item.percentage,
                    }
                )

        return output.getvalue()
