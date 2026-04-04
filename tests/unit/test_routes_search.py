"""Unit tests for search API routes.

Tests search endpoints:
- GET /api/v1/search/ with query parameter
- Query min_length validation
- Type filtering parameter
- Tenant filtering
- Limit parameter
- GET /api/v1/search/suggestions endpoint
"""

from unittest.mock import AsyncMock, patch

from app.api.services.search_service import SearchResult, SearchResultType


def _make_results(count: int = 2) -> list[SearchResult]:
    """Helper to build mock SearchResult lists."""
    items = [
        SearchResult(
            id="t-1",
            type=SearchResultType.TENANT,
            title="Acme Corp",
            description="Code: ACME",
            url="/tenants/t-1",
            icon="building",
        ),
        SearchResult(
            id="r-1",
            type=SearchResultType.RESOURCE,
            title="acme-vm-01",
            description="Microsoft.Compute/virtualMachines in eastus",
            url="/resources/r-1",
            icon="cloud",
            metadata={"resource_type": "Microsoft.Compute/virtualMachines", "location": "eastus"},
        ),
    ]
    return items[:count]


# ---------------------------------------------------------------------------
# GET /api/v1/search/
# ---------------------------------------------------------------------------


def test_search_with_query_returns_results(authed_client):
    """GET /api/v1/search/?q=acme returns matching results."""
    mock_results = _make_results(2)

    with patch("app.api.routes.search.SearchService") as MockCls:
        instance = MockCls.return_value
        instance.search = AsyncMock(return_value=mock_results)

        response = authed_client.get("/api/v1/search/?q=acme")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["title"] == "Acme Corp"
    assert data[0]["type"] == "tenant"
    assert data[1]["type"] == "resource"
    instance.search.assert_awaited_once()


def test_search_min_length_validation(authed_client):
    """GET /api/v1/search/?q=a rejects queries shorter than 2 characters."""
    response = authed_client.get("/api/v1/search/?q=a")
    assert response.status_code == 422


def test_search_type_filtering(authed_client):
    """GET /api/v1/search/?q=acme&types=tenant passes type filter to service."""
    with patch("app.api.routes.search.SearchService") as MockCls:
        instance = MockCls.return_value
        instance.search = AsyncMock(return_value=_make_results(1))

        response = authed_client.get("/api/v1/search/?q=acme&types=tenant")

    assert response.status_code == 200
    # Verify SearchService.search was called with the type filter
    call_args, call_kwargs = instance.search.call_args
    # positional: (query, types, tenant_id, limit)
    assert call_args[0] == "acme"
    types_arg = call_args[1]
    assert types_arg is not None
    assert SearchResultType.TENANT in types_arg


def test_search_tenant_filtering(authed_client):
    """GET /api/v1/search/?q=vm&tenant_id=t-1 passes tenant filter to service."""
    with patch("app.api.routes.search.SearchService") as MockCls:
        instance = MockCls.return_value
        instance.search = AsyncMock(return_value=[])

        response = authed_client.get("/api/v1/search/?q=vm&tenant_id=t-1")

    assert response.status_code == 200
    call_args, _ = instance.search.call_args
    assert call_args[2] == "t-1"  # tenant_id positional arg


def test_search_limit_parameter(authed_client):
    """GET /api/v1/search/?q=acme&limit=5 passes custom limit to service."""
    with patch("app.api.routes.search.SearchService") as MockCls:
        instance = MockCls.return_value
        instance.search = AsyncMock(return_value=_make_results(1))

        response = authed_client.get("/api/v1/search/?q=acme&limit=5")

    assert response.status_code == 200
    call_args, _ = instance.search.call_args
    assert call_args[3] == 5  # limit positional arg


# ---------------------------------------------------------------------------
# GET /api/v1/search/suggestions
# ---------------------------------------------------------------------------


def test_suggestions_returns_compact_results(authed_client):
    """GET /api/v1/search/suggestions?q=ac returns id/title/type dicts."""
    mock_results = _make_results(2)

    with patch("app.api.routes.search.SearchService") as MockCls:
        instance = MockCls.return_value
        instance.search = AsyncMock(return_value=mock_results)

        response = authed_client.get("/api/v1/search/suggestions?q=ac")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Suggestions only contain id, title, type
    for item in data:
        assert set(item.keys()) == {"id", "title", "type"}
    assert data[0]["id"] == "t-1"
    assert data[0]["title"] == "Acme Corp"
