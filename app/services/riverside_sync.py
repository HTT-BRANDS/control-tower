"""Azure sync services for Riverside compliance data.

This module provides comprehensive Azure synchronization services for Riverside
Company compliance tracking, integrating with Microsoft Graph API and Azure
collecting data for MFA enrollment, device compliance, requirement status,
and maturity scores.

All functions are async with proper error handling, retry logic, circuit breaker
patterns, and database persistence to riverside tables.
"""

import logging
from datetime import date, datetime
from typing import TYPE_CHECKING

from azure.core.exceptions import HttpResponseError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.circuit_breaker import RIVERSIDE_SYNC_BREAKER, CircuitBreakerError, circuit_breaker
from app.core.database import get_db_context
from app.core.retry import RIVERSIDE_SYNC_POLICY, retry_with_backoff
from app.models.riverside import (
    RequirementPriority,
    RequirementStatus,
    RiversideCompliance,
    RiversideDeviceCompliance,
    RiversideMFA,
    RiversideRequirement,
)
from app.models.tenant import Tenant

if TYPE_CHECKING:
    pass

# Import constant from graph_client (safe, no circular dependency)
from app.api.services.graph_client import ADMIN_ROLE_TEMPLATE_IDS

# Lazy imports to avoid circular dependency issues
_graph_client = None
_monitoring_service = None


def _get_graph_client(tenant_id: str):
    """Get GraphClient instance lazily to avoid circular imports."""
    global _graph_client
    if _graph_client is None:
        from app.api.services.graph_client import GraphClient

        _graph_client = GraphClient
    return _graph_client(tenant_id)


def _get_monitoring_service(db):
    """Get MonitoringService instance lazily to avoid circular imports."""
    from app.api.services.monitoring_service import MonitoringService

    return MonitoringService(db)


logger = logging.getLogger(__name__)

RIVERSIDE_DEADLINE = date(2026, 7, 8)
TARGET_MATURITY_SCORE = 3.0


class SyncError(Exception):
    """Exception raised when sync operations fail."""

    def __init__(self, message: str, tenant_id: str | None = None) -> None:
        """Initialize sync error.

        Args:
            message: Error message
            tenant_id: Optional tenant ID associated with the error
        """
        super().__init__(message)
        self.tenant_id = tenant_id


class ProgressTracker:
    """Track sync progress for batch operations."""

    def __init__(self) -> None:
        """Initialize progress tracker."""
        self.total = 0
        self.completed = 0
        self.failed = 0
        self.errors: list[dict] = []

    def increment_completed(self) -> None:
        """Increment completed count."""
        self.completed += 1

    def increment_failed(self, error: str, tenant_id: str | None = None) -> None:
        """Increment failed count and record error.

        Args:
            error: Error message
            tenant_id: Optional tenant ID associated with the error
        """
        self.failed += 1
        self.errors.append({"tenant_id": tenant_id, "error": error})

    def set_total(self, total: int) -> None:
        """Set total items to process."""
        self.total = total

    @property
    def percentage(self) -> float:
        """Calculate completion percentage."""
        if self.total == 0:
            return 0.0
        return (self.completed + self.failed) / self.total * 100

    def to_dict(self) -> dict:
        """Convert tracker to dictionary."""
        return {
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "percentage": round(self.percentage, 1),
            "errors": self.errors,
        }


