"""MFA compliance preflight checks.

This module provides comprehensive MFA enrollment verification checks
for the preflight system, validating:
- Tenant MFA data exists in database
- Admin MFA enrollment (target: 100%)
- User MFA enrollment (target: 95%)
- Reporting of gaps in MFA coverage
- Remediation suggestions

Example:
    >>> from app.preflight.mfa_checks import (
    ...     MFATenantDataCheck,
    ...     MFAAdminEnrollmentCheck,
    ...     MFAUserEnrollmentCheck,
    ...     run_all_mfa_checks,
    ... )
    >>> # Using class-based API
    >>> check = MFAAdminEnrollmentCheck()
    >>> result = await check.run(tenant_id="12345678-1234-1234-1234-123456789012")
    >>>
    >>> # Run all MFA checks
    >>> results = await run_all_mfa_checks()
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.riverside import RiversideMFA
from app.models.tenant import Tenant
from app.preflight.base import BasePreflightCheck
from app.preflight.models import CheckCategory, CheckResult, CheckStatus

logger = logging.getLogger(__name__)


class SeverityLevel(str):
    """Severity levels for MFA compliance checks."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class MFATenantDataCheck(BasePreflightCheck):
    """Check that tenant MFA data exists in the database.

    Verifies that MFA enrollment data has been synced from Azure AD
    and is available for compliance reporting.
    """

    def __init__(self):
        super().__init__(
            check_id="mfa_tenant_data",
            name="MFA Tenant Data Availability",
            category=CheckCategory.MFA_COMPLIANCE,
            description="Verify MFA data exists in database for tenant",
            timeout_seconds=15.0,
        )

    async def _execute_check(
        self, tenant_id: str | None = None
    ) -> CheckResult:
        """Execute MFA tenant data availability check."""
        start_time = datetime.utcnow()
        db: Session | None = None

        try:
            db = SessionLocal()

            # Build query
            query = db.query(RiversideMFA)
            if tenant_id:
                query = query.filter(RiversideMFA.tenant_id == tenant_id)

            # Get latest MFA data
            latest_mfa = (
                query.order_by(RiversideMFA.snapshot_date.desc())
                .first()
            )

            # Get total record count
            total_records = query.count()

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            if not latest_mfa:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.FAIL,
                    message="No MFA data found in database for tenant",
                    details={
                        "tenant_id": tenant_id,
                        "total_records": total_records,
                        "severity": SeverityLevel.CRITICAL,
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Run MFA sync to populate data: app.core.sync.riverside.sync_riverside()",
                        "Verify Azure AD permissions allow MFA data retrieval",
                        "Check that the sync job is properly scheduled",
                    ],
                    tenant_id=tenant_id,
                )

            # Check data freshness (data older than 7 days is stale)
            data_age_days = (
                datetime.utcnow() - latest_mfa.snapshot_date
            ).total_seconds() / 86400

            is_stale = data_age_days > 7

            if is_stale:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.WARNING,
                    message=f"MFA data is stale ({data_age_days:.1f} days old)",
                    details={
                        "tenant_id": tenant_id,
                        "latest_snapshot": latest_mfa.snapshot_date.isoformat(),
                        "data_age_days": round(data_age_days, 1),
                        "total_records": total_records,
                        "severity": SeverityLevel.WARNING,
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        f"Data is {data_age_days:.1f} days old - consider running a new sync",
                        "Check if the scheduled sync job is running properly",
                        "Verify Azure AD sync permissions are still valid",
                    ],
                    tenant_id=tenant_id,
                )

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.PASS,
                message=f"MFA data available ({total_records} records, {data_age_days:.1f} days old)",
                details={
                    "tenant_id": tenant_id,
                    "latest_snapshot": latest_mfa.snapshot_date.isoformat(),
                    "data_age_days": round(data_age_days, 1),
                    "total_records": total_records,
                    "severity": SeverityLevel.INFO,
                },
                duration_ms=duration_ms,
                tenant_id=tenant_id,
            )

        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"MFA data check failed: {str(e)}",
                details={
                    "error_type": type(e).__name__,
                    "severity": SeverityLevel.CRITICAL,
                },
                duration_ms=duration_ms,
                recommendations=[
                    "Check database connectivity",
                    "Verify RiversideMFA table exists",
                    "Review application logs for database errors",
                ],
                tenant_id=tenant_id,
            )
        finally:
            if db:
                db.close()


