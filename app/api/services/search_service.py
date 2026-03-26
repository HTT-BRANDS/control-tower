"""
Global Search Service

Provides unified search across all entities in the platform.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import or_
from sqlalchemy.orm import Session


class SearchResultType(Enum):
    TENANT = "tenant"
    USER = "user"
    RESOURCE = "resource"
    ALERT = "alert"
    COMPLIANCE = "compliance"


@dataclass
class SearchResult:
    """Unified search result."""

    id: str
    type: SearchResultType
    title: str
    description: str | None
    url: str
    icon: str | None = None
    metadata: dict | None = None


class SearchService:
    """Global search across all entities."""

    def __init__(self, db: Session):
        self.db = db

    async def search(
        self,
        query: str,
        types: list[SearchResultType] | None = None,
        tenant_id: str | None = None,
        limit: int = 20,
    ) -> list[SearchResult]:
        """
        Search across all entities.

        Args:
            query: Search string
            types: Filter by result types (default: all)
            tenant_id: Filter to specific tenant
            limit: Max results per type
        """
        if not query or len(query) < 2:
            return []

        types = types or list(SearchResultType)

        # Run searches in parallel
        tasks = []

        if SearchResultType.TENANT in types:
            tasks.append(self._search_tenants(query, limit))
        if SearchResultType.USER in types:
            tasks.append(self._search_users(query, tenant_id, limit))
        if SearchResultType.RESOURCE in types:
            tasks.append(self._search_resources(query, tenant_id, limit))
        if SearchResultType.ALERT in types:
            tasks.append(self._search_alerts(query, tenant_id, limit))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten and sort by relevance (simple: alphabetical for now)
        all_results = []
        for result_set in results:
            if isinstance(result_set, list):
                all_results.extend(result_set)

        # Sort by title, take top results
        all_results.sort(key=lambda r: r.title.lower())
        return all_results[:limit]

    async def _search_tenants(self, query: str, limit: int) -> list[SearchResult]:
        """Search tenants by name or code."""
        from app.models.tenant import Tenant

        search = f"%{query}%"
        tenants = (
            self.db.query(Tenant)
            .filter(or_(Tenant.name.ilike(search), Tenant.code.ilike(search)))
            .limit(limit)
            .all()
        )

        return [
            SearchResult(
                id=str(t.id),
                type=SearchResultType.TENANT,
                title=t.name,
                description=f"Code: {t.code}",
                url=f"/tenants/{t.id}",
                icon="building",
            )
            for t in tenants
        ]

    async def _search_users(
        self, query: str, tenant_id: str | None, limit: int
    ) -> list[SearchResult]:
        """Search users by name or email."""
        from app.models.user import User

        search = f"%{query}%"
        q = self.db.query(User).filter(or_(User.name.ilike(search), User.email.ilike(search)))

        if tenant_id:
            q = q.filter(User.tenant_id == tenant_id)

        users = q.limit(limit).all()

        return [
            SearchResult(
                id=str(u.id),
                type=SearchResultType.USER,
                title=u.name,
                description=u.email,
                url=f"/users/{u.id}",
                icon="user",
            )
            for u in users
        ]

    async def _search_resources(
        self, query: str, tenant_id: str | None, limit: int
    ) -> list[SearchResult]:
        """Search Azure resources by name or type."""
        from app.models.resource import Resource

        search = f"%{query}%"
        q = self.db.query(Resource).filter(
            or_(
                Resource.name.ilike(search),
                Resource.type.ilike(search),
                Resource.resource_id.ilike(search),
            )
        )

        if tenant_id:
            q = q.filter(Resource.tenant_id == tenant_id)

        resources = q.limit(limit).all()

        return [
            SearchResult(
                id=str(r.id),
                type=SearchResultType.RESOURCE,
                title=r.name,
                description=f"{r.type} in {r.location}",
                url=f"/resources/{r.id}",
                icon="cloud",
                metadata={"resource_type": r.type, "location": r.location},
            )
            for r in resources
        ]

    async def _search_alerts(
        self, query: str, tenant_id: str | None, limit: int
    ) -> list[SearchResult]:
        """Search alerts by title or description."""
        from app.models.alert import Alert

        search = f"%{query}%"
        q = self.db.query(Alert).filter(
            or_(Alert.title.ilike(search), Alert.description.ilike(search))
        )

        if tenant_id:
            q = q.filter(Alert.tenant_id == tenant_id)

        alerts = q.limit(limit).all()

        return [
            SearchResult(
                id=str(a.id),
                type=SearchResultType.ALERT,
                title=a.title,
                description=a.severity.value if a.severity else None,
                url=f"/alerts/{a.id}",
                icon="alert-triangle",
                metadata={"severity": a.severity.value if a.severity else None},
            )
            for a in alerts
        ]
