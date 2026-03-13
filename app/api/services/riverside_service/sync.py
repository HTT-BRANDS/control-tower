"""Riverside Service - Sync functions for Graph API integration."""

import logging
from datetime import datetime

from sqlalchemy import func

from app.api.services.graph_client import GraphClient
from app.api.services.riverside_service.constants import (
    ADMIN_ROLE_IDS,
    RIVERSIDE_DEADLINE,
)
from app.models.riverside import (
    RiversideCompliance,
    RiversideDeviceCompliance,
    RiversideMFA,
    RiversideRequirement,
)
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)


async def sync_riverside_mfa(db) -> dict:
    """Sync MFA data from Microsoft Graph API for all tenants.

    Args:
        db: Database session

    Returns:
        Dict with sync results by tenant.
    """
    results = {}
    snapshot_date = datetime.utcnow()

    tenants = db.query(Tenant).filter(Tenant.is_active.is_(True)).all()

    for tenant in tenants:
        try:
            graph_client = GraphClient(tenant.tenant_id)

            # Get MFA registration details
            mfa_data = await graph_client.get_mfa_status()

            # Get users for total count
            users = await graph_client.get_users(top=999)

            # Get directory roles for admin MFA tracking
            directory_roles = await graph_client.get_directory_roles()

            # Calculate MFA metrics
            total_users = len(users)
            mfa_enrolled = 0
            admin_accounts_total = 0
            admin_accounts_mfa = 0

            # Parse MFA registration data
            registrations = mfa_data.get("value", [])
            for reg in registrations:
                methods_registered = reg.get("methodsRegistered", [])
                if methods_registered:
                    mfa_enrolled += 1

            # Count admin accounts and MFA status
            for role in directory_roles:
                if role.get("roleTemplateId") in ADMIN_ROLE_IDS:
                    members = role.get("members", [])
                    admin_accounts_total += len(members)
                    for member in members:
                        for reg in registrations:
                            if reg.get("userPrincipalName") == member.get("userPrincipalName"):
                                if reg.get("isMfaRegistered"):
                                    admin_accounts_mfa += 1
                                    break

            # Calculate percentages
            mfa_coverage_pct = (mfa_enrolled / total_users * 100) if total_users > 0 else 0
            admin_mfa_pct = (
                (admin_accounts_mfa / admin_accounts_total * 100) if admin_accounts_total > 0 else 0
            )
            unprotected = total_users - mfa_enrolled

            # Create or update MFA record
            mfa_record = (
                db.query(RiversideMFA)
                .filter(
                    RiversideMFA.tenant_id == tenant.tenant_id,
                    func.date(RiversideMFA.snapshot_date) == snapshot_date.date(),
                )
                .first()
            )

            if mfa_record:
                mfa_record.total_users = total_users
                mfa_record.mfa_enrolled_users = mfa_enrolled
                mfa_record.mfa_coverage_percentage = mfa_coverage_pct
                mfa_record.admin_accounts_total = admin_accounts_total
                mfa_record.admin_accounts_mfa = admin_accounts_mfa
                mfa_record.admin_mfa_percentage = admin_mfa_pct
                mfa_record.unprotected_users = unprotected
                mfa_record.snapshot_date = snapshot_date
            else:
                mfa_record = RiversideMFA(
                    tenant_id=tenant.tenant_id,
                    total_users=total_users,
                    mfa_enrolled_users=mfa_enrolled,
                    mfa_coverage_percentage=mfa_coverage_pct,
                    admin_accounts_total=admin_accounts_total,
                    admin_accounts_mfa=admin_accounts_mfa,
                    admin_mfa_percentage=admin_mfa_pct,
                    unprotected_users=unprotected,
                    snapshot_date=snapshot_date,
                )
                db.add(mfa_record)

            db.commit()

            results[tenant.tenant_id] = {
                "status": "success",
                "total_users": total_users,
                "mfa_enrolled": mfa_enrolled,
                "mfa_coverage_pct": mfa_coverage_pct,
                "admin_accounts": admin_accounts_total,
                "admin_mfa_pct": admin_mfa_pct,
            }

            logger.info(f"Synced MFA for {tenant.name}: {mfa_coverage_pct:.1f}% coverage")

        except Exception as e:
            logger.error(f"Failed to sync MFA for {tenant.name}: {e}")
            results[tenant.tenant_id] = {
                "status": "error",
                "error": str(e),
            }
            continue

    return results


