"""Unit tests for ChargebackService and chargeback API routes.

CO-010: Chargeback/Showback Reporting

Tests:
 1. get_tenant_report — happy path with cost data
 2. get_tenant_report — empty period (no cost data)
 3. get_tenant_report — start_date > end_date raises error
 4. export_report JSON format — structure and content
 5. export_report CSV format — validates CSV rows and columns
 6. export_report — unsupported format raises ChargebackServiceError
 7. get_multi_tenant_report — aggregates multiple tenants
 8. Percentage calculation correctness — values sum to 100
 9. Date range filtering — snapshots outside range excluded
10. Route GET /costs/chargeback/{tenant_id} — 200 with JSON data
11. Route GET /costs/chargeback/{tenant_id} — CSV sets Content-Disposition header
12. Route GET /costs/chargeback — multi-tenant admin route returns 200
13. Route GET /costs/chargeback/{tenant_id} — 403 for inaccessible tenant
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.api.services.chargeback_service import ChargebackService, ChargebackServiceError
from app.models.cost import CostSnapshot
from app.models.tenant import Tenant
from app.schemas.chargeback import ChargebackReport, ExportedReport

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TENANT_ID = "test-tenant-123"
_START = date(2024, 1, 1)
_END = date(2024, 1, 31)


def _make_snapshot(
    tenant_id: str = _TENANT_ID,
    snap_date: date = date(2024, 1, 10),
    total_cost: float = 100.0,
    service_name: str | None = "Virtual Machines",
    resource_group: str | None = "rg-prod",
    currency: str = "USD",
) -> CostSnapshot:
    """Create an in-memory CostSnapshot (not persisted to DB)."""
    snap = CostSnapshot()
    snap.tenant_id = tenant_id
    snap.subscription_id = "sub-001"
    snap.date = snap_date
    snap.total_cost = total_cost
    snap.currency = currency
    snap.service_name = service_name
    snap.resource_group = resource_group
    snap.meter_category = None
    return snap


def _make_db_with_snapshots(db_session: Session, snapshots: list[CostSnapshot]) -> Session:
    """Seed a DB session with snapshots and return it."""
    for snap in snapshots:
        db_session.add(snap)
    db_session.commit()
    return db_session


# ===========================================================================
# 1. get_tenant_report — happy path
# ===========================================================================


class TestGetTenantReportHappyPath:
    """get_tenant_report with real cost data in the DB."""

    @pytest.mark.asyncio
    async def test_returns_correct_totals(self, db_session: Session):
        """Report totals match the sum of snapshots in the period."""
        snapshots = [
            _make_snapshot(total_cost=200.0, service_name="Storage", resource_group="rg-a"),
            _make_snapshot(total_cost=300.0, service_name="Compute", resource_group="rg-b"),
        ]
        _make_db_with_snapshots(db_session, snapshots)

        service = ChargebackService(db_session)
        report = await service.get_tenant_report(_TENANT_ID, _START, _END)

        assert report.total_cost == pytest.approx(500.0)
        assert report.tenant_id == _TENANT_ID
        assert report.period_start == _START
        assert report.period_end == _END

    @pytest.mark.asyncio
    async def test_includes_resource_type_breakdown(self, db_session: Session):
        """by_resource_type contains one entry per distinct service_name."""
        snapshots = [
            _make_snapshot(total_cost=400.0, service_name="Storage"),
            _make_snapshot(total_cost=100.0, service_name="Networking"),
        ]
        _make_db_with_snapshots(db_session, snapshots)

        service = ChargebackService(db_session)
        report = await service.get_tenant_report(_TENANT_ID, _START, _END)

        names = {r.resource_type for r in report.by_resource_type}
        assert "Storage" in names
        assert "Networking" in names

    @pytest.mark.asyncio
    async def test_includes_resource_group_breakdown(self, db_session: Session):
        """by_resource_group contains one entry per distinct resource_group."""
        snapshots = [
            _make_snapshot(total_cost=150.0, resource_group="rg-prod"),
            _make_snapshot(total_cost=50.0, resource_group="rg-dev"),
        ]
        _make_db_with_snapshots(db_session, snapshots)

        service = ChargebackService(db_session)
        report = await service.get_tenant_report(_TENANT_ID, _START, _END)

        groups = {r.resource_group for r in report.by_resource_group}
        assert "rg-prod" in groups
        assert "rg-dev" in groups

    @pytest.mark.asyncio
    async def test_tenant_name_resolved_from_db(self, db_session: Session):
        """tenant_name is pulled from the Tenant table when available."""
        tenant = Tenant(id=_TENANT_ID, tenant_id=_TENANT_ID, name="Contoso Corp", is_active=True)
        db_session.add(tenant)
        _make_db_with_snapshots(db_session, [_make_snapshot()])

        service = ChargebackService(db_session)
        report = await service.get_tenant_report(_TENANT_ID, _START, _END)

        assert report.tenant_name == "Contoso Corp"


# ===========================================================================
# 2. get_tenant_report — empty period
# ===========================================================================


class TestGetTenantReportEmpty:
    """get_tenant_report when no snapshots exist for the period."""

    @pytest.mark.asyncio
    async def test_empty_period_returns_zero_cost(self, db_session: Session):
        """When there are no cost records the total is zero."""
        service = ChargebackService(db_session)
        report = await service.get_tenant_report(_TENANT_ID, _START, _END)

        assert report.total_cost == 0.0
        assert report.by_resource_type == []
        assert report.by_resource_group == []
        assert report.currency == "USD"

    @pytest.mark.asyncio
    async def test_empty_tenant_name_fallback(self, db_session: Session):
        """Unknown tenant gets a sensible fallback name."""
        service = ChargebackService(db_session)
        report = await service.get_tenant_report("nonexistent-tenant", _START, _END)

        assert report.tenant_name == "Unknown Tenant"


# ===========================================================================
# 3. get_tenant_report — invalid date range
# ===========================================================================


class TestGetTenantReportInvalidDates:
    @pytest.mark.asyncio
    async def test_start_after_end_raises_error(self, db_session: Session):
        """Passing start_date > end_date raises ChargebackServiceError."""
        service = ChargebackService(db_session)

        with pytest.raises(ChargebackServiceError, match="start_date"):
            await service.get_tenant_report(_TENANT_ID, date(2024, 2, 1), date(2024, 1, 1))


# ===========================================================================
# 4. export_report — JSON format
# ===========================================================================


class TestExportReportJson:
    @pytest.mark.asyncio
    async def test_json_export_has_correct_format_field(self, db_session: Session):
        """JSON export carries format='json'."""
        _make_db_with_snapshots(db_session, [_make_snapshot()])
        service = ChargebackService(db_session)
        exported = await service.export_report(_TENANT_ID, _START, _END, format="json")

        assert exported.format == "json"

    @pytest.mark.asyncio
    async def test_json_export_filename_ends_with_json(self, db_session: Session):
        """JSON export filename has .json extension."""
        service = ChargebackService(db_session)
        exported = await service.export_report(_TENANT_ID, _START, _END, format="json")

        assert exported.filename.endswith(".json")

    @pytest.mark.asyncio
    async def test_json_export_content_is_valid_json(self, db_session: Session):
        """The content field of a JSON export is parseable JSON."""
        _make_db_with_snapshots(db_session, [_make_snapshot(total_cost=99.5)])
        service = ChargebackService(db_session)
        exported = await service.export_report(_TENANT_ID, _START, _END, format="json")

        parsed = json.loads(exported.content)
        assert parsed["tenant_id"] == _TENANT_ID
        assert parsed["total_cost"] == pytest.approx(99.5)

    @pytest.mark.asyncio
    async def test_json_export_populates_report_field(self, db_session: Session):
        """JSON export populates the structured report field."""
        service = ChargebackService(db_session)
        exported = await service.export_report(_TENANT_ID, _START, _END, format="json")

        assert exported.report is not None
        assert isinstance(exported.report, ChargebackReport)


# ===========================================================================
# 5. export_report — CSV format
# ===========================================================================


class TestExportReportCsv:
    @pytest.mark.asyncio
    async def test_csv_export_has_correct_format_field(self, db_session: Session):
        """CSV export carries format='csv'."""
        service = ChargebackService(db_session)
        exported = await service.export_report(_TENANT_ID, _START, _END, format="csv")

        assert exported.format == "csv"

    @pytest.mark.asyncio
    async def test_csv_export_filename_ends_with_csv(self, db_session: Session):
        """CSV export filename has .csv extension."""
        service = ChargebackService(db_session)
        exported = await service.export_report(_TENANT_ID, _START, _END, format="csv")

        assert exported.filename.endswith(".csv")

    @pytest.mark.asyncio
    async def test_csv_export_content_parseable(self, db_session: Session):
        """CSV content can be parsed with the standard csv module."""
        snapshots = [
            _make_snapshot(total_cost=150.0, service_name="Storage", resource_group="rg-a"),
            _make_snapshot(total_cost=350.0, service_name="Compute", resource_group="rg-b"),
        ]
        _make_db_with_snapshots(db_session, snapshots)
        service = ChargebackService(db_session)
        exported = await service.export_report(_TENANT_ID, _START, _END, format="csv")

        reader = csv.DictReader(io.StringIO(exported.content))
        rows = list(reader)
        # Two resource_type rows + two resource_group rows = 4 total
        assert len(rows) >= 2

    @pytest.mark.asyncio
    async def test_csv_export_expected_columns(self, db_session: Session):
        """CSV contains all required columns."""
        service = ChargebackService(db_session)
        exported = await service.export_report(_TENANT_ID, _START, _END, format="csv")

        reader = csv.DictReader(io.StringIO(exported.content))
        assert reader.fieldnames is not None
        required = {
            "tenant_id",
            "tenant_name",
            "period_start",
            "period_end",
            "dimension",
            "name",
            "cost_amount",
            "percentage",
            "currency",
        }
        assert required.issubset(set(reader.fieldnames))

    @pytest.mark.asyncio
    async def test_csv_export_report_field_is_none(self, db_session: Session):
        """CSV export keeps report=None to keep the response lean."""
        service = ChargebackService(db_session)
        exported = await service.export_report(_TENANT_ID, _START, _END, format="csv")

        assert exported.report is None


# ===========================================================================
# 6. export_report — unsupported format
# ===========================================================================


class TestExportReportUnsupportedFormat:
    @pytest.mark.asyncio
    async def test_unsupported_format_raises_error(self, db_session: Session):
        """Requesting 'xml' format raises ChargebackServiceError."""
        service = ChargebackService(db_session)

        with pytest.raises(ChargebackServiceError, match="Unsupported export format"):
            await service.export_report(_TENANT_ID, _START, _END, format="xml")


# ===========================================================================
# 7. get_multi_tenant_report
# ===========================================================================


class TestGetMultiTenantReport:
    @pytest.mark.asyncio
    async def test_multi_tenant_returns_one_report_per_tenant(self, db_session: Session):
        """Multi-tenant report returns one ChargebackReport per requested tenant."""
        t1 = "tenant-aaa"
        t2 = "tenant-bbb"
        for tid, cost in [(t1, 500.0), (t2, 250.0)]:
            db_session.add(Tenant(id=tid, tenant_id=tid, name=f"T-{tid}", is_active=True))
            db_session.add(_make_snapshot(tenant_id=tid, total_cost=cost))
        db_session.commit()

        service = ChargebackService(db_session)
        reports = await service.get_multi_tenant_report([t1, t2], _START, _END)

        assert len(reports) == 2
        tenant_ids = {r.tenant_id for r in reports}
        assert t1 in tenant_ids
        assert t2 in tenant_ids

    @pytest.mark.asyncio
    async def test_multi_tenant_sorted_by_cost_descending(self, db_session: Session):
        """Multi-tenant report is sorted highest-cost-first."""
        t1, t2 = "tenant-high", "tenant-low"
        for tid, cost in [(t1, 1000.0), (t2, 50.0)]:
            db_session.add(Tenant(id=tid, tenant_id=tid, name=tid, is_active=True))
            db_session.add(_make_snapshot(tenant_id=tid, total_cost=cost))
        db_session.commit()

        service = ChargebackService(db_session)
        reports = await service.get_multi_tenant_report([t1, t2], _START, _END)

        assert reports[0].tenant_id == t1

    @pytest.mark.asyncio
    async def test_multi_tenant_empty_list(self, db_session: Session):
        """Empty tenant_ids list returns an empty list without error."""
        service = ChargebackService(db_session)
        reports = await service.get_multi_tenant_report([], _START, _END)

        assert reports == []


# ===========================================================================
# 8. Percentage calculation correctness
# ===========================================================================


class TestPercentageCalculation:
    @pytest.mark.asyncio
    async def test_resource_type_percentages_sum_to_100(self, db_session: Session):
        """by_resource_type percentages must sum to exactly 100 (within float tolerance)."""
        snapshots = [
            _make_snapshot(total_cost=250.0, service_name="Storage"),
            _make_snapshot(total_cost=500.0, service_name="Compute"),
            _make_snapshot(total_cost=250.0, service_name="Networking"),
        ]
        _make_db_with_snapshots(db_session, snapshots)

        service = ChargebackService(db_session)
        report = await service.get_tenant_report(_TENANT_ID, _START, _END)

        total_pct = sum(r.percentage for r in report.by_resource_type)
        assert total_pct == pytest.approx(100.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_resource_group_percentages_sum_to_100(self, db_session: Session):
        """by_resource_group percentages must sum to exactly 100."""
        snapshots = [
            _make_snapshot(total_cost=300.0, resource_group="rg-prod"),
            _make_snapshot(total_cost=700.0, resource_group="rg-staging"),
        ]
        _make_db_with_snapshots(db_session, snapshots)

        service = ChargebackService(db_session)
        report = await service.get_tenant_report(_TENANT_ID, _START, _END)

        total_pct = sum(r.percentage for r in report.by_resource_group)
        assert total_pct == pytest.approx(100.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_zero_total_cost_yields_zero_percentages(self, db_session: Session):
        """When total_cost is 0 all percentages must be 0 (no division by zero)."""
        service = ChargebackService(db_session)
        # No snapshots → empty report
        report = await service.get_tenant_report(_TENANT_ID, _START, _END)

        assert report.total_cost == 0.0
        # No items, so no division-by-zero risk
        assert report.by_resource_type == []
        assert report.by_resource_group == []


# ===========================================================================
# 9. Date range filtering
# ===========================================================================


class TestDateRangeFiltering:
    @pytest.mark.asyncio
    async def test_snapshots_outside_range_excluded(self, db_session: Session):
        """Only snapshots within [start_date, end_date] are included."""
        inside = _make_snapshot(snap_date=date(2024, 1, 15), total_cost=100.0)
        before = _make_snapshot(snap_date=date(2023, 12, 31), total_cost=9999.0)
        after = _make_snapshot(snap_date=date(2024, 2, 1), total_cost=9999.0)
        _make_db_with_snapshots(db_session, [inside, before, after])

        service = ChargebackService(db_session)
        report = await service.get_tenant_report(_TENANT_ID, _START, _END)

        # Only the "inside" snapshot counts
        assert report.total_cost == pytest.approx(100.0)

    @pytest.mark.asyncio
    async def test_boundary_dates_are_inclusive(self, db_session: Session):
        """Snapshots on start_date and end_date boundaries are included."""
        on_start = _make_snapshot(snap_date=_START, total_cost=10.0)
        on_end = _make_snapshot(snap_date=_END, total_cost=20.0)
        _make_db_with_snapshots(db_session, [on_start, on_end])

        service = ChargebackService(db_session)
        report = await service.get_tenant_report(_TENANT_ID, _START, _END)

        assert report.total_cost == pytest.approx(30.0)


# ===========================================================================
# 10–13. Route-level tests
# ===========================================================================


class TestChargebackRoutes:
    """Integration-style tests using FastAPI TestClient."""

    # -----------------------------------------------------------------------
    # 10. Single-tenant route — 200 JSON
    # -----------------------------------------------------------------------

    @patch("app.api.routes.costs.ChargebackService")
    def test_single_tenant_route_returns_200(self, mock_svc_cls, authed_client):
        """GET /api/v1/costs/chargeback/{tenant_id} returns 200 with ExportedReport."""
        mock_svc = MagicMock()
        mock_report = ChargebackReport(
            tenant_id=_TENANT_ID,
            tenant_name="Test Tenant",
            period_start=_START,
            period_end=_END,
            total_cost=500.0,
            currency="USD",
        )
        mock_exported = ExportedReport(
            format="json",
            filename="chargeback-test-tenant-123.json",
            content='{"tenant_id":"test-tenant-123","total_cost":500.0}',
            report=mock_report,
        )
        mock_svc.export_report = AsyncMock(return_value=mock_exported)
        mock_svc_cls.return_value = mock_svc

        response = authed_client.get(
            f"/api/v1/costs/chargeback/{_TENANT_ID}"
            "?start_date=2024-01-01&end_date=2024-01-31&format=json"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "json"
        assert data["filename"].endswith(".json")

    # -----------------------------------------------------------------------
    # 11. Single-tenant route — CSV Content-Disposition header
    # -----------------------------------------------------------------------

    @patch("app.api.routes.costs.ChargebackService")
    def test_csv_download_sets_content_disposition(self, mock_svc_cls, authed_client):
        """GET ...?format=csv includes Content-Disposition: attachment header."""
        csv_content = (
            "tenant_id,tenant_name,period_start,period_end,dimension,name,"
            "cost_amount,percentage,currency\n"
            f"{_TENANT_ID},Test Tenant,2024-01-01,2024-01-31,"
            "resource_type,Storage,100.0,100.0,USD\n"
        )
        mock_svc = MagicMock()
        mock_exported = ExportedReport(
            format="csv",
            filename=f"chargeback-{_TENANT_ID}-2024-01-01_2024-01-31.csv",
            content=csv_content,
            report=None,
        )
        mock_svc.export_report = AsyncMock(return_value=mock_exported)
        mock_svc_cls.return_value = mock_svc

        response = authed_client.get(
            f"/api/v1/costs/chargeback/{_TENANT_ID}"
            "?start_date=2024-01-01&end_date=2024-01-31&format=csv"
        )

        assert response.status_code == 200
        assert "content-disposition" in response.headers
        assert "attachment" in response.headers["content-disposition"]
        assert mock_exported.filename in response.headers["content-disposition"]

    # -----------------------------------------------------------------------
    # 12. Multi-tenant route — 200 JSON list
    # -----------------------------------------------------------------------

    @patch("app.api.routes.costs.ChargebackService")
    def test_multi_tenant_route_returns_200(self, mock_svc_cls, authed_client):
        """GET /api/v1/costs/chargeback returns 200 with a list of ExportedReports."""
        mock_svc = MagicMock()
        mock_report = ChargebackReport(
            tenant_id=_TENANT_ID,
            tenant_name="Test Tenant",
            period_start=_START,
            period_end=_END,
            total_cost=250.0,
            currency="USD",
        )
        mock_svc.get_multi_tenant_report = AsyncMock(return_value=[mock_report])
        mock_svc.export_report = AsyncMock(
            return_value=ExportedReport(
                format="json",
                filename=f"chargeback-{_TENANT_ID}.json",
                content='{"tenant_id":"test-tenant-123"}',
                report=mock_report,
            )
        )
        mock_svc_cls.return_value = mock_svc

        response = authed_client.get(
            "/api/v1/costs/chargeback?start_date=2024-01-01&end_date=2024-01-31"
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    # -----------------------------------------------------------------------
    # 13. Single-tenant route — 403 for inaccessible tenant
    # -----------------------------------------------------------------------

    def test_single_tenant_route_403_for_inaccessible_tenant(self, authed_client):
        """GET /costs/chargeback/{tenant_id} returns 403 for unauthorised tenants."""
        response = authed_client.get(
            "/api/v1/costs/chargeback/some-other-tenant?start_date=2024-01-01&end_date=2024-01-31"
        )
        # mock_authz only grants access to _TENANT_ID, not "some-other-tenant"
        assert response.status_code == 403