class MFAAdminEnrollmentCheck(BasePreflightCheck):
    """Check admin MFA enrollment compliance.

    Validates that all admin accounts have MFA enrolled.
    Target: 100% MFA enrollment for admin accounts.
    """

    # Target: 100% MFA enrollment for admin accounts
    ADMIN_MFA_TARGET = 100.0

    def __init__(self):
        super().__init__(
            check_id="mfa_admin_enrollment",
            name="MFA Admin Enrollment Compliance",
            category=CheckCategory.MFA_COMPLIANCE,
            description="Verify 100% MFA enrollment for admin accounts",
            timeout_seconds=15.0,
        )

    async def _execute_check(
        self, tenant_id: str | None = None
    ) -> CheckResult:
        """Execute admin MFA enrollment check."""
        start_time = datetime.utcnow()
        db: Session | None = None

        try:
            db = SessionLocal()

            # Get latest MFA data for tenant
            query = db.query(RiversideMFA)
            if tenant_id:
                query = query.filter(RiversideMFA.tenant_id == tenant_id)

            latest_mfa = (
                query.order_by(RiversideMFA.snapshot_date.desc())
                .first()
            )

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            if not latest_mfa:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.FAIL,
                    message="No MFA data available to check admin enrollment",
                    details={
                        "tenant_id": tenant_id,
                        "severity": SeverityLevel.CRITICAL,
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Run MFA sync to populate data",
                        "Check tenant configuration",
                    ],
                    tenant_id=tenant_id,
                )

            # Extract admin MFA metrics
            admin_total = latest_mfa.admin_accounts_total or 0
            admin_mfa = latest_mfa.admin_accounts_mfa or 0
            admin_mfa_pct = latest_mfa.admin_mfa_percentage or 0.0
            admin_unprotected = admin_total - admin_mfa

            # Determine compliance status
            if admin_total == 0:
                # No admin accounts found - warning but not failure
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.WARNING,
                    message="No admin accounts found in MFA data",
                    details={
                        "tenant_id": tenant_id,
                        "admin_accounts_total": 0,
                        "severity": SeverityLevel.WARNING,
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Verify Azure AD sync is capturing admin roles",
                        "Check that admin role mappings are configured correctly",
                    ],
                    tenant_id=tenant_id,
                )

            if admin_mfa_pct >= self.ADMIN_MFA_TARGET:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.PASS,
                    message=f"Admin MFA compliance achieved: {admin_mfa_pct:.1f}% ({admin_mfa}/{admin_total})",
                    details={
                        "tenant_id": tenant_id,
                        "admin_accounts_total": admin_total,
                        "admin_accounts_mfa": admin_mfa,
                        "admin_mfa_percentage": admin_mfa_pct,
                        "target_percentage": self.ADMIN_MFA_TARGET,
                        "unprotected_admins": admin_unprotected,
                        "severity": SeverityLevel.INFO,
                    },
                    duration_ms=duration_ms,
                    tenant_id=tenant_id,
                )

            # Admin MFA below target - CRITICAL
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"CRITICAL: Admin MFA enrollment {admin_mfa_pct:.1f}% below target {self.ADMIN_MFA_TARGET:.0f}% ({admin_mfa}/{admin_total})",
                details={
                    "tenant_id": tenant_id,
                    "admin_accounts_total": admin_total,
                    "admin_accounts_mfa": admin_mfa,
                    "admin_mfa_percentage": admin_mfa_pct,
                    "target_percentage": self.ADMIN_MFA_TARGET,
                    "unprotected_admins": admin_unprotected,
                    "severity": SeverityLevel.CRITICAL,
                },
                duration_ms=duration_ms,
                recommendations=[
                    f"CRITICAL: {admin_unprotected} admin accounts without MFA protection",
                    "Immediately enforce MFA for all admin accounts via Conditional Access",
                    "Review admin accounts and remove unnecessary elevated privileges",
                    "Consider emergency MFA rollout for privileged accounts",
                ],
                tenant_id=tenant_id,
            )

        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"Admin MFA check failed: {str(e)}",
                details={
                    "error_type": type(e).__name__,
                    "severity": SeverityLevel.CRITICAL,
                },
                duration_ms=duration_ms,
                recommendations=[
                    "Check database connectivity",
                    "Verify RiversideMFA table structure",
                ],
                tenant_id=tenant_id,
            )
        finally:
            if db:
                db.close()