@circuit_breaker(RIVERSIDE_SYNC_BREAKER)
@retry_with_backoff(RIVERSIDE_SYNC_POLICY)
async def sync_all_tenants(
    db: Session | None = None,
    skip_failed: bool = True,
    include_mfa: bool = True,
    include_devices: bool = False,  # Disabled by default - Sui Generis integration coming in Phase 2
    include_requirements: bool = True,
    include_maturity: bool = True,
) -> dict:
    """Batch sync Riverside compliance data for all active tenants.

    This function orchestrates the synchronization of all Riverside compliance
    data across all active tenants, including MFA enrollment, device compliance,
    requirement status, and maturity scores.

    Args:
        db: Database session (creates context if None)
        skip_failed: If True, continue with other tenants when one fails
        include_mfa: Whether to sync MFA data
        include_devices: Whether to sync device compliance data
        include_requirements: Whether to sync requirement status
        include_maturity: Whether to sync maturity scores

    Returns:
        Dict with sync results containing:
        - status: overall status ("success", "partial", "failed")
        - tenants_processed: number of tenants processed
        - tenants_failed: number of tenants that failed
        - results: detailed results by sync type
        - progress: progress tracking information
    """
    logger.info(f"Starting batch sync for all tenants at {datetime.utcnow()}")

    progress = ProgressTracker()
    results = {
        "mfa": {},
        "devices": {},
        "requirements": {},
        "maturity": {},
    }

    async def _do_sync(session: Session) -> dict:
        # Start monitoring
        monitoring = _get_monitoring_service(session)
        log_entry = monitoring.start_sync_job(job_type="riverside_batch")
        log_id = log_entry.id

        try:
            # Get all active tenants
            tenants = session.query(Tenant).filter(Tenant.is_active == True).all()  # noqa: E712
            progress.set_total(len(tenants))

            logger.info(f"Found {len(tenants)} active tenants to sync")

            for tenant in tenants:
                tenant_results = {
                    "mfa": None,
                    "devices": None,
                    "requirements": None,
                    "maturity": None,
                }

                try:
                    logger.info(f"Syncing tenant: {tenant.name} ({tenant.tenant_id})")

                    # Sync MFA data
                    if include_mfa:
                        try:
                            mfa_result = await sync_tenant_mfa(tenant.tenant_id, session)
                            tenant_results["mfa"] = mfa_result
                            results["mfa"][tenant.tenant_id] = mfa_result
                        except Exception as e:
                            logger.error(f"MFA sync failed for {tenant.name}: {e}")
                            tenant_results["mfa"] = {"status": "error", "error": str(e)}
                            results["mfa"][tenant.tenant_id] = tenant_results["mfa"]
                            if not skip_failed:
                                raise

                    # Sync device compliance
                    # NOTE: Device sync disabled - Sui Generis MSP integration coming in Phase 2 (Q3 2025)
                    if include_devices:
                        logger.info(
                            f"Device sync skipped for {tenant.name}: "
                            "Sui Generis MSP integration coming in Phase 2 (Q3 2025)"
                        )
                        skipped_result = {
                            "status": "skipped",
                            "message": "Device sync disabled - Sui Generis MSP integration coming in Phase 2 (Q3 2025)",
                        }
                        tenant_results["devices"] = skipped_result
                        results["devices"][tenant.tenant_id] = skipped_result

                    # Sync requirement status
                    if include_requirements:
                        try:
                            req_result = await sync_requirement_status(tenant.tenant_id, session)
                            tenant_results["requirements"] = req_result
                            results["requirements"][tenant.tenant_id] = req_result
                        except Exception as e:
                            logger.error(f"Requirement sync failed for {tenant.name}: {e}")
                            tenant_results["requirements"] = {"status": "error", "error": str(e)}
                            results["requirements"][tenant.tenant_id] = tenant_results[
                                "requirements"
                            ]
                            if not skip_failed:
                                raise

                    # Sync maturity scores
                    if include_maturity:
                        try:
                            maturity_result = await sync_maturity_scores(tenant.tenant_id, session)
                            tenant_results["maturity"] = maturity_result
                            results["maturity"][tenant.tenant_id] = maturity_result
                        except Exception as e:
                            logger.error(f"Maturity sync failed for {tenant.name}: {e}")
                            tenant_results["maturity"] = {"status": "error", "error": str(e)}
                            results["maturity"][tenant.tenant_id] = tenant_results["maturity"]
                            if not skip_failed:
                                raise

                    progress.increment_completed()
                    logger.info(f"Successfully synced tenant: {tenant.name}")

                except Exception as e:
                    progress.increment_failed(str(e), tenant.tenant_id)
                    logger.error(f"Failed to sync tenant {tenant.name}: {e}")
                    if not skip_failed:
                        raise

            # Determine overall status
            if progress.failed == 0:
                status = "success"
            elif progress.completed > 0:
                status = "partial"
            else:
                status = "failed"

            # Complete monitoring
            monitoring.complete_sync_job(
                log_id=log_id,
                status=status,
                error_message=None,
                final_records={
                    "records_processed": progress.completed + progress.failed,
                    "errors_count": progress.failed,
                },
            )

            return {
                "status": status,
                "tenants_processed": progress.completed,
                "tenants_failed": progress.failed,
                "results": results,
                "progress": progress.to_dict(),
            }

        except Exception as e:
            logger.error(f"Batch sync failed: {e}")
            monitoring.complete_sync_job(
                log_id=log_id,
                status="failed",
                error_message=f"Batch sync error: {e!s}",
                final_records={
                    "records_processed": progress.completed + progress.failed,
                    "errors_count": progress.failed + 1,
                },
            )
            raise

    if db:
        return await _do_sync(db)
    else:
        with get_db_context() as session:
            return await _do_sync(session)


