"""
Search API Routes

Global search across all entities.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.api.services.search_service import SearchService, SearchResult, SearchResultType

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("/", response_model=List[SearchResult])
async def global_search(
    q: str = Query(..., min_length=2, description="Search query"),
    types: Optional[List[SearchResultType]] = Query(None, description="Filter by types"),
    tenant_id: Optional[str] = Query(None, description="Filter by tenant"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Global search across all entities.
    
    Searches: tenants, users, resources, alerts
    """
    service = SearchService(db)
    return await service.search(q, types, tenant_id, limit)


@router.get("/suggestions")
async def search_suggestions(
    q: str = Query(..., min_length=1, description="Partial search query"),
    limit: int = Query(5, ge=1, le=10),
    db: Session = Depends(get_db)
):
    """
    Quick search suggestions for autocomplete.
    """
    service = SearchService(db)
    results = await service.search(q, limit=limit)
    return [{"id": r.id, "title": r.title, "type": r.type} for r in results]