class MFAUserEnrollmentCheck(BasePreflightCheck):
    """Check user MFA enrollment compliance.

    Validates that regular users meet MFA enrollment targets.
    Target: 95% MFA enrollment for all users.
    """

    # Target: 95% MFA enrollment for users
    USER_MFA_TARGET = 95.0
    WARNING_THRESHOLD = 90.0

    def __init__(self):
        super().__init__(
            check_id="mfa_user_enrollment",
            name="MFA User Enrollment Compliance",
            category=CheckCategory.MFA_COMPLIANCE,
            description="Verify 95% MFA enrollment for all users",
            timeout_seconds=15.0,
        )

    async def _execute_check(
        self, tenant_id: str | None = None
    ) -> CheckResult:
        """Execute user MFA enrollment check."""
        start_time = datetime.utcnow()
        db: Session | None = None

        try:
            db = SessionLocal()

            # Get latest MFA data for tenant
            query = db.query(RiversideMFA)
            if tenant_id:
                query = query.filter(RiversideMFA.tenant_id == tenant_id)

            latest_mfa = (
                query.order_by(RiversideMFA.snapshot_date.desc())
                .first()
            )

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            if not latest_mfa:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.FAIL,
                    message="No MFA data available to check user enrollment",
                    details={
                        "tenant_id": tenant_id,
                        "severity": SeverityLevel.CRITICAL,
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Run MFA sync to populate data",
                        "Check tenant configuration",
                    ],
                    tenant_id=tenant_id,
                )

            # Extract user MFA metrics
            total_users = latest_mfa.total_users or 0
            mfa_enrolled = latest_mfa.mfa_enrolled_users or 0
            mfa_pct = latest_mfa.mfa_coverage_percentage or 0.0
            unprotected_users = latest_mfa.unprotected_users or 0

            # Determine compliance status
            if total_users == 0:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.WARNING,
                    message="No users found in MFA data",
                    details={
                        "tenant_id": tenant_id,
                        "total_users": 0,
                        "severity": SeverityLevel.WARNING,
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Verify Azure AD sync is working",
                        "Check that users are being synced from Azure AD",
                    ],
                    tenant_id=tenant_id,
                )

            if mfa_pct >= self.USER_MFA_TARGET:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.PASS,
                    message=f"User MFA compliance achieved: {mfa_pct:.1f}% ({mfa_enrolled}/{total_users})",
                    details={
                        "tenant_id": tenant_id,
                        "total_users": total_users,
                        "mfa_enrolled_users": mfa_enrolled,
                        "mfa_coverage_percentage": mfa_pct,
                        "target_percentage": self.USER_MFA_TARGET,
                        "unprotected_users": unprotected_users,
                        "severity": SeverityLevel.INFO,
                    },
                    duration_ms=duration_ms,
                    tenant_id=tenant_id,
                )

            if mfa_pct >= self.WARNING_THRESHOLD:
                # Between 90% and 95% - WARNING
                gap_to_target = self.USER_MFA_TARGET - mfa_pct
                users_needed = int(total_users * (gap_to_target / 100))

                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.WARNING,
                    message=f"User MFA below target: {mfa_pct:.1f}% vs {self.USER_MFA_TARGET:.0f}% target ({mfa_enrolled}/{total_users})",
                    details={
                        "tenant_id": tenant_id,
                        "total_users": total_users,
                        "mfa_enrolled_users": mfa_enrolled,
                        "mfa_coverage_percentage": mfa_pct,
                        "target_percentage": self.USER_MFA_TARGET,
                        "unprotected_users": unprotected_users,
                        "gap_to_target_percentage": round(gap_to_target, 2),
                        "estimated_users_needed": users_needed,
                        "severity": SeverityLevel.WARNING,
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        f"{unprotected_users} users without MFA ({gap_to_target:.1f}% gap to target)",
                        f"Need approximately {users_needed} more users to enroll",
                        "Enable MFA registration campaign in Azure AD",
                        "Send reminder communications to non-enrolled users",
                        "Consider gradual enforcement via Conditional Access",
                    ],
                    tenant_id=tenant_id,
                )

            # Below 90% - FAIL
            gap_to_target = self.USER_MFA_TARGET - mfa_pct
            users_needed = int(total_users * (gap_to_target / 100))

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"User MFA significantly below target: {mfa_pct:.1f}% vs {self.USER_MFA_TARGET:.0f}% target ({mfa_enrolled}/{total_users})",
                details={
                    "tenant_id": tenant_id,
                    "total_users": total_users,
                    "mfa_enrolled_users": mfa_enrolled,
                    "mfa_coverage_percentage": mfa_pct,
                    "target_percentage": self.USER_MFA_TARGET,
                    "unprotected_users": unprotected_users,
                    "gap_to_target_percentage": round(gap_to_target, 2),
                    "estimated_users_needed": users_needed,
                    "severity": SeverityLevel.CRITICAL,
                },
                duration_ms=duration_ms,
                recommendations=[
                    f"CRITICAL: {unprotected_users} users without MFA protection",
                    f"Need approximately {users_needed} users to reach target",
                    "Launch MFA enrollment campaign immediately",
                    "Enable security defaults if not already active",
                    "Configure Conditional Access to require MFA",
                    "Consider blocking access for non-compliant users",
                ],
                tenant_id=tenant_id,
            )

        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"User MFA check failed: {str(e)}",
                details={
                    "error_type": type(e).__name__,
                    "severity": SeverityLevel.CRITICAL,
                },
                duration_ms=duration_ms,
                recommendations=[
                    "Check database connectivity",
                    "Verify RiversideMFA table structure",
                ],
                tenant_id=tenant_id,
            )
        finally:
            if db:
                db.close()