@circuit_breaker(RIVERSIDE_SYNC_BREAKER)
@retry_with_backoff(RIVERSIDE_SYNC_POLICY)
async def sync_tenant_mfa(
    tenant_id: str,
    db: Session | None = None,
    snapshot_date: datetime | None = None,
    include_method_details: bool = False,
    batch_size: int = 100,
) -> dict:
    """Sync MFA enrollment data for a specific tenant from Microsoft Graph API.

    Fetches MFA registration status using the new Graph API integration,
    calculates coverage percentages, and tracks admin account MFA protection status.

    This enhanced version uses the new MFA data collection methods from GraphClient
    including paginated queries and detailed authentication method information.

    Args:
        tenant_id: Azure tenant ID to sync
        db: Database session (creates context if None)
        snapshot_date: Optional snapshot date (defaults to now)
        include_method_details: If True, include detailed method breakdown
        batch_size: Number of users per batch for pagination (default 100)

    Returns:
        Dict with MFA sync results:
        - status: "success" or "error"
        - total_users: total user count
        - mfa_enrolled: number of MFA-enrolled users
        - mfa_coverage_pct: MFA coverage percentage
        - admin_accounts: total admin accounts
        - admin_mfa_pct: admin MFA coverage percentage
        - unprotected_users: users without MFA
        - method_breakdown: dict of method types and counts (if include_method_details)
        - users_without_mfa: list of users without MFA (if include_method_details)

    Raises:
        SyncError: If sync fails and circuit breaker/retry exhausted
    """
    snapshot_date = snapshot_date or datetime.utcnow()

    logger.info(
        f"Syncing MFA data for tenant: {tenant_id} (include_details={include_method_details})"
    )

    async def _do_sync(session: Session) -> dict:
        # Get tenant
        tenant = session.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
        if not tenant:
            raise SyncError(f"Tenant {tenant_id} not found", tenant_id)

        try:
            graph_client = _get_graph_client(tenant_id)

            # Get all users with pagination for large tenants
            users = await graph_client.get_users_paginated(batch_size=batch_size)
            total_users = len(users)

            # Get MFA registration details with pagination
            registrations = await graph_client.get_mfa_registration_details_paginated(
                batch_size=batch_size
            )

            # Get directory roles for admin MFA tracking
            directory_roles = await graph_client.get_directory_roles()

            # Build set of admin user IDs
            admin_user_ids: set[str] = set()
            for role in directory_roles:
                role_template_id = role.get("roleTemplateId", "")
                if role_template_id in ADMIN_ROLE_TEMPLATE_IDS:
                    for member in role.get("members", []):
                        user_id = member.get("id")
                        if user_id:
                            admin_user_ids.add(user_id)

            # Build user lookup by UPN
            {u.get("userPrincipalName", "").lower(): u for u in users}

            # Build registration lookup by UPN
            registration_lookup: dict[str, dict] = {
                reg.get("userPrincipalName", "").lower(): reg for reg in registrations
            }

            # Calculate MFA metrics
            mfa_enrolled = 0
            admin_accounts_total = len(admin_user_ids)
            admin_accounts_mfa = 0
            method_breakdown: dict[str, int] = {}
            users_without_mfa: list[dict] = []

            for user in users:
                upn = user.get("userPrincipalName", "").lower()
                user_id = user.get("id", "")
                is_admin = user_id in admin_user_ids

                reg = registration_lookup.get(upn, {})
                is_mfa_registered = reg.get("isMfaRegistered", False)
                methods = reg.get("methodsRegistered", []) if reg else []

                if is_mfa_registered:
                    mfa_enrolled += 1
                    if is_admin:
                        admin_accounts_mfa += 1

                    # Count methods
                    for method in methods:
                        method_type = method.lower() if isinstance(method, str) else str(method)
                        method_breakdown[method_type] = method_breakdown.get(method_type, 0) + 1
                else:
                    if include_method_details or is_admin:
                        users_without_mfa.append(
                            {
                                "user_id": user_id,
                                "user_principal_name": upn,
                                "display_name": user.get("displayName", ""),
                                "is_admin": is_admin,
                            }
                        )

            # Calculate percentages
            mfa_coverage_pct = (mfa_enrolled / total_users * 100) if total_users > 0 else 0.0
            admin_mfa_pct = (
                (admin_accounts_mfa / admin_accounts_total * 100)
                if admin_accounts_total > 0
                else 0.0
            )
            unprotected_users = total_users - mfa_enrolled

            # Check for existing record for today
            existing = (
                session.query(RiversideMFA)
                .filter(
                    RiversideMFA.tenant_id == tenant_id,
                    func.date(RiversideMFA.snapshot_date) == snapshot_date.date(),
                )
                .first()
            )

            if existing:
                # Update existing record
                existing.total_users = total_users
                existing.mfa_enrolled_users = mfa_enrolled
                existing.mfa_coverage_percentage = round(mfa_coverage_pct, 2)
                existing.admin_accounts_total = admin_accounts_total
                existing.admin_accounts_mfa = admin_accounts_mfa
                existing.admin_mfa_percentage = round(admin_mfa_pct, 2)
                existing.unprotected_users = unprotected_users
                existing.snapshot_date = snapshot_date
            else:
                # Create new record
                mfa_record = RiversideMFA(
                    tenant_id=tenant_id,
                    total_users=total_users,
                    mfa_enrolled_users=mfa_enrolled,
                    mfa_coverage_percentage=round(mfa_coverage_pct, 2),
                    admin_accounts_total=admin_accounts_total,
                    admin_accounts_mfa=admin_accounts_mfa,
                    admin_mfa_percentage=round(admin_mfa_pct, 2),
                    unprotected_users=unprotected_users,
                    snapshot_date=snapshot_date,
                )
                session.add(mfa_record)

            session.commit()

            logger.info(
                f"MFA sync completed for {tenant.name}: "
                f"{mfa_coverage_pct:.1f}% coverage, {admin_mfa_pct:.1f}% admin MFA, "
                f"{len(method_breakdown)} method types registered"
            )

            result = {
                "status": "success",
                "total_users": total_users,
                "mfa_enrolled": mfa_enrolled,
                "mfa_coverage_pct": round(mfa_coverage_pct, 2),
                "admin_accounts": admin_accounts_total,
                "admin_mfa_pct": round(admin_mfa_pct, 2),
                "unprotected_users": unprotected_users,
            }

            if include_method_details:
                result["method_breakdown"] = method_breakdown
                result["users_without_mfa"] = users_without_mfa[:100]  # Limit to first 100

            return result

        except HttpResponseError as e:
            error_msg = f"Azure API error syncing MFA: {e.status_code} - {e.message}"
            logger.error(error_msg)
            raise SyncError(error_msg, tenant_id) from e
        except CircuitBreakerError as e:
            error_msg = f"Circuit breaker open for MFA sync: {e}"
            logger.error(error_msg)
            raise SyncError(error_msg, tenant_id) from e
        except Exception as e:
            error_msg = f"Unexpected error syncing MFA: {e}"
            logger.error(error_msg)
            raise SyncError(error_msg, tenant_id) from e

    if db:
        return await _do_sync(db)
    else:
        with get_db_context() as session:
            return await _do_sync(session)


