"""Tenant authorization and access control.

Provides tenant isolation enforcement, user-tenant mappings, and
authorization decorators for multi-tenant access control.
"""

import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.auth import User, get_current_user
from app.core.database import get_db
from app.models.tenant import Tenant, UserTenant

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class TenantAccessError(Exception):
    """Exception raised when user attempts to access unauthorized tenant."""

    def __init__(self, tenant_id: str, user_id: str) -> None:
        self.tenant_id = tenant_id
        self.user_id = user_id
        super().__init__(f"User {user_id} does not have access to tenant {tenant_id}")


def get_user_tenants(
    user: User,
    db: Session,
    include_inactive: bool = False,
) -> list[Tenant]:
    """Get list of tenants the user has access to.

    Args:
        user: The authenticated user
        db: Database session
        include_inactive: Whether to include inactive tenants

    Returns:
        List of accessible tenants
    """
    # Admins can access all tenants
    if "admin" in user.roles:
        query = db.query(Tenant)
        if not include_inactive:
            query = query.filter(Tenant.is_active == True)  # noqa: E712
        return query.all()

    # If user has explicit tenant_ids from token, use those
    if user.tenant_ids:
        query = db.query(Tenant).filter(Tenant.tenant_id.in_(user.tenant_ids))
        if not include_inactive:
            query = query.filter(Tenant.is_active == True)  # noqa: E712
        return query.all()

    # Otherwise, check UserTenant mappings
    query = (
        db.query(Tenant)
        .join(UserTenant, Tenant.id == UserTenant.tenant_id)
        .filter(UserTenant.user_id == user.id)
    )

    if not include_inactive:
        query = query.filter(
            Tenant.is_active == True,  # noqa: E712
            UserTenant.is_active == True,  # noqa: E712
        )

    return query.all()


def get_user_tenant_ids(
    user: User,
    db: Session,
    include_inactive: bool = False,
) -> list[str]:
    """Get list of tenant IDs the user has access to.

    Args:
        user: The authenticated user
        db: Database session
        include_inactive: Whether to include inactive tenants

    Returns:
        List of accessible tenant IDs (Azure tenant IDs)
    """
    tenants = get_user_tenants(user, db, include_inactive)
    return [t.tenant_id for t in tenants]


def validate_tenant_access(
    user: User,
    tenant_id: str,
    db: Session,
    raise_exception: bool = True,
) -> bool:
    """Validate that user has access to a specific tenant.

    Args:
        user: The authenticated user
        tenant_id: The tenant ID to check (Azure tenant ID)
        db: Database session
        raise_exception: Whether to raise exception on failure

    Returns:
        True if user has access, False otherwise (if raise_exception is False)

    Raises:
        TenantAccessError: If user doesn't have access and raise_exception is True
        HTTPException: 403 Forbidden if user doesn't have access
    """
    # Admins have access to all tenants
    if "admin" in user.roles:
        return True

    # Check token-based tenant access
    if user.tenant_ids and tenant_id in user.tenant_ids:
        return True

    # Check database UserTenant mapping
    mapping = (
        db.query(UserTenant)
        .join(Tenant, UserTenant.tenant_id == Tenant.id)
        .filter(
            UserTenant.user_id == user.id,
            Tenant.tenant_id == tenant_id,
            UserTenant.is_active == True,  # noqa: E712
            Tenant.is_active == True,  # noqa: E712
        )
        .first()
    )

    if mapping:
        return True

    if raise_exception:
        logger.warning(f"Tenant access denied: user={user.id}, tenant={tenant_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to tenant {tenant_id}",
        )

    return False


def validate_tenants_access(
    user: User,
    tenant_ids: list[str],
    db: Session,
    raise_exception: bool = True,
) -> bool:
    """Validate that user has access to all specified tenants.

    Args:
        user: The authenticated user
        tenant_ids: List of tenant IDs to check
        db: Database session
        raise_exception: Whether to raise exception on failure

    Returns:
        True if user has access to all tenants

    Raises:
        HTTPException: 403 Forbidden if user lacks access to any tenant
    """
    if not tenant_ids:
        return True

    # Admins have access to all
    if "admin" in user.roles:
        return True

    # Get all accessible tenant IDs
    accessible_tenants = get_user_tenant_ids(user, db)

    # Check each requested tenant
    for tenant_id in tenant_ids:
        if tenant_id not in accessible_tenants:
            if raise_exception:
                logger.warning(
                    f"Bulk tenant access denied: user={user.id}, "
                    f"requested={tenant_id}, accessible={accessible_tenants}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied to tenant {tenant_id}",
                )
            return False

    return True