class MFAGapReportCheck(BasePreflightCheck):
    """Generate comprehensive MFA gap report.

    Analyzes MFA coverage across all tenants and reports gaps,
    providing detailed remediation suggestions.
    """

    def __init__(self):
        super().__init__(
            check_id="mfa_gap_report",
            name="MFA Gap Analysis Report",
            category=CheckCategory.MFA_COMPLIANCE,
            description="Comprehensive MFA enrollment gap analysis",
            timeout_seconds=30.0,
        )

    async def _execute_check(
        self, tenant_id: str | None = None
    ) -> CheckResult:
        """Execute MFA gap analysis check."""
        start_time = datetime.utcnow()
        db: Session | None = None

        try:
            db = SessionLocal()

            # Build query for latest MFA data per tenant
            from sqlalchemy import func

            # Get latest snapshot date per tenant
            latest_dates = (
                db.query(
                    RiversideMFA.tenant_id,
                    func.max(RiversideMFA.snapshot_date).label("latest_date")
                )
                .group_by(RiversideMFA.tenant_id)
                .subquery()
            )

            # Get latest MFA records
            query = (
                db.query(RiversideMFA)
                .join(
                    latest_dates,
                    (RiversideMFA.tenant_id == latest_dates.c.tenant_id) &
                    (RiversideMFA.snapshot_date == latest_dates.c.latest_date)
                )
            )

            if tenant_id:
                query = query.filter(RiversideMFA.tenant_id == tenant_id)

            mfa_records = query.all()

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            if not mfa_records:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.FAIL,
                    message="No MFA data available for gap analysis",
                    details={
                        "tenant_id": tenant_id,
                        "tenant_count": 0,
                        "severity": SeverityLevel.CRITICAL,
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Run MFA sync across all tenants",
                        "Verify sync job configuration",
                    ],
                    tenant_id=tenant_id,
                )

            # Calculate aggregate metrics
            total_users = sum(r.total_users or 0 for r in mfa_records)
            total_mfa_enrolled = sum(r.mfa_enrolled_users or 0 for r in mfa_records)
            total_admins = sum(r.admin_accounts_total or 0 for r in mfa_records)
            admins_with_mfa = sum(r.admin_accounts_mfa or 0 for r in mfa_records)

            overall_user_pct = (
                (total_mfa_enrolled / total_users * 100) if total_users > 0 else 0
            )
            overall_admin_pct = (
                (admins_with_mfa / total_admins * 100) if total_admins > 0 else 0
            )

            # Identify gaps
            gaps = []
            tenant_summaries = []

            for record in mfa_records:
                tenant_gaps = []

                user_pct = record.mfa_coverage_percentage or 0
                admin_pct = record.admin_mfa_percentage or 0

                if user_pct < 95:
                    tenant_gaps.append({
                        "type": "user_mfa",
                        "current": user_pct,
                        "target": 95,
                        "gap": 95 - user_pct,
                    })

                if admin_pct < 100:
                    tenant_gaps.append({
                        "type": "admin_mfa",
                        "current": admin_pct,
                        "target": 100,
                        "gap": 100 - admin_pct,
                    })

                if tenant_gaps:
                    gaps.append({
                        "tenant_id": record.tenant_id,
                        "gaps": tenant_gaps,
                    })

                tenant_summaries.append({
                    "tenant_id": record.tenant_id,
                    "total_users": record.total_users,
                    "mfa_enrolled": record.mfa_enrolled_users,
                    "user_mfa_pct": user_pct,
                    "admin_total": record.admin_accounts_total,
                    "admin_mfa": record.admin_accounts_mfa,
                    "admin_mfa_pct": admin_pct,
                })

            # Determine overall status
            critical_gaps = sum(
                1 for g in gaps
                for tg in g["gaps"]
                if tg["type"] == "admin_mfa" and tg["gap"] > 0
            )

            warning_gaps = sum(
                1 for g in gaps
                for tg in g["gaps"]
                if tg["type"] == "user_mfa" and tg["gap"] > 0
            )

            if critical_gaps > 0:
                status = CheckStatus.FAIL
                severity = SeverityLevel.CRITICAL
                message = f"CRITICAL: {critical_gaps} tenants with admin MFA gaps, {warning_gaps} with user MFA gaps"
            elif warning_gaps > 0:
                status = CheckStatus.WARNING
                severity = SeverityLevel.WARNING
                message = f"WARNING: {warning_gaps} tenants below user MFA target (95%)"
            else:
                status = CheckStatus.PASS
                severity = SeverityLevel.INFO
                message = f"All tenants compliant - User MFA: {overall_user_pct:.1f}%, Admin MFA: {overall_admin_pct:.1f}%"

            # Generate remediation suggestions
            recommendations = []
            if critical_gaps > 0:
                recommendations.append(
                    f"CRITICAL: {critical_gaps} tenant(s) have admin accounts without MFA"
                )
                recommendations.append(
                    "Enable Conditional Access policy requiring MFA for all admin roles"
                )
                recommendations.append(
                    "Review and revoke unnecessary admin privileges"
                )

            if warning_gaps > 0:
                recommendations.append(
                    f"{warning_gaps} tenant(s) below 95% user MFA target"
                )
                recommendations.append(
                    "Enable MFA registration campaign in Azure AD"
                )
                recommendations.append(
                    "Send targeted communications to non-enrolled users"
                )

            if not recommendations:
                recommendations.append(
                    "Maintain current MFA policies and monitoring"
                )
                recommendations.append(
                    "Consider increasing user MFA target to 98-100%"
                )

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=status,
                message=message,
                details={
                    "tenant_id": tenant_id,
                    "tenant_count": len(mfa_records),
                    "total_users": total_users,
                    "total_mfa_enrolled": total_mfa_enrolled,
                    "overall_user_mfa_pct": round(overall_user_pct, 2),
                    "overall_admin_mfa_pct": round(overall_admin_pct, 2),
                    "critical_gaps": critical_gaps,
                    "warning_gaps": warning_gaps,
                    "tenant_summaries": tenant_summaries,
                    "gap_details": gaps,
                    "severity": severity,
                },
                duration_ms=duration_ms,
                recommendations=recommendations,
                tenant_id=tenant_id,
            )

        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"MFA gap report failed: {str(e)}",
                details={
                    "error_type": type(e).__name__,
                    "severity": SeverityLevel.CRITICAL,
                },
                duration_ms=duration_ms,
                recommendations=[
                    "Check database connectivity",
                    "Verify RiversideMFA table structure",
                ],
                tenant_id=tenant_id,
            )
        finally:
            if db:
                db.close()