@circuit_breaker(RIVERSIDE_SYNC_BREAKER)
@retry_with_backoff(RIVERSIDE_SYNC_POLICY)
async def sync_tenant_devices(
    tenant_id: str,
    db: Session | None = None,
    snapshot_date: datetime | None = None,
) -> dict:
    """Sync device compliance data for a specific tenant from Microsoft Graph API.

    Fetches device management data from Intune/Endpoint Manager, including
    MDM enrollment, compliance status, and encryption status.

    Args:
        tenant_id: Azure tenant ID to sync
        db: Database session (creates context if None)
        snapshot_date: Optional snapshot date (defaults to now)

    Returns:
        Dict with device sync results:
        - status: "success" or "error"
        - total_devices: total device count
        - compliant_devices: compliant device count
        - compliance_pct: compliance percentage
        - mdm_enrolled: MDM-enrolled device count
        - encrypted_devices: encrypted device count
        - edr_covered: EDR-covered device count

    Raises:
        SyncError: If sync fails and circuit breaker/retry exhausted
    """
    snapshot_date = snapshot_date or datetime.utcnow()

    logger.info(f"Syncing device compliance for tenant: {tenant_id}")

    async def _do_sync(session: Session) -> dict:
        # Get tenant
        tenant = session.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
        if not tenant:
            raise SyncError(f"Tenant {tenant_id} not found", tenant_id)

        try:
            graph_client = _get_graph_client(tenant_id)

            # Get managed devices from Intune via Graph API
            devices_data = await graph_client._request(
                "GET",
                "/deviceManagement/managedDevices",
                params={"$top": 999},
            )
            device_list = devices_data.get("value", [])
            total_devices = len(device_list)

            # Calculate compliance metrics
            compliant_devices = 0
            mdm_enrolled = 0
            encrypted_devices = 0

            MDM_AGENTS = {
                "mdm",
                "easMdm",
                "configurationManagerClientMdm",
                "configurationManagerClientMdmEas",
            }

            for device in device_list:
                # Check compliance state
                if device.get("complianceState") == "compliant":
                    compliant_devices += 1

                # Check MDM enrollment
                if device.get("managementAgent") in MDM_AGENTS:
                    mdm_enrolled += 1

                # Check encryption
                if device.get("isEncrypted"):
                    encrypted_devices += 1

            # For EDR coverage, use compliant devices as proxy
            # (In a real implementation, this would query Defender for Endpoint)
            edr_covered = compliant_devices

            # Calculate compliance percentage
            compliance_pct = (compliant_devices / total_devices * 100) if total_devices > 0 else 0.0

            # Check for existing record for today
            existing = (
                session.query(RiversideDeviceCompliance)
                .filter(
                    RiversideDeviceCompliance.tenant_id == tenant_id,
                    func.date(RiversideDeviceCompliance.snapshot_date) == snapshot_date.date(),
                )
                .first()
            )

            if existing:
                # Update existing record
                existing.total_devices = total_devices
                existing.mdm_enrolled = mdm_enrolled
                existing.edr_covered = edr_covered
                existing.encrypted_devices = encrypted_devices
                existing.compliant_devices = compliant_devices
                existing.compliance_percentage = round(compliance_pct, 2)
                existing.snapshot_date = snapshot_date
            else:
                # Create new record
                device_record = RiversideDeviceCompliance(
                    tenant_id=tenant_id,
                    total_devices=total_devices,
                    mdm_enrolled=mdm_enrolled,
                    edr_covered=edr_covered,
                    encrypted_devices=encrypted_devices,
                    compliant_devices=compliant_devices,
                    compliance_percentage=round(compliance_pct, 2),
                    snapshot_date=snapshot_date,
                )
                session.add(device_record)

            session.commit()

            logger.info(
                f"Device sync completed for {tenant.name}: "
                f"{compliance_pct:.1f}% compliant ({compliant_devices}/{total_devices})"
            )

            return {
                "status": "success",
                "total_devices": total_devices,
                "compliant_devices": compliant_devices,
                "compliance_pct": round(compliance_pct, 2),
                "mdm_enrolled": mdm_enrolled,
                "encrypted_devices": encrypted_devices,
                "edr_covered": edr_covered,
            }

        except HttpResponseError as e:
            error_msg = f"Azure API error syncing devices: {e.status_code} - {e.message}"
            logger.error(error_msg)
            raise SyncError(error_msg, tenant_id) from e
        except CircuitBreakerError as e:
            error_msg = f"Circuit breaker open for device sync: {e}"
            logger.error(error_msg)
            raise SyncError(error_msg, tenant_id) from e
        except Exception as e:
            error_msg = f"Unexpected error syncing devices: {e}"
            logger.error(error_msg)
            raise SyncError(error_msg, tenant_id) from e

    if db:
        return await _do_sync(db)
    else:
        with get_db_context() as session:
            return await _do_sync(session)


