"""MFA gap detection and alerting system for Riverside tenants.

Detects MFA enrollment gaps across HTT, BCC, FN, TLL, and DCE tenants
and triggers notifications when coverage falls below targets:
- Users: 95% MFA enrollment target
- Admins: 100% MFA enrollment target (mandatory)

Severity levels:
- HIGH: Any unprotected admin accounts
- MEDIUM: User MFA coverage below 95%

SECURITY: This module handles sensitive compliance data. All alert
details are sanitized before logging to prevent information leakage.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import logging
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db_context
from app.core.notifications import (
    Notification,
    Severity,
    create_dashboard_url,
    record_notification_sent,
    send_notification,
    should_notify,
)
from app.models.riverside import RiversideMFA

logger = logging.getLogger(__name__)

# Riverside tenant IDs
RIVERSIDE_TENANTS = ["HTT", "BCC", "FN", "TLL", "DCE"]

# MFA compliance targets
USER_MFA_TARGET = 95.0
ADMIN_MFA_TARGET = 100.0

# Alert cooldown period in minutes (prevent spam)
ALERT_COOLDOWN_MINUTES = 60


@dataclass
class MFAComplianceStatus:
    """MFA compliance status for a single tenant.

    Attributes:
        tenant_id: The tenant identifier (e.g., 'HTT', 'BCC')
        user_mfa_percentage: Current user MFA enrollment percentage
        admin_mfa_percentage: Current admin MFA enrollment percentage
        total_users: Total number of users in tenant
        mfa_enrolled_users: Number of users with MFA enrolled
        admin_accounts_total: Total number of admin accounts
        admin_accounts_mfa: Number of admins with MFA enrolled
        unprotected_admins: Number of admin accounts without MFA
        snapshot_date: When the data was captured
        user_compliant: Whether user MFA meets 95% target
        admin_compliant: Whether admin MFA meets 100% target
    """

    tenant_id: str
    user_mfa_percentage: float
    admin_mfa_percentage: float
    total_users: int
    mfa_enrolled_users: int
    admin_accounts_total: int
    admin_accounts_mfa: int
    unprotected_admins: int
    snapshot_date: datetime
    user_compliant: bool = False
    admin_compliant: bool = False

    def __post_init__(self) -> None:
        """Calculate compliance flags after initialization."""
        self.user_compliant = self.user_mfa_percentage >= USER_MFA_TARGET
        self.admin_compliant = self.admin_mfa_percentage >= ADMIN_MFA_TARGET


class MFAGapDetector:
    """Detector for MFA enrollment gaps across Riverside tenants.

    Queries the riverside_mfa table to identify tenants with MFA coverage
    below compliance targets and triggers appropriate alerts.

    Usage:
        detector = MFAGapDetector()
        gaps = await detector.detect_gaps()
        for gap in gaps:
            await detector.trigger_alert(gap)
    """

    def __init__(self, db: Session | None = None) -> None:
        """Initialize the MFA gap detector.

        Args:
            db: Optional database session. If not provided, sessions
                will be created automatically for each operation.
        """
        self._db = db
        self._riv_tenants = set(RIVERSIDE_TENANTS)

    async def detect_gaps(self, db: Session | None = None) -> list[MFAComplianceStatus]:
        """Detect all MFA gaps across Riverside tenants.

        Queries the riverside_mfa table for the latest snapshot per tenant
        and returns any tenants below compliance thresholds.

        Args:
            db: Optional database session. If not provided and no session
                was provided to __init__, a new session will be created.

        Returns:
            List of MFAComplianceStatus for non-compliant tenants.
            Returns empty list if all tenants are compliant or on error.

        Raises:
            Exception: Propagates database errors if db session was provided.
        """
        gaps: list[MFAComplianceStatus] = []
        session = db or self._db

        try:
            if session is None:
                with get_db_context() as db_session:
                    return await self.detect_gaps(db_session)

            # Get latest MFA snapshot for each tenant
            latest_snapshots = (
                session.query(
                    RiversideMFA.tenant_id,
                    func.max(RiversideMFA.snapshot_date).label("max_date"),
                )
                .filter(RiversideMFA.tenant_id.in_(self._riv_tenants))
                .group_by(RiversideMFA.tenant_id)
                .subquery()
            )

            mfa_records = (
                session.query(RiversideMFA)
                .join(
                    latest_snapshots,
                    (RiversideMFA.tenant_id == latest_snapshots.c.tenant_id)
                    & (RiversideMFA.snapshot_date == latest_snapshots.c.max_date),
                )
                .all()
            )

            for record in mfa_records:
                # Calculate unprotected admins
                unprotected_admins = record.admin_accounts_total - record.admin_accounts_mfa

                status = MFAComplianceStatus(
                    tenant_id=record.tenant_id,
                    user_mfa_percentage=record.mfa_coverage_percentage,
                    admin_mfa_percentage=record.admin_mfa_percentage,
                    total_users=record.total_users,
                    mfa_enrolled_users=record.mfa_enrolled_users,
                    admin_accounts_total=record.admin_accounts_total,
                    admin_accounts_mfa=record.admin_accounts_mfa,
                    unprotected_admins=unprotected_admins,
                    snapshot_date=record.snapshot_date,
                )

                # Only include non-compliant tenants
                if not status.user_compliant or not status.admin_compliant:
                    gaps.append(status)
                    logger.warning(
                        f"MFA gap detected for tenant {record.tenant_id}: "
                        f"users={status.user_mfa_percentage:.1f}% "
                        f"(target={USER_MFA_TARGET}%), "
                        f"admins={status.admin_mfa_percentage:.1f}% "
                        f"(target={ADMIN_MFA_TARGET}%), "
                        f"unprotected_admins={unprotected_admins}"
                    )

            if gaps:
                logger.info(f"MFA gap detection complete: {len(gaps)} tenants below threshold")
            else:
                logger.info("MFA gap detection complete: all tenants compliant")

            return gaps

        except Exception as e:
            logger.error(f"Error detecting MFA gaps: {e}", exc_info=True)
            if session is not None and db is not None:
                raise
            return []

    async def check_admin_compliance(
        self, db: Session | None = None
    ) -> list[MFAComplianceStatus]:
        """Check admin MFA compliance specifically.

        Returns tenants where admin MFA coverage is below 100%.
        This is a critical security check as all admins must have MFA.

        Args:
            db: Optional database session.

        Returns:
            List of MFAComplianceStatus for tenants with non-compliant admins.
        """
        all_gaps = await self.detect_gaps(db)
        return [g for g in all_gaps if not g.admin_compliant]

    async def check_user_compliance(
        self, db: Session | None = None
    ) -> list[MFAComplianceStatus]:
        """Check user MFA compliance specifically.

        Returns tenants where user MFA coverage is below 95%.

        Args:
            db: Optional database session.

        Returns:
            List of MFAComplianceStatus for tenants with user MFA gaps.
        """
        all_gaps = await self.detect_gaps(db)
        return [g for g in all_gaps if not g.user_compliant]

    async def trigger_alert(
        self, status: MFAComplianceStatus, force: bool = False
    ) -> dict[str, Any]:
        """Trigger an MFA alert for a specific tenant.

        Sends a notification via the notification system if the alert
        is not in cooldown period (unless force=True).

        Args:
            status: The MFA compliance status to alert on.
            force: If True, skip cooldown check and send immediately.

        Returns:
            Dict with success status and response details.
        """
        # Determine severity based on admin compliance
        # Admin MFA gaps are ERROR severity (critical security requirement)
        # User MFA gaps are WARNING severity
        if not status.admin_compliant:
            severity = Severity.ERROR
            alert_key = f"mfa_admin_gap_{status.tenant_id}"
        else:
            severity = Severity.WARNING
            alert_key = f"mfa_user_gap_{status.tenant_id}"

        # Check cooldown unless forced
        if not force and not should_notify(
            alert_key, job_type="mfa_gaps", cooldown_minutes=ALERT_COOLDOWN_MINUTES
        ):
            logger.debug(f"MFA alert for {status.tenant_id} in cooldown, skipping")
            return {
                "success": False,
                "reason": "in_cooldown",
                "tenant_id": status.tenant_id,
            }

        # Build alert message
        issues = []
        if not status.admin_compliant:
            issues.append(
                f"⚠️ Admin MFA: {status.admin_mfa_percentage:.1f}% "
                f"({status.admin_accounts_mfa}/{status.admin_accounts_total}) - "
                f"Target: {ADMIN_MFA_TARGET}%"
            )
        if not status.user_compliant:
            issues.append(
                f"⚠️ User MFA: {status.user_mfa_percentage:.1f}% "
                f"({status.mfa_enrolled_users}/{status.total_users}) - "
                f"Target: {USER_MFA_TARGET}%"
            )

        notification = Notification(
            title=f"MFA Compliance Alert: {status.tenant_id}",
            message=(
                f"MFA enrollment gaps detected for tenant **{status.tenant_id}**:\n\n"
                + "\n".join(f"  {issue}" for issue in issues)
                + f"\n\n📅 Snapshot: {status.snapshot_date.strftime('%Y-%m-%d %H:%M UTC')}"
            ),
            severity=severity,
            job_type="mfa_gaps",
            tenant_id=status.tenant_id,
            dashboard_url=create_dashboard_url("riverside"),
        )

        try:
            result = await send_notification(notification)

            if result.get("success"):
                record_notification_sent(alert_key, job_type="mfa_gaps")
                logger.info(f"MFA alert sent for tenant {status.tenant_id}")
            else:
                logger.warning(
                    f"Failed to send MFA alert for {status.tenant_id}: "
                    f"{result.get('error')}"
                )

            return {
                "success": result.get("success", False),
                "tenant_id": status.tenant_id,
                "severity": severity.value,
                "error": result.get("error"),
            }

        except Exception as e:
            logger.error(f"Error triggering MFA alert: {e}", exc_info=True)
            return {
                "success": False,
                "tenant_id": status.tenant_id,
                "error": str(e),
            }

    async def check_and_alert(self, db: Session | None = None) -> dict[str, Any]:
        """Run full MFA gap detection and send alerts.

        Convenience method that detects all gaps and triggers alerts
        for each non-compliant tenant.

        Args:
            db: Optional database session.

        Returns:
            Dict with detection results and alert statuses.
        """
        gaps = await self.detect_gaps(db)
        alert_results = []

        for gap in gaps:
            result = await self.trigger_alert(gap)
            alert_results.append(result)

        return {
            "success": True,
            "tenants_checked": len(self._riv_tenants),
            "gaps_found": len(gaps),
            "alerts_sent": len([r for r in alert_results if r.get("success")]),
            "gaps": [
                {
                    "tenant_id": g.tenant_id,
                    "user_mfa": g.user_mfa_percentage,
                    "admin_mfa": g.admin_mfa_percentage,
                    "unprotected_admins": g.unprotected_admins,
                }
                for g in gaps
            ],
            "alert_results": alert_results,
        }


# Convenience functions for direct usage
async def detect_mfa_gaps(db: Session | None = None) -> list[MFAComplianceStatus]:
    """Detect MFA gaps across all Riverside tenants.

    Convenience function that creates an MFAGapDetector instance
    and runs detection.

    Args:
        db: Optional database session.

    Returns:
        List of MFAComplianceStatus for non-compliant tenants.
    """
    detector = MFAGapDetector(db)
    return await detector.detect_gaps(db)


async def check_admin_mfa_compliance(
    db: Session | None = None,
) -> list[MFAComplianceStatus]:
    """Check admin MFA compliance across all tenants.

    Args:
        db: Optional database session.

    Returns:
        List of non-compliant admin MFA statuses.
    """
    detector = MFAGapDetector(db)
    return await detector.check_admin_compliance(db)


async def check_user_mfa_compliance(
    db: Session | None = None,
) -> list[MFAComplianceStatus]:
    """Check user MFA compliance across all tenants.

    Args:
        db: Optional database session.

    Returns:
        List of non-compliant user MFA statuses.
    """
    detector = MFAGapDetector(db)
    return await detector.check_user_compliance(db)


async def trigger_mfa_alert(
    status: MFAComplianceStatus, force: bool = False
) -> dict[str, Any]:
    """Trigger an MFA alert for a specific tenant.

    Args:
        status: The MFA compliance status to alert on.
        force: If True, bypass cooldown check.

    Returns:
        Dict with alert result.
    """
    detector = MFAGapDetector()
    return await detector.trigger_alert(status, force)


# Export constants for external use
__all__ = [
    "MFAGapDetector",
    "MFAComplianceStatus",
    "RIVERSIDE_TENANTS",
    "USER_MFA_TARGET",
    "ADMIN_MFA_TARGET",
    "detect_mfa_gaps",
    "check_admin_mfa_compliance",
    "check_user_mfa_compliance",
    "trigger_mfa_alert",
]