# ============================================================================
# FUNCTION-BASED API (for direct use)
# ============================================================================

async def check_mfa_tenant_data(tenant_id: str | None = None) -> CheckResult:
    """Check MFA tenant data availability.

    Args:
        tenant_id: Optional tenant ID for tenant-specific check

    Returns:
        CheckResult with MFA data availability status
    """
    check = MFATenantDataCheck()
    return await check.run(tenant_id=tenant_id)


async def check_mfa_admin_enrollment(tenant_id: str | None = None) -> CheckResult:
    """Check admin MFA enrollment compliance.

    Args:
        tenant_id: Optional tenant ID for tenant-specific check

    Returns:
        CheckResult with admin MFA enrollment status
    """
    check = MFAAdminEnrollmentCheck()
    return await check.run(tenant_id=tenant_id)


async def check_mfa_user_enrollment(tenant_id: str | None = None) -> CheckResult:
    """Check user MFA enrollment compliance.

    Args:
        tenant_id: Optional tenant ID for tenant-specific check

    Returns:
        CheckResult with user MFA enrollment status
    """
    check = MFAUserEnrollmentCheck()
    return await check.run(tenant_id=tenant_id)


async def check_mfa_gap_report(tenant_id: str | None = None) -> CheckResult:
    """Generate MFA gap analysis report.

    Args:
        tenant_id: Optional tenant ID for tenant-specific check

    Returns:
        CheckResult with comprehensive MFA gap analysis
    """
    check = MFAGapReportCheck()
    return await check.run(tenant_id=tenant_id)