@circuit_breaker(RIVERSIDE_SYNC_BREAKER)
@retry_with_backoff(RIVERSIDE_SYNC_POLICY)
async def sync_requirement_status(
    tenant_id: str,
    db: Session | None = None,
) -> dict:
    """Sync requirement status progress for a specific tenant.

    Checks Azure resources and configuration against requirement criteria,
    updating requirement status based on actual tenant compliance state.

    Args:
        tenant_id: Azure tenant ID to sync
        db: Database session (creates context if None)

    Returns:
        Dict with requirement sync results:
        - status: "success" or "error"
        - requirements_checked: number of requirements checked
        - requirements_updated: number of requirements updated
        - updates: list of requirement status changes

    Raises:
        SyncError: If sync fails and circuit breaker/retry exhausted
    """
    logger.info(f"Syncing requirement status for tenant: {tenant_id}")

    async def _do_sync(session: Session) -> dict:
        # Get tenant
        tenant = session.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
        if not tenant:
            raise SyncError(f"Tenant {tenant_id} not found", tenant_id)

        try:
            graph_client = _get_graph_client(tenant_id)

            # Get requirements for this tenant
            requirements = (
                session.query(RiversideRequirement)
                .filter(RiversideRequirement.tenant_id == tenant_id)
                .all()
            )

            requirements_checked = 0
            requirements_updated = 0
            updates: list[dict] = []

            # Check Conditional Access policies for MFA enforcement
            ca_policies = await graph_client.get_conditional_access_policies()

            # Analyze policies for MFA enforcement
            has_mfa_policy = False
            for policy in ca_policies:
                policy_name = policy.get("displayName", "").lower()
                grant_controls = policy.get("grantControls", {})
                built_in_controls = grant_controls.get("builtInControls", [])

                # Check for MFA enforcement
                if "mfa" in policy_name or "mfa" in str(built_in_controls).lower():
                    has_mfa_policy = True
                    break

            # Check each requirement and update status based on Azure state
            for req in requirements:
                requirements_checked += 1
                old_status = req.status
                new_status = old_status

                # MFA-related requirements
                if "MFA" in req.requirement_id.upper() or "mfa" in req.title.lower():
                    if has_mfa_policy and old_status == RequirementStatus.NOT_STARTED:
                        new_status = RequirementStatus.IN_PROGRESS

                # Update if status changed
                if new_status != old_status:
                    req.status = new_status
                    req.updated_at = datetime.utcnow()
                    requirements_updated += 1
                    updates.append(
                        {
                            "requirement_id": req.requirement_id,
                            "title": req.title,
                            "old_status": old_status.value,
                            "new_status": new_status.value,
                        }
                    )

            session.commit()

            logger.info(
                f"Requirement sync completed for {tenant.name}: "
                f"{requirements_checked} checked, {requirements_updated} updated"
            )

            return {
                "status": "success",
                "requirements_checked": requirements_checked,
                "requirements_updated": requirements_updated,
                "updates": updates,
            }

        except HttpResponseError as e:
            error_msg = f"Azure API error syncing requirements: {e.status_code} - {e.message}"
            logger.error(error_msg)
            raise SyncError(error_msg, tenant_id) from e
        except CircuitBreakerError as e:
            error_msg = f"Circuit breaker open for requirement sync: {e}"
            logger.error(error_msg)
            raise SyncError(error_msg, tenant_id) from e
        except Exception as e:
            error_msg = f"Unexpected error syncing requirements: {e}"
            logger.error(error_msg)
            raise SyncError(error_msg, tenant_id) from e

    if db:
        return await _do_sync(db)
    else:
        with get_db_context() as session:
            return await _do_sync(session)


