"""Tenant data synchronization utilities."""


async def sync_tenant_data(tenant_id: str):
    """Trigger async data sync for a tenant.

    Args:
        tenant_id: The tenant ID to sync.
    """
    from app.core.scheduler import get_scheduler

    scheduler = get_scheduler()
    if scheduler:
        # Queue sync job
        scheduler.add_job(
            func=lambda: None, trigger="date", id=f"sync-tenant-{tenant_id}", replace_existing=True
        )