async def run_all_mfa_checks(tenant_id: str | None = None) -> list[CheckResult]:
    """Run all MFA compliance preflight checks.

    Args:
        tenant_id: Optional tenant ID for tenant-specific checks

    Returns:
        List of CheckResults from all MFA checks
    """
    checks = [
        MFATenantDataCheck(),
        MFAAdminEnrollmentCheck(),
        MFAUserEnrollmentCheck(),
        MFAGapReportCheck(),
    ]

    results = []
    for check in checks:
        try:
            result = await check.run(tenant_id=tenant_id)
            results.append(result)
        except Exception as e:
            # If a check fails completely, create a failed result
            results.append(
                CheckResult(
                    check_id=check.check_id,
                    name=check.name,
                    category=check.category,
                    status=CheckStatus.FAIL,
                    message=f"Check failed with exception: {str(e)}",
                    details={"error_type": type(e).__name__},
                    recommendations=["Review application logs for details"],
                    tenant_id=tenant_id,
                )
            )

    return results


def get_mfa_checks() -> dict[str, BasePreflightCheck]:
    """Get all MFA compliance preflight checks.

    Returns:
        Dictionary mapping check_id to check instance
    """
    checks = [
        MFATenantDataCheck(),
        MFAAdminEnrollmentCheck(),
        MFAUserEnrollmentCheck(),
        MFAGapReportCheck(),
    ]

    return {check.check_id: check for check in checks}
