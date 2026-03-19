"""Identity governance API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.services.azure_ad_admin_service import azure_ad_admin_service
from app.api.services.identity_service import IdentityService
from app.api.services.license_service import LicenseServiceError, license_service
from app.core.auth import get_current_user
from app.core.authorization import (
    TenantAuthorization,
    get_tenant_authorization,
)
from app.core.database import get_db
from app.schemas.identity import (
    GuestAccount,
    IdentitySummary,
    PrivilegedAccount,
    StaleAccount,
)
from app.schemas.license import UserLicense, UserLicenseSummary

router = APIRouter(
    prefix="/api/v1/identity",
    tags=["identity"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/summary", response_model=IdentitySummary)
async def get_identity_summary(
    tenant_ids: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get aggregated identity summary across all tenants.

    Args:
        tenant_ids: Filter by specific tenants
    """
    authz.ensure_at_least_one_tenant()

    # Filter tenant_ids to only accessible ones
    authz.filter_tenant_ids(tenant_ids)

    service = IdentityService(db)
    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)
    return await service.get_identity_summary(tenant_ids=filtered_tenant_ids)


@router.get("/privileged", response_model=list[PrivilegedAccount])
async def get_privileged_accounts(
    tenant_id: str | None = Query(default=None),
    tenant_ids: list[str] | None = Query(default=None),
    risk_level: str | None = Query(default=None, pattern="^(High|Medium|Low)$"),
    mfa_enabled: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="display_name"),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get privileged account details.

    Args:
        tenant_id: Single tenant filter (deprecated, use tenant_ids)
        tenant_ids: Filter by specific tenants
        risk_level: Filter by risk level (High, Medium, Low)
        mfa_enabled: Filter by MFA status
        limit: Maximum results to return
        offset: Pagination offset
        sort_by: Field to sort by
        sort_order: Sort direction (asc or desc)
    """
    authz.ensure_at_least_one_tenant()

    # Validate and filter tenant access
    if tenant_id:
        authz.validate_access(tenant_id)

    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)

    service = IdentityService(db)
    accounts = await service.get_privileged_accounts(tenant_id=tenant_id)

    # Apply tenant isolation
    accessible_tenants = authz.accessible_tenant_ids
    accounts = [
        a
        for a in accounts
        if a.tenant_id in accessible_tenants
        and (not filtered_tenant_ids or a.tenant_id in filtered_tenant_ids)
    ]
    if risk_level:
        accounts = [a for a in accounts if a.risk_level == risk_level]
    if mfa_enabled is not None:
        accounts = [a for a in accounts if a.mfa_enabled == mfa_enabled]

    return accounts[offset : offset + limit]


@router.get("/guests", response_model=list[GuestAccount])
async def get_guest_accounts(
    tenant_id: str | None = Query(default=None),
    tenant_ids: list[str] | None = Query(default=None),
    stale_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get guest account details.

    Args:
        tenant_id: Single tenant filter (deprecated, use tenant_ids)
        tenant_ids: Filter by specific tenants
        stale_only: Only show stale guest accounts
        limit: Maximum results to return
        offset: Pagination offset
    """
    authz.ensure_at_least_one_tenant()

    # Validate and filter tenant access
    if tenant_id:
        authz.validate_access(tenant_id)

    authz.filter_tenant_ids(tenant_ids)

    service = IdentityService(db)
    guests = service.get_guest_accounts(tenant_id=tenant_id, stale_only=stale_only)

    return guests[offset : offset + limit]