def filter_query_by_tenants(
    query: Any,
    user: User,
    db: Session,
    tenant_column: str = "tenant_id",
) -> Any:
    """Filter a SQLAlchemy query to only include accessible tenants.

    Args:
        query: SQLAlchemy query object
        user: The authenticated user
        db: Database session
        tenant_column: Name of the tenant_id column

    Returns:
        Filtered query
    """
    # Admins see all data
    if "admin" in user.roles:
        return query

    # Get accessible tenant IDs
    accessible_tenant_ids = get_user_tenant_ids(user, db)

    if not accessible_tenant_ids:
        # User has no tenant access - return empty result
        return query.filter(False)  # noqa: F821

    # Apply tenant filter
    entity_cls = query.column_descriptions[0]["entity"]
    tenant_attr = getattr(entity_cls, tenant_column)
    return query.filter(tenant_attr.in_(accessible_tenant_ids))


def require_tenant_access(tenant_id_param: str = "tenant_id") -> Callable[[F], F]:
    """Decorator to require tenant access for a route handler.

    Usage:
        @router.get("/tenants/{tenant_id}/resources")
        @require_tenant_access("tenant_id")
        async def get_resources(
            tenant_id: str,
            user: User = Depends(get_current_user),
            db: Session = Depends(get_db),
        ):
            ...

    Args:
        tenant_id_param: Name of the parameter containing the tenant ID
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract dependencies from kwargs
            user = kwargs.get("user") or kwargs.get("current_user")
            db = kwargs.get("db") or kwargs.get("session")

            if not user or not db:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Missing user or db dependency for tenant access check",
                )

            # Get tenant ID from kwargs
            tenant_id = kwargs.get(tenant_id_param)
            if tenant_id:
                validate_tenant_access(user, tenant_id, db)

            return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


class TenantAuthorization:
    """Helper class for tenant authorization in route handlers."""

    def __init__(self, user: User, db: Session) -> None:
        self.user = user
        self.db = db
        self._accessible_tenants: list[str] | None = None

    @property
    def accessible_tenant_ids(self) -> list[str]:
        """Get cached list of accessible tenant IDs."""
        if self._accessible_tenants is None:
            self._accessible_tenants = get_user_tenant_ids(self.user, self.db)
        return self._accessible_tenants

    def can_access(self, tenant_id: str) -> bool:
        """Check if user can access a specific tenant."""
        if "admin" in self.user.roles:
            return True
        return tenant_id in self.accessible_tenant_ids

    def validate_access(self, tenant_id: str) -> None:
        """Validate access to a tenant, raising 403 if denied."""
        validate_tenant_access(self.user, tenant_id, self.db)

    def filter_tenant_ids(self, requested_tenants: list[str] | None) -> list[str]:
        """Filter requested tenant IDs to only include accessible ones.

        Args:
            requested_tenants: User-requested tenant IDs (None = all accessible)

        Returns:
            Filtered list of tenant IDs user can access
        """
        if "admin" in self.user.roles:
            return requested_tenants or []

        if not requested_tenants:
            return self.accessible_tenant_ids

        # Filter to only accessible tenants
        return [t for t in requested_tenants if t in self.accessible_tenant_ids]

    def ensure_at_least_one_tenant(self) -> None:
        """Ensure user has access to at least one tenant."""
        if "admin" in self.user.roles:
            return

        if not self.accessible_tenant_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no access to any tenants",
            )


async def get_tenant_authorization(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenantAuthorization:
    """Dependency to get TenantAuthorization helper.

    Usage:
        @router.get("/resources")
        async def get_resources(
            authz: TenantAuthorization = Depends(get_tenant_authorization),
        ):
            tenant_ids = authz.filter_tenant_ids(requested_tenants)
            ...
    """
    return TenantAuthorization(user, db)


# ============================================================================
# Route-level dependencies for common patterns
# ============================================================================


async def validate_tenant_ids_param(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[str] | None:
    """Validate and filter tenant_ids query parameter.

    Returns filtered list of tenant IDs user can access.
    """
    tenant_ids_str = request.query_params.get("tenant_ids")
    if not tenant_ids_str:
        # Return all accessible tenants
        if "admin" in user.roles:
            return None  # Admin sees all
        return get_user_tenant_ids(user, db)

    # Parse tenant_ids
    requested_ids = tenant_ids_str.split(",") if "," in tenant_ids_str else [tenant_ids_str]

    # Validate and filter
    authz = TenantAuthorization(user, db)
    return authz.filter_tenant_ids(requested_ids)