async def sync_riverside_device_compliance(db) -> dict:
    """Sync device compliance data from Intune/Graph API for all tenants.

    Args:
        db: Database session

    Returns:
        Dict with sync results by tenant.
    """
    results = {}
    snapshot_date = datetime.utcnow()

    tenants = db.query(Tenant).filter(Tenant.is_active.is_(True)).all()

    for tenant in tenants:
        try:
            graph_client = GraphClient(tenant.tenant_id)

            # Get managed devices from Intune
            devices = await graph_client._request(
                "GET", "/deviceManagement/managedDevices", params={"$top": 999}
            )

            device_list = devices.get("value", [])
            total_devices = len(device_list)

            # Calculate compliance metrics
            compliant = 0
            mdm_enrolled = 0
            encrypted = 0

            for device in device_list:
                if device.get("complianceState") == "compliant":
                    compliant += 1
                if device.get("managementAgent") in [
                    "mdm",
                    "easMdm",
                    "configurationManagerClientMdm",
                    "configurationManagerClientMdmEas",
                ]:
                    mdm_enrolled += 1
                if device.get("isEncrypted"):
                    encrypted += 1

            edr_covered = compliant
            compliance_pct = (compliant / total_devices * 100) if total_devices > 0 else 0

            # Create or update device compliance record
            device_record = (
                db.query(RiversideDeviceCompliance)
                .filter(
                    RiversideDeviceCompliance.tenant_id == tenant.tenant_id,
                    func.date(RiversideDeviceCompliance.snapshot_date) == snapshot_date.date(),
                )
                .first()
            )

            if device_record:
                device_record.total_devices = total_devices
                device_record.mdm_enrolled = mdm_enrolled
                device_record.edr_covered = edr_covered
                device_record.encrypted_devices = encrypted
                device_record.compliant_devices = compliant
                device_record.compliance_percentage = compliance_pct
                device_record.snapshot_date = snapshot_date
            else:
                device_record = RiversideDeviceCompliance(
                    tenant_id=tenant.tenant_id,
                    total_devices=total_devices,
                    mdm_enrolled=mdm_enrolled,
                    edr_covered=edr_covered,
                    encrypted_devices=encrypted,
                    compliant_devices=compliant,
                    compliance_percentage=compliance_pct,
                    snapshot_date=snapshot_date,
                )
                db.add(device_record)

            db.commit()

            results[tenant.tenant_id] = {
                "status": "success",
                "total_devices": total_devices,
                "compliant": compliant,
                "compliance_pct": compliance_pct,
                "mdm_enrolled": mdm_enrolled,
                "encrypted": encrypted,
            }

            logger.info(
                f"Synced device compliance for {tenant.name}: {compliance_pct:.1f}% compliant"
            )

        except Exception as e:
            logger.error(f"Failed to sync device compliance for {tenant.name}: {e}")
            results[tenant.tenant_id] = {
                "status": "error",
                "error": str(e),
            }
            continue

    return results


async def sync_riverside_requirements(db) -> dict:
    """Sync requirement status from database and Graph API indicators.

    This checks Azure resources against requirement criteria and updates
    requirement status based on actual tenant configuration.

    Args:
        db: Database session

    Returns:
        Dict with sync results.
    """
    results = {
        "requirements_synced": 0,
        "requirements_updated": 0,
        "errors": [],
    }

    tenants = db.query(Tenant).filter(Tenant.is_active.is_(True)).all()

    for tenant in tenants:
        try:
            graph_client = GraphClient(tenant.tenant_id)

            # Check Conditional Access policies for MFA enforcement
            ca_policies = await graph_client.get_conditional_access_policies()

            # Check for MFA enforcement requirement
            mfa_req = (
                db.query(RiversideRequirement)
                .filter(
                    RiversideRequirement.tenant_id == tenant.tenant_id,
                    RiversideRequirement.requirement_id.like("%MFA%"),
                )
                .first()
            )

            if mfa_req:
                has_mfa_policy = any(
                    "mfa" in (policy.get("displayName", "")).lower()
                    or any(
                        "mfa" in str(grant).lower()
                        for grant in policy.get("grantControls", {}).get("builtInControls", [])
                    )
                    for policy in ca_policies
                )

                if has_mfa_policy and mfa_req.status != "completed":
                    mfa_req.status = "in_progress"
                    results["requirements_updated"] += 1

            db.commit()
            results["requirements_synced"] += 1

        except Exception as e:
            logger.error(f"Failed to sync requirements for {tenant.name}: {e}")
            results["errors"].append({"tenant": tenant.name, "error": str(e)})
            continue

    return results