@circuit_breaker(RIVERSIDE_SYNC_BREAKER)
@retry_with_backoff(RIVERSIDE_SYNC_POLICY)
async def sync_maturity_scores(
    tenant_id: str,
    db: Session | None = None,
    snapshot_date: datetime | None = None,
) -> dict:
    """Sync and calculate maturity scores for a specific tenant.

    Calculates domain maturity scores (0-5 scale) based on MFA coverage,
    device compliance, and requirement completion status.

    Args:
        tenant_id: Azure tenant ID to sync
        db: Database session (creates context if None)
        snapshot_date: Optional snapshot date (defaults to now)

    Returns:
        Dict with maturity sync results:
        - status: "success" or "error"
        - maturity_score: overall maturity score (0-5)
        - target_score: target maturity score (3.0)
        - domain_scores: individual domain scores
        - requirements_completed: completed requirements count
        - requirements_total: total requirements count
        - critical_gaps: count of critical gaps

    Raises:
        SyncError: If sync fails and circuit breaker/retry exhausted
    """
    snapshot_date = snapshot_date or datetime.utcnow()

    logger.info(f"Syncing maturity scores for tenant: {tenant_id}")

    def _do_sync(session: Session) -> dict:
        # Get tenant
        tenant = session.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
        if not tenant:
            raise SyncError(f"Tenant {tenant_id} not found", tenant_id)

        try:
            # Get latest MFA data for this tenant
            mfa_data = (
                session.query(RiversideMFA)
                .filter(RiversideMFA.tenant_id == tenant_id)
                .order_by(RiversideMFA.snapshot_date.desc())
                .first()
            )

            # Get latest device compliance data
            device_data = (
                session.query(RiversideDeviceCompliance)
                .filter(RiversideDeviceCompliance.tenant_id == tenant_id)
                .order_by(RiversideDeviceCompliance.snapshot_date.desc())
                .first()
            )

            # Get requirements data
            total_reqs = (
                session.query(RiversideRequirement)
                .filter(RiversideRequirement.tenant_id == tenant_id)
                .count()
            )

            completed_reqs = (
                session.query(RiversideRequirement)
                .filter(
                    RiversideRequirement.tenant_id == tenant_id,
                    RiversideRequirement.status == RequirementStatus.COMPLETED.value,
                )
                .count()
            )

            # Calculate maturity scores (0-5 scale)
            # MFA Score (40% weight)
            mfa_score = 0.0
            if mfa_data and mfa_data.total_users > 0:
                mfa_pct = mfa_data.mfa_coverage_percentage / 100
                # Scale: <20% = 0, 20-40% = 1, 40-60% = 2, 60-80% = 3, 80-90% = 4, >90% = 5
                mfa_score = min(mfa_pct * 5, 5.0)

            # Device Score (30% weight)
            device_score = 0.0
            if device_data and device_data.total_devices > 0:
                device_pct = device_data.compliance_percentage / 100
                device_score = min(device_pct * 5, 5.0)

            # Requirements Score (30% weight)
            req_score = 0.0
            if total_reqs > 0:
                req_pct = completed_reqs / total_reqs
                req_score = min(req_pct * 5, 5.0)

            # Calculate weighted overall maturity
            overall_maturity = (mfa_score * 0.4) + (device_score * 0.3) + (req_score * 0.3)

            # Count critical gaps (P0 requirements not completed)
            critical_gaps = (
                session.query(RiversideRequirement)
                .filter(
                    RiversideRequirement.tenant_id == tenant_id,
                    RiversideRequirement.status != RequirementStatus.COMPLETED.value,
                    RiversideRequirement.priority == RequirementPriority.P0.value,
                )
                .count()
            )

            # Get or create compliance record
            compliance_record = (
                session.query(RiversideCompliance)
                .filter(RiversideCompliance.tenant_id == tenant_id)
                .first()
            )

            if compliance_record:
                compliance_record.overall_maturity_score = round(overall_maturity, 2)
                compliance_record.target_maturity_score = TARGET_MATURITY_SCORE
                compliance_record.critical_gaps_count = critical_gaps
                compliance_record.requirements_completed = completed_reqs
                compliance_record.requirements_total = total_reqs
                compliance_record.last_assessment_date = snapshot_date
                compliance_record.updated_at = snapshot_date
            else:
                compliance_record = RiversideCompliance(
                    tenant_id=tenant_id,
                    overall_maturity_score=round(overall_maturity, 2),
                    target_maturity_score=TARGET_MATURITY_SCORE,
                    deadline_date=RIVERSIDE_DEADLINE,
                    financial_risk="$4M",
                    critical_gaps_count=critical_gaps,
                    requirements_completed=completed_reqs,
                    requirements_total=total_reqs,
                    last_assessment_date=snapshot_date,
                )
                session.add(compliance_record)

            session.commit()

            domain_scores = {
                "mfa": round(mfa_score, 2),
                "device": round(device_score, 2),
                "requirements": round(req_score, 2),
            }

            logger.info(
                f"Maturity sync completed for {tenant.name}: "
                f"{overall_maturity:.2f}/5.0 (MFA: {mfa_score:.1f}, Device: {device_score:.1f}, Req: {req_score:.1f})"
            )

            return {
                "status": "success",
                "maturity_score": round(overall_maturity, 2),
                "target_score": TARGET_MATURITY_SCORE,
                "domain_scores": domain_scores,
                "requirements_completed": completed_reqs,
                "requirements_total": total_reqs,
                "critical_gaps": critical_gaps,
            }

        except CircuitBreakerError as e:
            error_msg = f"Circuit breaker open for maturity sync: {e}"
            logger.error(error_msg)
            raise SyncError(error_msg, tenant_id) from e
        except Exception as e:
            error_msg = f"Unexpected error syncing maturity scores: {e}"
            logger.error(error_msg)
            raise SyncError(error_msg, tenant_id) from e

    if db:
        return _do_sync(db)
    else:
        with get_db_context() as session:
            return _do_sync(session)


