"""Admin risk checks for privileged access control verification.

This module provides comprehensive preflight checks for identifying
privileged access risks including:
- Missing MFA on privileged accounts
- Overprivileged accounts (too many roles)
- Inactive admin accounts (90+ days)
- Shared admin accounts
- Compliance gaps

Example:
    >>> from app.preflight.admin_risk_checks import (
    ...     AdminMfaCheck,
    ...     OverprivilegedAccountCheck,
    ...     InactiveAdminCheck,
    ...     SharedAdminCheck,
    ...     AdminComplianceGapCheck,
    ... )
    >>> # Using class-based API
    >>> check = AdminMfaCheck()
    >>> result = await check.run(tenant_id="12345678-1234-1234-1234-123456789012")
    >>>
    >>> # Run all admin risk checks
    >>> from app.preflight.admin_risk_checks import run_all_admin_risk_checks
    >>> results = await run_all_admin_risk_checks()
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.identity import PrivilegedUser
from app.preflight.base import BasePreflightCheck
from app.preflight.models import CheckCategory, CheckResult, CheckStatus

logger = logging.getLogger(__name__)

# Thresholds for risk detection
OVERPRIVILEGED_ROLE_THRESHOLD = 3  # More than this many roles is concerning
INACTIVE_ADMIN_DAYS = 90  # Days of inactivity to flag
SHARED_ACCOUNT_INDICATORS = ["admin", "service", "shared", "svc-"]
CRITICAL_ROLES = [
    "Global Administrator",
    "Privileged Role Administrator",
    "User Administrator",
    "Security Administrator",
]


class AdminRiskSeverity:
    """Severity levels for admin risk checks."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AdminMfaCheck(BasePreflightCheck):
    """Check that privileged accounts have MFA enabled.

    Verifies that all privileged users (admins) have MFA enabled
    as a basic security requirement for privileged access.
    """

    def __init__(self):
        super().__init__(
            check_id="admin_mfa_enabled",
            name="Privileged Account MFA Status",
            category=CheckCategory.AZURE_SECURITY,
            description="Verify all privileged accounts have MFA enabled",
            timeout_seconds=15.0,
        )

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute MFA check for privileged accounts."""
        start_time = datetime.utcnow()
        db: Session | None = None

        try:
            db = SessionLocal()

            # Query privileged users without MFA
            query = db.query(PrivilegedUser).filter(PrivilegedUser.mfa_enabled == 0)

            if tenant_id:
                query = query.filter(PrivilegedUser.tenant_id == tenant_id)

            users_without_mfa = query.all()

            # Group by user to avoid duplicates (same user, multiple roles)
            unique_users: dict[str, dict[str, Any]] = {}
            for user in users_without_mfa:
                if user.user_principal_name not in unique_users:
                    unique_users[user.user_principal_name] = {
                        "display_name": user.display_name,
                        "roles": [],
                        "is_critical": False,
                    }
                unique_users[user.user_principal_name]["roles"].append(user.role_name)
                if user.role_name in CRITICAL_ROLES:
                    unique_users[user.user_principal_name]["is_critical"] = True

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            if unique_users:
                critical_count = sum(1 for u in unique_users.values() if u["is_critical"])

                if critical_count > 0:
                    status = CheckStatus.FAIL
                    severity = AdminRiskSeverity.CRITICAL
                    message = (
                        f"{len(unique_users)} privileged accounts without MFA "
                        f"({critical_count} with critical roles)"
                    )
                else:
                    status = CheckStatus.WARNING
                    severity = AdminRiskSeverity.HIGH
                    message = f"{len(unique_users)} privileged accounts without MFA"

                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=status,
                    message=message,
                    details={
                        "accounts_without_mfa": len(unique_users),
                        "critical_role_count": critical_count,
                        "severity": severity,
                        "accounts": [
                            {
                                "user_principal_name": upn,
                                "display_name": info["display_name"],
                                "roles": info["roles"],
                                "has_critical_role": info["is_critical"],
                            }
                            for upn, info in unique_users.items()
                        ],
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Enable MFA for all privileged accounts immediately",
                        "Require MFA for administrative role assignments",
                        "Use Conditional Access policies to enforce MFA for admins",
                        "Review and update PIM settings to require MFA activation",
                        "Consider emergency access accounts with secure MFA",
                    ],
                    tenant_id=tenant_id,
                )

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.PASS,
                message="All privileged accounts have MFA enabled",
                details={
                    "accounts_checked": db.query(PrivilegedUser)
                    .filter(PrivilegedUser.tenant_id == tenant_id if tenant_id else True)
                    .distinct(PrivilegedUser.user_principal_name)
                    .count(),
                    "severity": AdminRiskSeverity.INFO,
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
                message=f"Failed to check MFA status: {str(e)}",
                details={
                    "error_type": type(e).__name__,
                    "severity": AdminRiskSeverity.CRITICAL,
                },
                duration_ms=duration_ms,
                recommendations=[
                    "Verify database connectivity",
                    "Check identity sync job is running correctly",
                    "Review application logs for errors",
                ],
                tenant_id=tenant_id,
            )
        finally:
            if db:
                db.close()


class OverprivilegedAccountCheck(BasePreflightCheck):
    """Check for accounts with too many privileged roles.

    Identifies users who have been assigned multiple administrative
    roles, which violates the principle of least privilege.
    """

    def __init__(self):
        super().__init__(
            check_id="admin_overprivileged",
            name="Overprivileged Account Detection",
            category=CheckCategory.AZURE_SECURITY,
            description="Identify accounts with excessive role assignments",
            timeout_seconds=15.0,
        )

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute overprivileged account check."""
        start_time = datetime.utcnow()
        db: Session | None = None

        try:
            db = SessionLocal()

            # Get all privileged users
            query = db.query(PrivilegedUser)
            if tenant_id:
                query = query.filter(PrivilegedUser.tenant_id == tenant_id)

            users = query.all()

            # Count roles per user
            user_roles: dict[str, dict[str, Any]] = defaultdict(
                lambda: {"roles": [], "display_name": "", "tenant_id": ""}
            )
            for user in users:
                user_roles[user.user_principal_name]["roles"].append(
                    {
                        "name": user.role_name,
                        "scope": user.role_scope,
                        "is_permanent": bool(user.is_permanent),
                    }
                )
                user_roles[user.user_principal_name]["display_name"] = user.display_name
                user_roles[user.user_principal_name]["tenant_id"] = user.tenant_id

            # Find overprivileged users
            overprivileged = []
            for upn, data in user_roles.items():
                role_count = len(data["roles"])
                if role_count > OVERPRIVILEGED_ROLE_THRESHOLD:
                    has_critical = any(r["name"] in CRITICAL_ROLES for r in data["roles"])
                    overprivileged.append(
                        {
                            "user_principal_name": upn,
                            "display_name": data["display_name"],
                            "tenant_id": data["tenant_id"],
                            "role_count": role_count,
                            "roles": [r["name"] for r in data["roles"]],
                            "has_critical_role": has_critical,
                        }
                    )

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            if overprivileged:
                critical_count = sum(1 for u in overprivileged if u["has_critical_role"])

                if critical_count > 0:
                    status = CheckStatus.FAIL
                    severity = AdminRiskSeverity.CRITICAL
                else:
                    status = CheckStatus.WARNING
                    severity = AdminRiskSeverity.MEDIUM

                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=status,
                    message=(
                        f"{len(overprivileged)} accounts with excessive "
                        f"privileges (> {OVERPRIVILEGED_ROLE_THRESHOLD} roles)"
                    ),
                    details={
                        "overprivileged_count": len(overprivileged),
                        "critical_role_violations": critical_count,
                        "role_threshold": OVERPRIVILEGED_ROLE_THRESHOLD,
                        "severity": severity,
                        "accounts": overprivileged,
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Review role assignments and remove unnecessary privileges",
                        "Apply principle of least privilege - one role per user where possible",
                        "Use PIM for temporary access instead of permanent assignments",
                        "Consider role consolidation - create custom roles for specific needs",
                        "Audit role assignments quarterly",
                        "Document business justification for multiple role assignments",
                    ],
                    tenant_id=tenant_id,
                )

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.PASS,
                message="No overprivileged accounts detected",
                details={
                    "accounts_checked": len(user_roles),
                    "role_threshold": OVERPRIVILEGED_ROLE_THRESHOLD,
                    "severity": AdminRiskSeverity.INFO,
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
                message=f"Failed to check for overprivileged accounts: {str(e)}",
                details={
                    "error_type": type(e).__name__,
                    "severity": AdminRiskSeverity.CRITICAL,
                },
                duration_ms=duration_ms,
                recommendations=[
                    "Verify database connectivity",
                    "Check identity sync job is running correctly",
                    "Review application logs for errors",
                ],
                tenant_id=tenant_id,
            )
        finally:
            if db:
                db.close()


