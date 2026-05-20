"""Regression tests for ct-d11: /api/v1/costs/summary returned zeros.

Bug: ``CostService.get_cost_summary`` derived ``tenant_count`` from the
set of distinct ``tenant_id``s found in cost snapshots within the
requested window. Sync ran daily but the last successful run was 45
days ago at one point, so the default 30-day summary window contained
zero snapshots — and ``tenant_count`` came back as 0 even though
``/by-tenant`` happily iterated the ``Tenant`` table and returned 5
rows (with zero costs each). The dashboard binds ``tenant_count`` to
a tile labeled "Tenants" which now read 0 — looking like a system
failure rather than a stale-data situation.

Fix: ``tenant_count`` now reflects the SCOPE of the query — the set of
tenant IDs the caller asked about (when ``tenant_ids`` is passed) or
the number of active tenants in the database (when no scope is given).
``/by-tenant`` already used the latter approach, so the two endpoints
now agree. The ``cost_change_percent`` was also tightened: when
``current_total`` is 0 we no longer report -100% (which alarmingly
implies a 100% spend collapse); we return ``None`` so the UI shows
"No prior period data."
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest


def _noop_cache(cache_key):  # pragma: no cover - test fixture
    def decorator(func):
        return func

    return decorator


with patch("app.core.cache.cached", _noop_cache):
    sys.modules.pop("app.api.services.cost_service", None)
    from app.api.services.cost_service import CostService

from app.models.cost import CostSnapshot


def _empty_cost_query() -> MagicMock:
    q = MagicMock()
    q.filter.return_value = q
    q.all.return_value = []
    return q


def _cost_query_with(rows: list) -> MagicMock:
    q = MagicMock()
    q.filter.return_value = q
    q.all.return_value = rows
    return q


def _tenant_count_query(count: int) -> MagicMock:
    q = MagicMock()
    q.filter.return_value = q
    q.count.return_value = count
    return q


@pytest.mark.asyncio
async def test_tenant_count_uses_active_tenant_table_when_no_scope_passed():
    """ct-d11: with no tenant_ids filter, fall back to active Tenant count."""
    mock_db = MagicMock()
    mock_db.query.side_effect = [
        _empty_cost_query(),  # current period
        _empty_cost_query(),  # prev period
        _tenant_count_query(5),  # Tenant fallback
    ]
    result = await CostService(db=mock_db).get_cost_summary(period_days=30)
    assert result.tenant_count == 5
    assert result.total_cost == 0  # window had no data — that's fine
    assert result.cost_change_percent is None


@pytest.mark.asyncio
async def test_tenant_count_honors_explicit_scope():
    """When tenant_ids is provided, the count reflects that explicit scope."""
    mock_db = MagicMock()
    mock_db.query.side_effect = [
        _empty_cost_query(),
        _empty_cost_query(),
        # NOTE: Tenant fallback query MUST NOT be called when tenant_ids passed.
    ]
    result = await CostService(db=mock_db).get_cost_summary(
        period_days=30, tenant_ids=["t1", "t2", "t3"]
    )
    assert result.tenant_count == 3, "explicit scope wins over table count"
    # And we didn't try to consume a third query off the side_effect iterator.


@pytest.mark.asyncio
async def test_change_percent_is_none_when_current_period_has_no_data():
    """ct-d11: -100% is misleading when current period is missing data."""
    today = date.today()
    prev_snaps = []
    for i in range(10):
        snap = MagicMock(spec=CostSnapshot)
        snap.date = today - timedelta(days=30 + i)
        snap.total_cost = 100.0
        snap.tenant_id = "t1"
        snap.subscription_id = "sub-1"
        snap.service_name = "Compute"
        prev_snaps.append(snap)

    mock_db = MagicMock()
    mock_db.query.side_effect = [
        _empty_cost_query(),  # current period — empty (stale sync)
        _cost_query_with(prev_snaps),  # prev period — has data
        _tenant_count_query(5),  # Tenant fallback
    ]
    result = await CostService(db=mock_db).get_cost_summary(period_days=30)
    assert result.total_cost == 0
    assert result.cost_change_percent is None, (
        "current=0 with prev>0 means missing data, not a -100% collapse"
    )


@pytest.mark.asyncio
async def test_change_percent_calculated_normally_when_both_periods_have_data():
    """Sanity: regular case still computes change percent."""
    today = date.today()

    def _make_snaps(days_offset: int, cost: float, n: int = 10):
        snaps = []
        for i in range(n):
            snap = MagicMock(spec=CostSnapshot)
            snap.date = today - timedelta(days=days_offset + i)
            snap.total_cost = cost
            snap.tenant_id = "t1"
            snap.subscription_id = "sub-1"
            snap.service_name = "Compute"
            snaps.append(snap)
        return snaps

    mock_db = MagicMock()
    mock_db.query.side_effect = [
        _cost_query_with(_make_snaps(0, 200.0)),
        _cost_query_with(_make_snaps(30, 100.0)),
        _tenant_count_query(5),
    ]
    result = await CostService(db=mock_db).get_cost_summary(period_days=30)
    assert result.total_cost == 2000.0  # 200 * 10
    assert result.cost_change_percent == 100.0  # doubled
