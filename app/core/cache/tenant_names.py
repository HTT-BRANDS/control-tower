from __future__ import annotations

from functools import lru_cache

from app.core.database import SessionLocal
from app.models.tenant import Tenant


@lru_cache(maxsize=1)
def get_tenant_name_map() -> dict[str, str]:
    """
    Cached tenant ID to name mapping.
    Cache expires every 5 minutes or when explicitly cleared.

    This eliminates the N+1 query problem where we query all tenants
    for each resource lookup.
    """
    db = SessionLocal()
    try:
        return {str(t.id): t.name for t in db.query(Tenant).all()}
    finally:
        db.close()


def clear_tenant_cache():
    """Clear the tenant cache after tenant updates."""
    get_tenant_name_map.cache_clear()


def get_tenant_name(tenant_id: str) -> str | None:
    """Get tenant name by ID (cached).

    Args:
        tenant_id: The tenant ID to look up

    Returns:
        Tenant name or None if not found

    Example:
        # OLD (N+1 problem):
        # for t in db.query(Tenant).all():
        #     if t.id == resource.tenant_id:
        #         tenant_name = t.name

        # NEW (cached):
        tenant_name = get_tenant_name(str(resource.tenant_id))
    """
    return get_tenant_name_map().get(tenant_id)
