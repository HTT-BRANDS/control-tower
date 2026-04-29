"""Riverside maturity score synchronization."""

from datetime import UTC, datetime

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
from app.services.riverside_sync.common import (
    RIVERSIDE_DEADLINE,
    TARGET_MATURITY_SCORE,
    SyncError,
    logger,
)


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
    snapshot_date = snapshot_date or datetime.now(UTC)

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
                .filter(RiversideMFA.tenant_id == tenant.id)
                .order_by(RiversideMFA.snapshot_date.desc())
                .first()
            )

            # Get latest device compliance data
            device_data = (
                session.query(RiversideDeviceCompliance)
                .filter(RiversideDeviceCompliance.tenant_id == tenant.id)
                .order_by(RiversideDeviceCompliance.snapshot_date.desc())
                .first()
            )

            # Get requirements data
            total_reqs = (
                session.query(RiversideRequirement)
                .filter(RiversideRequirement.tenant_id == tenant.id)
                .count()
            )

            completed_reqs = (
                session.query(RiversideRequirement)
                .filter(
                    RiversideRequirement.tenant_id == tenant.id,
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
                    RiversideRequirement.tenant_id == tenant.id,
                    RiversideRequirement.status != RequirementStatus.COMPLETED.value,
                    RiversideRequirement.priority == RequirementPriority.P0.value,
                )
                .count()
            )

            # Get or create compliance record
            compliance_record = (
                session.query(RiversideCompliance)
                .filter(RiversideCompliance.tenant_id == tenant.id)
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
                    tenant_id=tenant.id,
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
            session.rollback()
            error_msg = f"Unexpected error syncing maturity scores: {e}"
            logger.error(error_msg)
            raise SyncError(error_msg, tenant_id) from e

    if db:
        return _do_sync(db)
    else:
        with get_db_context() as session:
            return _do_sync(session)