@router.get("/stale", response_model=list[StaleAccount])
async def get_stale_accounts(
    days_inactive: int = Query(default=30, ge=7, le=365),
    tenant_id: str | None = Query(default=None),
    tenant_ids: list[str] | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get stale account details.

    Args:
        days_inactive: Days since last activity
        tenant_id: Single tenant filter (deprecated, use tenant_ids)
        tenant_ids: Filter by specific tenants
        limit: Maximum results to return
        offset: Pagination offset
    """
    authz.ensure_at_least_one_tenant()

    # Validate and filter tenant access
    if tenant_id:
        authz.validate_access(tenant_id)

    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)

    service = IdentityService(db)
    stale = service.get_stale_accounts(days_inactive=days_inactive, tenant_id=tenant_id)

    # Apply tenant isolation
    accessible_tenants = authz.accessible_tenant_ids
    stale = [
        s
        for s in stale
        if s.tenant_id in accessible_tenants
        and (not filtered_tenant_ids or s.tenant_id in filtered_tenant_ids)
    ]

    return stale[offset : offset + limit]


@router.get("/trends")
async def get_identity_trends(
    tenant_ids: list[str] | None = Query(default=None),
    days: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get identity metrics trends over time.

    Args:
        tenant_ids: Filter by specific tenants
        days: Number of days of history to analyze

    Returns trends for:
    - MFA adoption rate
    - Guest account count
    - Privileged account count
    - Stale account count
    """
    authz.ensure_at_least_one_tenant()

    # Filter tenant_ids to only accessible ones
    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)

    service = IdentityService(db)
    return await service.get_identity_trends(tenant_ids=filtered_tenant_ids, days=days)


# ============================================================================
# Admin Role and Privileged Access Endpoints
# ============================================================================


