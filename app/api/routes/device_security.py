"""Device Security API routes.

Endpoints for device security features including EDR coverage,
device encryption, asset inventory, compliance scoring, and
non-compliant device alerting.

Traces: RC-031 (EDR coverage), RC-032 (Device encryption), RC-033 (Asset inventory),
        RC-034 (Device compliance), RC-035 (Non-compliant devices)
"""

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.services.device_security_service import (
    DeviceSecurityService,
    get_device_security_service,
)
from app.core.auth import User, get_current_user
from app.core.authorization import (
    TenantAuthorization,
    get_tenant_authorization,
)

router = APIRouter(
    prefix="/api/v1/device-security",
    tags=["device-security"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/edr-coverage")
async def get_edr_coverage(
    current_user: User = Depends(get_current_user),
    tenant_id: str | None = Query(default=None),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
    service: DeviceSecurityService = Depends(get_device_security_service),
) -> dict[str, Any]:
    """Get EDR coverage monitoring data.

    Returns placeholder response indicating feature is coming soon
    when Sui Generis API integration is complete.

    Args:
        tenant_id: Optional tenant ID to filter by

    Returns:
        Dictionary with EDR coverage status and features
    """
    # Ensure user has access to at least one tenant
    authz.ensure_at_least_one_tenant()

    # Filter tenant ID to only those user has access to
    filtered_tenant_id = authz.filter_tenant_ids([tenant_id])[0] if tenant_id else None

    return service.get_edr_coverage(filtered_tenant_id)


@router.get("/encryption")
async def get_device_encryption(
    current_user: User = Depends(get_current_user),
    tenant_id: str | None = Query(default=None),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
    service: DeviceSecurityService = Depends(get_device_security_service),
) -> dict[str, Any]:
    """Get device encryption status.

    Returns placeholder response indicating feature is coming soon
    when Sui Generis API integration is complete.

    Args:
        tenant_id: Optional tenant ID to filter by

    Returns:
        Dictionary with encryption status and features
    """
    # Ensure user has access to at least one tenant
    authz.ensure_at_least_one_tenant()

    # Filter tenant ID to only those user has access to
    filtered_tenant_id = authz.filter_tenant_ids([tenant_id])[0] if tenant_id else None

    return service.get_device_encryption(filtered_tenant_id)


@router.get("/inventory")
async def get_asset_inventory(
    current_user: User = Depends(get_current_user),
    tenant_id: str | None = Query(default=None),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
    service: DeviceSecurityService = Depends(get_device_security_service),
) -> dict[str, Any]:
    """Get asset inventory data.

    Returns placeholder response indicating feature is coming soon
    when Sui Generis API integration is complete.

    Args:
        tenant_id: Optional tenant ID to filter by

    Returns:
        Dictionary with inventory status and features
    """
    # Ensure user has access to at least one tenant
    authz.ensure_at_least_one_tenant()

    # Filter tenant ID to only those user has access to
    filtered_tenant_id = authz.filter_tenant_ids([tenant_id])[0] if tenant_id else None

    return service.get_asset_inventory(filtered_tenant_id)


@router.get("/compliance-score")
async def get_device_compliance_score(
    current_user: User = Depends(get_current_user),
    tenant_id: str | None = Query(default=None),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
    service: DeviceSecurityService = Depends(get_device_security_service),
) -> dict[str, Any]:
    """Get device compliance score.

    Returns placeholder response indicating feature is coming soon
    when Sui Generis API integration is complete.

    Args:
        tenant_id: Optional tenant ID to filter by

    Returns:
        Dictionary with compliance score and features
    """
    # Ensure user has access to at least one tenant
    authz.ensure_at_least_one_tenant()

    # Filter tenant ID to only those user has access to
    filtered_tenant_id = authz.filter_tenant_ids([tenant_id])[0] if tenant_id else None

    return service.get_device_compliance_score(filtered_tenant_id)


@router.get("/non-compliant")
async def get_non_compliant_devices(
    current_user: User = Depends(get_current_user),
    tenant_id: str | None = Query(default=None),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
    service: DeviceSecurityService = Depends(get_device_security_service),
) -> dict[str, Any]:
    """Get non-compliant device alerts.

    Returns placeholder response indicating feature is coming soon
    when Sui Generis API integration is complete.

    Args:
        tenant_id: Optional tenant ID to filter by

    Returns:
        Dictionary with non-compliant device status and features
    """
    # Ensure user has access to at least one tenant
    authz.ensure_at_least_one_tenant()

    # Filter tenant ID to only those user has access to
    filtered_tenant_id = authz.filter_tenant_ids([tenant_id])[0] if tenant_id else None

    return service.get_non_compliant_devices(filtered_tenant_id)
