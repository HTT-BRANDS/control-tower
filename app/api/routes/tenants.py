"""Tenant management API routes.

SECURITY FEATURES:
- UUID validation on all ID parameters
- Strict input validation via Pydantic schemas
- Rate limiting on sensitive endpoints
"""

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.core.auth import User, get_current_user
from app.core.authorization import (
    TenantAuthorization,
    get_tenant_authorization,
    get_user_tenants,
    validate_tenant_access,
)
from app.core.database import get_db
from app.core.rate_limit import rate_limit
from app.models.tenant import Tenant
from app.schemas.tenant import (
    SubscriptionResponse,
    TenantCreate,
    TenantResponse,
    TenantUpdate,
)


def validate_uuid_param(tenant_id: str, param_name: str = "tenant_id") -> str:
    """Validate UUID format for path parameters.

    Args:
        tenant_id: The ID to validate
        param_name: Name for error messages

    Returns:
        The validated UUID (lowercased)

    Raises:
        HTTPException: 400 if invalid format
    """
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{param_name} is required",
        )

    uuid_pattern = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    if not re.match(uuid_pattern, tenant_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{param_name} must be a valid UUID format (e.g., '12345678-1234-1234-1234-123456789abc')",
        )

    return tenant_id.lower()


router = APIRouter(
    prefix="/api/v1/tenants",
    tags=["tenants"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=list[TenantResponse],
    dependencies=[Depends(rate_limit("default"))],
)
async def list_tenants(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """List all tenants the current user has access to."""
    # Get accessible tenants based on user permissions
    accessible_tenants = get_user_tenants(current_user, db, include_inactive=False)

    return [
        TenantResponse(
            id=t.id,
            name=t.name,
            tenant_id=t.tenant_id,
            description=t.description,
            is_active=t.is_active,
            use_lighthouse=t.use_lighthouse,
            subscription_count=len(t.subscriptions),
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in accessible_tenants
    ]


@router.post(
    "",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("auth"))],  # Stricter rate limit for tenant creation
)
async def create_tenant(
    tenant: TenantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new tenant configuration.

    Requires admin role.
    """
    # Only admins can create tenants
    if "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required to create tenants",
        )

    # Check for duplicate tenant_id
    existing = db.query(Tenant).filter(Tenant.tenant_id == tenant.tenant_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant with Azure tenant ID {tenant.tenant_id} already exists",
        )

    db_tenant = Tenant(
        id=str(uuid.uuid4()),
        name=tenant.name,
        tenant_id=tenant.tenant_id,
        client_id=tenant.client_id,
        client_secret_ref=tenant.client_secret_ref,
        description=tenant.description,
        use_lighthouse=tenant.use_lighthouse,
    )
    db.add(db_tenant)
    db.commit()
    db.refresh(db_tenant)

    return TenantResponse(
        id=db_tenant.id,
        name=db_tenant.name,
        tenant_id=db_tenant.tenant_id,
        description=db_tenant.description,
        is_active=db_tenant.is_active,
        use_lighthouse=db_tenant.use_lighthouse,
        subscription_count=0,
        created_at=db_tenant.created_at,
        updated_at=db_tenant.updated_at,
    )


@router.get(
    "/{id}",
    response_model=TenantResponse,
    dependencies=[Depends(rate_limit("default"))],
)
async def get_tenant(
    id: str = Path(
        ...,
        description="Tenant UUID",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get a specific tenant.

    User must have access to the tenant.
    """
    tenant = db.query(Tenant).filter(Tenant.id == id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {id} not found",
        )

    # Validate tenant access
    validate_tenant_access(current_user, tenant.tenant_id, db)

    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        tenant_id=tenant.tenant_id,
        description=tenant.description,
        is_active=tenant.is_active,
        use_lighthouse=tenant.use_lighthouse,
        subscription_count=len(tenant.subscriptions),
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
    )


@router.patch(
    "/{id}",
    response_model=TenantResponse,
    dependencies=[Depends(rate_limit("auth"))],
)
async def update_tenant(
    tenant_update: TenantUpdate,
    id: str = Path(
        ...,
        description="Tenant UUID",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a tenant configuration.

    Requires admin role.
    """
    # Only admins can update tenants
    if "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required to update tenants",
        )

    tenant = db.query(Tenant).filter(Tenant.id == id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {id} not found",
        )

    update_data = tenant_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tenant, field, value)

    db.commit()
    db.refresh(tenant)

    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        tenant_id=tenant.tenant_id,
        description=tenant.description,
        is_active=tenant.is_active,
        use_lighthouse=tenant.use_lighthouse,
        subscription_count=len(tenant.subscriptions),
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
    )


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("auth"))],
)
async def delete_tenant(
    id: str = Path(
        ...,
        description="Tenant UUID",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a tenant configuration.

    Requires admin role.
    """
    # Only admins can delete tenants
    if "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required to delete tenants",
        )

    tenant = db.query(Tenant).filter(Tenant.id == id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {id} not found",
        )

    db.delete(tenant)
    db.commit()


@router.get(
    "/{id}/subscriptions",
    response_model=list[SubscriptionResponse],
    dependencies=[Depends(rate_limit("default"))],
)
async def get_tenant_subscriptions(
    id: str = Path(
        ...,
        description="Tenant UUID",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get subscriptions for a tenant.

    User must have access to the tenant.
    """
    tenant = db.query(Tenant).filter(Tenant.id == id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {id} not found",
        )

    # Validate tenant access
    validate_tenant_access(current_user, tenant.tenant_id, db)

    return [
        SubscriptionResponse(
            id=s.id,
            subscription_id=s.subscription_id,
            display_name=s.display_name,
            state=s.state,
            tenant_id=tenant.id,
            synced_at=s.synced_at,
        )
        for s in tenant.subscriptions
    ]
