"""Unit tests for SearchService.

Tests the global search service logic:
- Empty / too-short query returns []
- Tenant search via mocked db
- Resource search via mocked db
- Alert search via mocked db (with fixed import)
- Type filtering restricts which sub-searches run
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.services.search_service import SearchResult, SearchResultType, SearchService

# ---------------------------------------------------------------------------
# Helpers — mock DB rows
# ---------------------------------------------------------------------------


def _mock_db_chain(return_rows: list) -> MagicMock:
    """Build a mock Session whose chained query returns *return_rows*.

    Supports: db.query(Model).filter(...).limit(...).all()
    and also: db.query(Model).filter(...).filter(...).limit(...).all()
    """
    db = MagicMock()
    q = db.query.return_value
    f1 = q.filter.return_value
    # Second .filter() (for tenant_id) chains to same mock
    f1.filter.return_value = f1
    f1.limit.return_value.all.return_value = return_rows
    return db


def _make_tenant(*, id: str = "t-1", name: str = "Acme Corp", tenant_id: str = "ACME"):
    t = MagicMock()
    t.id = id
    t.name = name
    t.tenant_id = tenant_id
    return t


def _make_resource(
    *,
    id: str = "r-1",
    name: str = "acme-vm-01",
    resource_type: str = "Microsoft.Compute/virtualMachines",
    location: str = "eastus",
    tenant_id: str = "t-1",
):
    r = MagicMock()
    r.id = id
    r.name = name
    r.resource_type = resource_type
    r.location = location
    r.tenant_id = tenant_id
    return r


def _make_alert(
    *,
    id: int = 1,
    title: str = "High CPU Alert",
    message: str = "CPU usage exceeded threshold",
    severity: str = "warning",
    tenant_id: str = "t-1",
):
    a = MagicMock()
    a.id = id
    a.title = title
    a.message = message
    a.severity = severity
    a.tenant_id = tenant_id
    return a


# ---------------------------------------------------------------------------
# Empty / short query  →  early return
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_empty_query_returns_empty():
    """An empty query string returns no results."""
    service = SearchService(MagicMock())
    assert await service.search("") == []


@pytest.mark.asyncio
async def test_search_short_query_returns_empty():
    """A single-character query (< 2 chars) returns no results."""
    service = SearchService(MagicMock())
    assert await service.search("x") == []


# ---------------------------------------------------------------------------
# _search_tenants
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_tenants_by_name():
    """_search_tenants returns TENANT SearchResults from DB rows."""
    db = _mock_db_chain([_make_tenant(id="t-1", name="Acme Corp", tenant_id="ACME")])
    service = SearchService(db)

    results = await service._search_tenants("Acme", limit=20)

    assert len(results) == 1
    r = results[0]
    assert isinstance(r, SearchResult)
    assert r.type == SearchResultType.TENANT
    assert r.title == "Acme Corp"
    assert r.description == "Tenant ID: ACME"
    assert r.url == "/tenants/t-1"
    assert r.icon == "building"


# ---------------------------------------------------------------------------
# _search_resources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_resources():
    """_search_resources returns RESOURCE SearchResults from DB rows."""
    db = _mock_db_chain([_make_resource()])
    service = SearchService(db)

    results = await service._search_resources("vm", tenant_id=None, limit=20)

    assert len(results) == 1
    r = results[0]
    assert r.type == SearchResultType.RESOURCE
    assert r.title == "acme-vm-01"
    assert r.icon == "cloud"
    assert r.metadata["location"] == "eastus"


# ---------------------------------------------------------------------------
# _search_alerts  (uses fixed import from app.models.monitoring)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_alerts():
    """_search_alerts returns ALERT SearchResults with severity description."""
    db = _mock_db_chain([_make_alert(id=7, title="High CPU Alert", severity="critical")])
    service = SearchService(db)

    results = await service._search_alerts("CPU", tenant_id=None, limit=20)

    assert len(results) == 1
    r = results[0]
    assert r.type == SearchResultType.ALERT
    assert r.title == "High CPU Alert"
    assert r.description == "critical"
    assert r.url == "/alerts/7"
    assert r.icon == "alert-triangle"


# ---------------------------------------------------------------------------
# Type filtering — only requested sub-searches execute
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_type_filtering_only_runs_requested_searches():
    """When types=[TENANT], only _search_tenants runs — not resources/alerts."""
    db = MagicMock()
    service = SearchService(db)

    tenant_result = SearchResult(
        id="t-1",
        type=SearchResultType.TENANT,
        title="Acme Corp",
        description="Tenant ID: ACME",
        url="/tenants/t-1",
        icon="building",
    )

    with (
        patch.object(
            service, "_search_tenants", new_callable=AsyncMock, return_value=[tenant_result]
        ) as m_ten,
        patch.object(service, "_search_resources", new_callable=AsyncMock) as m_res,
        patch.object(service, "_search_alerts", new_callable=AsyncMock) as m_alerts,
    ):
        results = await service.search("acme", types=[SearchResultType.TENANT])

    m_ten.assert_awaited_once()
    m_res.assert_not_awaited()
    m_alerts.assert_not_awaited()
    assert len(results) == 1
    assert results[0].type == SearchResultType.TENANT