@router.get("/admin-roles/summary")
async def get_admin_roles_summary(
    tenant_id: str = Query(..., description="Azure tenant ID"),
    use_cache: bool = Query(default=True, description="Use cached data if available"),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get comprehensive admin role summary for a tenant.

    Returns statistics on:
    - Total directory roles
    - Total role assignments
    - Global admin count
    - Security admin count
    - Privileged role admin count
    - Other admin count
    - Service principals with admin roles
    - PIM assignments

    Args:
        tenant_id: The Azure tenant ID to query
        use_cache: Whether to use cached data
    """
    authz.ensure_at_least_one_tenant()
    authz.validate_access(tenant_id)

    try:
        summary = await azure_ad_admin_service.get_admin_role_summary(
            tenant_id=tenant_id,
            use_cache=use_cache,
        )
        return summary.__dict__
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get admin roles summary: {e}",
        ) from e


@router.get("/admin-roles/privileged-users")
async def get_privileged_users_admin_roles(
    tenant_id: str = Query(..., description="Azure tenant ID"),
    include_pim: bool = Query(default=True, description="Include PIM eligible/active assignments"),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get all privileged users with their admin role assignments.

    Returns users with directory roles including:
    - Global Administrators
    - Security Administrators
    - Privileged Role Administrators
    - Other admin roles

    Args:
        tenant_id: The Azure tenant ID to query
        include_pim: Whether to include PIM assignments
    """
    authz.ensure_at_least_one_tenant()
    authz.validate_access(tenant_id)

    try:
        users = await azure_ad_admin_service.get_privileged_users(
            tenant_id=tenant_id,
            include_pim=include_pim,
        )
        return {
            "tenant_id": tenant_id,
            "count": len(users),
            "users": users,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get privileged users: {e}",
        ) from e


@router.get("/admin-roles/global-admins")
async def get_global_admins(
    tenant_id: str = Query(..., description="Azure tenant ID"),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get all Global Administrators.

    Args:
        tenant_id: The Azure tenant ID to query
    """
    authz.ensure_at_least_one_tenant()
    authz.validate_access(tenant_id)

    try:
        admins = await azure_ad_admin_service.get_global_admins(tenant_id=tenant_id)
        return {
            "tenant_id": tenant_id,
            "count": len(admins),
            "admins": admins,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get global admins: {e}",
        ) from e


@router.get("/admin-roles/security-admins")
async def get_security_admins(
    tenant_id: str = Query(..., description="Azure tenant ID"),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get all Security Administrators.

    Args:
        tenant_id: The Azure tenant ID to query
    """
    authz.ensure_at_least_one_tenant()
    authz.validate_access(tenant_id)

    try:
        admins = await azure_ad_admin_service.get_security_admins(tenant_id=tenant_id)
        return {
            "tenant_id": tenant_id,
            "count": len(admins),
            "admins": admins,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get security admins: {e}",
        ) from e


@router.get("/admin-roles/service-principals")
async def get_privileged_service_principals(
    tenant_id: str = Query(..., description="Azure tenant ID"),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get service principals with admin role assignments.

    Args:
        tenant_id: The Azure tenant ID to query
    """
    authz.ensure_at_least_one_tenant()
    authz.validate_access(tenant_id)

    try:
        sps = await azure_ad_admin_service.get_privileged_service_principals(tenant_id=tenant_id)
        return {
            "tenant_id": tenant_id,
            "count": len(sps),
            "service_principals": sps,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get privileged service principals: {e}",
        ) from e


@router.post("/admin-roles/cache/invalidate")
async def invalidate_admin_roles_cache(
    tenant_id: str = Query(..., description="Azure tenant ID"),
    data_type: str | None = Query(default=None, description="Specific data type to invalidate"),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Invalidate cached admin role data for a tenant.

    Use this endpoint to force a refresh of admin role data.

    Args:
        tenant_id: The Azure tenant ID
        data_type: Optional specific data type to invalidate (roles, assignments, pim, summary)
    """
    authz.ensure_at_least_one_tenant()
    authz.validate_access(tenant_id)

    count = await azure_ad_admin_service.invalidate_cache(
        tenant_id=tenant_id,
        data_type=data_type,
    )
    return {
        "tenant_id": tenant_id,
        "data_type": data_type,
        "cache_entries_invalidated": count,
    }


# ============================================================================
# Per-User License Tracking Endpoints (IG-009)
# ============================================================================


@router.get("/licenses", response_model=list[UserLicenseSummary])
async def list_tenant_licenses(
    tenant_id: str = Query(..., description="Azure tenant ID"),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """List all user license assignments for a tenant.

    Returns an aggregated view of every licensed user in the tenant,
    enriched with SKU part numbers (e.g. 'ENTERPRISEPREMIUM' for E5).
    Uses ``GET /users?$select=assignedLicenses`` plus
    ``GET /subscribedSkus`` for SKU name resolution.

    Args:
        tenant_id: Azure AD tenant ID to query.

    Returns:
        List of UserLicenseSummary objects — one per licensed user.
    """
    authz.ensure_at_least_one_tenant()
    authz.validate_access(tenant_id)

    try:
        summaries = await license_service.list_tenant_licenses(tenant_id=tenant_id)
        return summaries
    except LicenseServiceError as exc:
        if exc.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Graph API authentication failed for tenant {tenant_id}: {exc}",
            ) from exc
        if exc.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Graph API rate limit exceeded: {exc}",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tenant licenses: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tenant licenses: {exc}",
        ) from exc


@router.get("/licenses/{user_id}", response_model=list[UserLicense])
async def get_user_licenses(
    user_id: str,
    tenant_id: str = Query(..., description="Azure tenant ID"),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get license details for a specific user.

    Fetches the full SKU and service-plan breakdown for *user_id* via
    ``GET /users/{user_id}/licenseDetails``.

    Args:
        user_id:   Azure AD object ID of the user.
        tenant_id: Azure AD tenant ID the user belongs to.

    Returns:
        List of UserLicense objects — one per assigned SKU.
    """
    authz.ensure_at_least_one_tenant()
    authz.validate_access(tenant_id)

    try:
        licenses = await license_service.get_user_licenses(
            tenant_id=tenant_id,
            user_id=user_id,
        )
        return licenses
    except LicenseServiceError as exc:
        if exc.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Graph API authentication failed for tenant {tenant_id}: {exc}",
            ) from exc
        if exc.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Graph API rate limit exceeded: {exc}",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch licenses for user {user_id}: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch licenses for user {user_id}: {exc}",
        ) from exc