# Convenience function for non-async usage
async def run_full_tenant_sync(tenant_id: str, db: Session | None = None) -> dict:
    """Run a full sync for a single tenant (all data types).

    This is a convenience function that runs all sync operations
    for a single tenant in sequence.

    Args:
        tenant_id: Azure tenant ID to sync
        db: Database session (creates context if None)

    Returns:
        Dict with full sync results for all data types
    """
    logger.info(f"Running full sync for tenant: {tenant_id}")

    results = {
        "tenant_id": tenant_id,
        "mfa": None,
        "devices": None,
        "requirements": None,
        "maturity": None,
    }

    try:
        results["mfa"] = await sync_tenant_mfa(tenant_id, db)
    except Exception as e:
        logger.error(f"MFA sync failed: {e}")
        results["mfa"] = {"status": "error", "error": str(e)}

    try:
        results["devices"] = await sync_tenant_devices(tenant_id, db)
    except Exception as e:
        logger.error(f"Device sync failed: {e}")
        results["devices"] = {"status": "error", "error": str(e)}

    try:
        results["requirements"] = await sync_requirement_status(tenant_id, db)
    except Exception as e:
        logger.error(f"Requirement sync failed: {e}")
        results["requirements"] = {"status": "error", "error": str(e)}

    try:
        results["maturity"] = await sync_maturity_scores(tenant_id, db)
    except Exception as e:
        logger.error(f"Maturity sync failed: {e}")
        results["maturity"] = {"status": "error", "error": str(e)}

    # Determine overall status
    statuses = [
        results["mfa"].get("status"),
        results["devices"].get("status"),
        results["requirements"].get("status"),
        results["maturity"].get("status"),
    ]

    if all(s == "success" for s in statuses):
        results["overall_status"] = "success"
    elif any(s == "success" for s in statuses):
        results["overall_status"] = "partial"
    else:
        results["overall_status"] = "failed"

    return results