class InactiveAdminCheck(BasePreflightCheck):
    """Check for inactive administrative accounts.

    Identifies privileged accounts that haven't signed in for
    90+ days, which may indicate stale credentials or
    unnecessary access.
    """

    def __init__(self):
        super().__init__(
            check_id="admin_inactive",
            name="Inactive Administrator Detection",
            category=CheckCategory.AZURE_SECURITY,
            description="Identify admin accounts inactive for 90+ days",
            timeout_seconds=15.0,
        )

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute inactive admin check."""
        start_time = datetime.utcnow()
        db: Session | None = None

        try:
            db = SessionLocal()

            # Calculate the threshold date
            threshold_date = datetime.utcnow() - timedelta(days=INACTIVE_ADMIN_DAYS)

            # Find inactive admins
            query = db.query(PrivilegedUser).filter(PrivilegedUser.last_sign_in < threshold_date)

            if tenant_id:
                query = query.filter(PrivilegedUser.tenant_id == tenant_id)

            inactive_users = query.all()

            # Group by user and calculate days inactive
            unique_users: dict[str, dict[str, Any]] = {}
            for user in inactive_users:
                if user.user_principal_name not in unique_users:
                    days_inactive = (
                        (datetime.utcnow() - user.last_sign_in).days if user.last_sign_in else None
                    )

                    unique_users[user.user_principal_name] = {
                        "display_name": user.display_name,
                        "last_sign_in": (
                            user.last_sign_in.isoformat() if user.last_sign_in else None
                        ),
                        "days_inactive": days_inactive,
                        "roles": [],
                        "has_critical_role": False,
                        "mfa_enabled": bool(user.mfa_enabled),
                    }

                unique_users[user.user_principal_name]["roles"].append(user.role_name)
                if user.role_name in CRITICAL_ROLES:
                    unique_users[user.user_principal_name]["has_critical_role"] = True

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            if unique_users:
                critical_count = sum(1 for u in unique_users.values() if u["has_critical_role"])
                without_mfa = sum(1 for u in unique_users.values() if not u["mfa_enabled"])

                # Determine severity based on critical roles
                if critical_count > 0:
                    status = CheckStatus.FAIL
                    severity = AdminRiskSeverity.CRITICAL
                else:
                    status = CheckStatus.WARNING
                    severity = AdminRiskSeverity.MEDIUM

                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=status,
                    message=(
                        f"{len(unique_users)} inactive admin accounts (>{INACTIVE_ADMIN_DAYS} days)"
                    ),
                    details={
                        "inactive_count": len(unique_users),
                        "inactive_days_threshold": INACTIVE_ADMIN_DAYS,
                        "critical_role_inactive": critical_count,
                        "without_mfa": without_mfa,
                        "severity": severity,
                        "accounts": [
                            {
                                "user_principal_name": upn,
                                "display_name": info["display_name"],
                                "last_sign_in": info["last_sign_in"],
                                "days_inactive": info["days_inactive"],
                                "roles": info["roles"],
                                "has_critical_role": info["has_critical_role"],
                                "mfa_enabled": info["mfa_enabled"],
                            }
                            for upn, info in unique_users.items()
                        ],
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Review and disable/remove inactive admin accounts",
                        "Require re-authentication for dormant accounts before reactivation",
                        "Implement automated access reviews for privileged roles",
                        "Set up alerts for accounts inactive > 30 days",
                        "Document and justify any exceptions for inactive accounts",
                        "Consider breaking glass accounts with documented procedures",
                    ],
                    tenant_id=tenant_id,
                )

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.PASS,
                message="No inactive admin accounts detected",
                details={
                    "inactive_days_threshold": INACTIVE_ADMIN_DAYS,
                    "severity": AdminRiskSeverity.INFO,
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
                message=f"Failed to check for inactive admins: {str(e)}",
                details={
                    "error_type": type(e).__name__,
                    "severity": AdminRiskSeverity.CRITICAL,
                },
                duration_ms=duration_ms,
                recommendations=[
                    "Verify database connectivity",
                    "Check identity sync job is running correctly",
                    "Review application logs for errors",
                ],
                tenant_id=tenant_id,
            )
        finally:
            if db:
                db.close()


class SharedAdminCheck(BasePreflightCheck):
    """Check for shared administrative accounts.

    Identifies accounts that appear to be shared based on naming
    conventions or usage patterns, which is a security risk
    for privileged access.
    """

    def __init__(self):
        super().__init__(
            check_id="admin_shared_accounts",
            name="Shared Admin Account Detection",
            category=CheckCategory.AZURE_SECURITY,
            description="Identify shared or service admin accounts",
            timeout_seconds=15.0,
        )

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute shared admin account check."""
        start_time = datetime.utcnow()
        db: Session | None = None

        try:
            db = SessionLocal()

            # Get all privileged users
            query = db.query(PrivilegedUser)
            if tenant_id:
                query = query.filter(PrivilegedUser.tenant_id == tenant_id)

            users = query.all()

            # Identify potential shared accounts
            shared_accounts = []
            seen_users = set()

            for user in users:
                upn_lower = user.user_principal_name.lower()

                # Skip if we've already processed this user
                if user.user_principal_name in seen_users:
                    continue
                seen_users.add(user.user_principal_name)

                # Check for shared account indicators
                is_shared = any(indicator in upn_lower for indicator in SHARED_ACCOUNT_INDICATORS)

                # Check if it looks like a service account
                is_service = (
                    "svc" in upn_lower or "service" in upn_lower or upn_lower.startswith("sa-")
                )

                if is_shared or is_service:
                    # Get all roles for this user
                    user_query = db.query(PrivilegedUser).filter(
                        PrivilegedUser.user_principal_name == user.user_principal_name
                    )
                    if tenant_id:
                        user_query = user_query.filter(PrivilegedUser.tenant_id == tenant_id)

                    user_roles = user_query.all()
                    roles = [r.role_name for r in user_roles]
                    has_critical = any(r in CRITICAL_ROLES for r in roles)

                    shared_accounts.append(
                        {
                            "user_principal_name": user.user_principal_name,
                            "display_name": user.display_name,
                            "account_type": ("service" if is_service else "shared"),
                            "roles": roles,
                            "role_count": len(roles),
                            "has_critical_role": has_critical,
                            "mfa_enabled": bool(user.mfa_enabled),
                            "last_sign_in": (
                                user.last_sign_in.isoformat() if user.last_sign_in else None
                            ),
                            "match_reason": (
                                "contains_shared_indicator"
                                if is_shared
                                else "service_account_pattern"
                            ),
                        }
                    )

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            if shared_accounts:
                critical_count = sum(1 for a in shared_accounts if a["has_critical_role"])
                without_mfa = sum(1 for a in shared_accounts if not a["mfa_enabled"])

                if critical_count > 0:
                    status = CheckStatus.FAIL
                    severity = AdminRiskSeverity.CRITICAL
                else:
                    status = CheckStatus.WARNING
                    severity = AdminRiskSeverity.HIGH

                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=status,
                    message=(f"{len(shared_accounts)} shared/service admin accounts detected"),
                    details={
                        "shared_account_count": len(shared_accounts),
                        "with_critical_roles": critical_count,
                        "without_mfa": without_mfa,
                        "severity": severity,
                        "shared_indicators": SHARED_ACCOUNT_INDICATORS,
                        "accounts": shared_accounts,
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Eliminate shared admin accounts - assign individual accounts",
                        "Use Azure AD PIM for shared responsibilities",
                        "Implement privileged access workstations (PAW) for admin tasks",
                        "Enable MFA on all shared accounts immediately",
                        "Document and audit all service account usage",
                        "Use managed identities instead of service accounts where possible",
                        "Implement regular credential rotation for service accounts",
                    ],
                    tenant_id=tenant_id,
                )

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.PASS,
                message="No shared admin accounts detected",
                details={
                    "accounts_checked": len(seen_users),
                    "shared_indicators_checked": SHARED_ACCOUNT_INDICATORS,
                    "severity": AdminRiskSeverity.INFO,
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
                message=f"Failed to check for shared accounts: {str(e)}",
                details={
                    "error_type": type(e).__name__,
                    "severity": AdminRiskSeverity.CRITICAL,
                },
                duration_ms=duration_ms,
                recommendations=[
                    "Verify database connectivity",
                    "Check identity sync job is running correctly",
                    "Review application logs for errors",
                ],
                tenant_id=tenant_id,
            )
        finally:
            if db:
                db.close()