async def sync_riverside_maturity_scores(db) -> dict:
    """Calculate and sync maturity scores based on current compliance data.

    Args:
        db: Database session

    Returns:
        Dict with maturity scores by tenant.
    """
    results = {}
    snapshot_date = datetime.utcnow()

    tenants = db.query(Tenant).filter(Tenant.is_active.is_(True)).all()

    for tenant in tenants:
        try:
            # Get latest MFA data
            mfa_data = (
                db.query(RiversideMFA)
                .filter(RiversideMFA.tenant_id == tenant.tenant_id)
                .order_by(RiversideMFA.snapshot_date.desc())
                .first()
            )

            # Get latest device compliance data
            device_data = (
                db.query(RiversideDeviceCompliance)
                .filter(RiversideDeviceCompliance.tenant_id == tenant.tenant_id)
                .order_by(RiversideDeviceCompliance.snapshot_date.desc())
                .first()
            )

            # Get requirements data
            total_reqs = (
                db.query(RiversideRequirement)
                .filter(RiversideRequirement.tenant_id == tenant.tenant_id)
                .count()
            )

            completed_reqs = (
                db.query(RiversideRequirement)
                .filter(
                    RiversideRequirement.tenant_id == tenant.tenant_id,
                    RiversideRequirement.status == "completed",
                )
                .count()
            )

            # Calculate maturity score (0-5 scale)
            mfa_score = 0.0
            device_score = 0.0
            req_score = 0.0

            if mfa_data and mfa_data.total_users > 0:
                mfa_pct = mfa_data.mfa_coverage_percentage / 100
                mfa_score = min(mfa_pct * 5, 5.0)

            if device_data and device_data.total_devices > 0:
                device_pct = device_data.compliance_percentage / 100
                device_score = min(device_pct * 5, 5.0)

            if total_reqs > 0:
                req_pct = completed_reqs / total_reqs
                req_score = min(req_pct * 5, 5.0)

            # Weighted average: MFA 40%, Device 30%, Requirements 30%
            overall_maturity = (mfa_score * 0.4) + (device_score * 0.3) + (req_score * 0.3)

            # Count critical gaps
            critical_gaps = (
                db.query(RiversideRequirement)
                .filter(
                    RiversideRequirement.tenant_id == tenant.tenant_id,
                    RiversideRequirement.status != "completed",
                    RiversideRequirement.priority == "P0",
                )
                .count()
            )

            # Create or update compliance record
            compliance_record = (
                db.query(RiversideCompliance)
                .filter(RiversideCompliance.tenant_id == tenant.tenant_id)
                .first()
            )

            if compliance_record:
                compliance_record.overall_maturity_score = round(overall_maturity, 2)
                compliance_record.critical_gaps_count = critical_gaps
                compliance_record.requirements_completed = completed_reqs
                compliance_record.requirements_total = total_reqs
                compliance_record.last_assessment_date = snapshot_date
                compliance_record.updated_at = snapshot_date
            else:
                compliance_record = RiversideCompliance(
                    tenant_id=tenant.tenant_id,
                    overall_maturity_score=round(overall_maturity, 2),
                    target_maturity_score=3.0,
                    deadline_date=RIVERSIDE_DEADLINE,
                    financial_risk="$4M",
                    critical_gaps_count=critical_gaps,
                    requirements_completed=completed_reqs,
                    requirements_total=total_reqs,
                    last_assessment_date=snapshot_date,
                )
                db.add(compliance_record)

            db.commit()

            results[tenant.tenant_id] = {
                "status": "success",
                "maturity_score": round(overall_maturity, 2),
                "target_score": 3.0,
                "requirements_completed": completed_reqs,
                "requirements_total": total_reqs,
                "critical_gaps": critical_gaps,
            }

            logger.info(f"Synced maturity score for {tenant.name}: {overall_maturity:.2f}/5.0")

        except Exception as e:
            logger.error(f"Failed to sync maturity score for {tenant.name}: {e}")
            results[tenant.tenant_id] = {
                "status": "error",
                "error": str(e),
            }
            continue

    return results