class AdminComplianceGapCheck(BasePreflightCheck):
    """Check for compliance gaps in privileged access.

    Performs an overall compliance assessment of privileged
    access controls and reports gaps against security baselines.
    """

    def __init__(self):
        super().__init__(
            check_id="admin_compliance_gaps",
            name="Privileged Access Compliance Assessment",
            category=CheckCategory.AZURE_SECURITY,
            description="Overall compliance assessment for privileged access",
            timeout_seconds=20.0,
        )

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute compliance gap assessment."""
        start_time = datetime.utcnow()
        db: Session | None = None

        try:
            db = SessionLocal()

            # Get all privileged users for the tenant
            query = db.query(PrivilegedUser)
            if tenant_id:
                query = query.filter(PrivilegedUser.tenant_id == tenant_id)

            users = query.all()

            if not users:
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.SKIPPED,
                    message="No privileged users found to assess",
                    details={
                        "severity": AdminRiskSeverity.INFO,
                        "reason": "no_privileged_users",
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Verify identity sync is configured correctly",
                        "Check Azure AD role assignments",
                        "Ensure service principal has required permissions",
                    ],
                    tenant_id=tenant_id,
                )

            # Calculate compliance metrics
            total_unique_users = len({u.user_principal_name for u in users})

            # MFA compliance
            users_without_mfa = set()
            for user in users:
                if not user.mfa_enabled:
                    users_without_mfa.add(user.user_principal_name)

            mfa_compliance_rate = (
                ((total_unique_users - len(users_without_mfa)) / total_unique_users) * 100
                if total_unique_users > 0
                else 0
            )

            # Inactive accounts
            threshold_date = datetime.utcnow() - timedelta(days=INACTIVE_ADMIN_DAYS)
            inactive_users = set()
            for user in users:
                if user.last_sign_in and user.last_sign_in < threshold_date:
                    inactive_users.add(user.user_principal_name)

            # Overprivileged accounts
            user_role_counts: dict[str, int] = defaultdict(int)
            for user in users:
                user_role_counts[user.user_principal_name] += 1

            overprivileged = [
                upn
                for upn, count in user_role_counts.items()
                if count > OVERPRIVILEGED_ROLE_THRESHOLD
            ]

            # Shared accounts
            shared_accounts = []
            for user in users:
                upn_lower = user.user_principal_name.lower()
                if any(ind in upn_lower for ind in SHARED_ACCOUNT_INDICATORS):
                    if user.user_principal_name not in shared_accounts:
                        shared_accounts.append(user.user_principal_name)

            # Calculate overall compliance score
            compliance_issues = len(users_without_mfa) + len(inactive_users) + len(overprivileged)
            compliance_score = max(
                0,
                100
                - (compliance_issues / total_unique_users * 100 if total_unique_users > 0 else 0),
            )

            # Determine status based on compliance score
            if compliance_score >= 90:
                status = CheckStatus.PASS
                severity = AdminRiskSeverity.LOW
            elif compliance_score >= 75:
                status = CheckStatus.WARNING
                severity = AdminRiskSeverity.MEDIUM
            elif compliance_score >= 50:
                status = CheckStatus.WARNING
                severity = AdminRiskSeverity.HIGH
            else:
                status = CheckStatus.FAIL
                severity = AdminRiskSeverity.CRITICAL

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=status,
                message=(
                    f"Compliance score: {compliance_score:.1f}% ({compliance_issues} issues found)"
                ),
                details={
                    "compliance_score": round(compliance_score, 1),
                    "total_privileged_users": total_unique_users,
                    "mfa_compliance_rate": round(mfa_compliance_rate, 1),
                    "issues": {
                        "without_mfa": len(users_without_mfa),
                        "inactive_accounts": len(inactive_users),
                        "overprivileged": len(overprivileged),
                        "shared_accounts": len(shared_accounts),
                    },
                    "severity": severity,
                    "thresholds": {
                        "mfa_required": True,
                        "max_roles": OVERPRIVILEGED_ROLE_THRESHOLD,
                        "inactive_days": INACTIVE_ADMIN_DAYS,
                    },
                },
                duration_ms=duration_ms,
                recommendations=self._generate_recommendations(
                    compliance_score,
                    len(users_without_mfa),
                    len(inactive_users),
                    len(overprivileged),
                    len(shared_accounts),
                ),
                tenant_id=tenant_id,
            )

        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"Failed to assess compliance: {str(e)}",
                details={
                    "error_type": type(e).__name__,
                    "severity": AdminRiskSeverity.CRITICAL,
                },
                duration_ms=duration_ms,
                recommendations=[
                    "Verify database connectivity",
                    "Check identity sync job is running correctly",
                    "Review application logs for errors",
                ],
                tenant_id=tenant_id,
            )
        finally:
            if db:
                db.close()

    def _generate_recommendations(
        self,
        compliance_score: float,
        without_mfa: int,
        inactive: int,
        overprivileged: int,
        shared: int,
    ) -> list[str]:
        """Generate recommendations based on compliance issues."""
        recommendations = []

        if compliance_score < 50:
            recommendations.append(
                "CRITICAL: Immediate action required - compliance score below 50%"
            )

        if without_mfa > 0:
            recommendations.append(f"Enable MFA for {without_mfa} privileged accounts immediately")

        if inactive > 0:
            recommendations.append(f"Review and disable {inactive} inactive admin accounts")

        if overprivileged > 0:
            recommendations.append(
                f"Review role assignments for {overprivileged} overprivileged accounts"
            )

        if shared > 0:
            recommendations.append(f"Eliminate {shared} shared admin accounts")

        # General recommendations
        recommendations.extend(
            [
                "Implement regular access reviews for privileged roles",
                "Use Azure AD PIM for just-in-time privileged access",
                "Enable Conditional Access policies for admin accounts",
                "Document and regularly audit all privileged access",
                "Consider implementing privileged access workstations (PAW)",
            ]
        )

        return recommendations


# Convenience functions for running all checks


def get_admin_risk_checks() -> dict[str, BasePreflightCheck]:
    """Get all admin risk check instances.

    Returns:
        Dictionary mapping check_id to check instance
    """
    return {
        "admin_mfa_enabled": AdminMfaCheck(),
        "admin_overprivileged": OverprivilegedAccountCheck(),
        "admin_inactive": InactiveAdminCheck(),
        "admin_shared_accounts": SharedAdminCheck(),
        "admin_compliance_gaps": AdminComplianceGapCheck(),
    }


async def run_all_admin_risk_checks(
    tenant_id: str | None = None,
) -> list[CheckResult]:
    """Run all admin risk checks.

    Args:
        tenant_id: Optional tenant ID to scope checks to

    Returns:
        List of CheckResult objects
    """
    checks = get_admin_risk_checks()
    results = []

    for check in checks.values():
        result = await check.run(tenant_id=tenant_id)
        results.append(result)

    return results
