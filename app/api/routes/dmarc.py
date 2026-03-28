"""DMARC/DKIM API routes.

Endpoints for email security monitoring and compliance tracking
for Riverside Company tenants.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.services.dmarc_service import DMARCService
from app.core.auth import get_current_user
from app.core.database import get_db

router = APIRouter(
    prefix="/api/v1/dmarc",
    tags=["dmarc"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/summary")
async def get_dmarc_summary(
    tenant_id: str | None = Query(None, description="Filter by tenant ID"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get DMARC/DKIM summary across tenants.

    Returns aggregated statistics including:
    - Total domains configured
    - DMARC policy compliance rates
    - DKIM enablement status
    - Security scores per tenant
    - Recent authentication failures
    - Active alerts
    """
    service = DMARCService(db)
    return await service.get_dmarc_summary(tenant_id)


@router.get("/records")
async def get_dmarc_records(
    tenant_id: str = Query(..., description="Tenant ID to query"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get DMARC records for a tenant.

    Returns all DMARC DNS records configured for the tenant's domains
    with policy details and validation status.
    """
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id is required")

    service = DMARCService(db)
    records = service.get_dmarc_records(tenant_id)

    return [
        {
            "id": r.id,
            "domain": r.domain,
            "policy": r.policy,
            "pct": r.pct,
            "rua": r.rua,
            "ruf": r.ruf,
            "adkim": r.adkim,
            "aspf": r.aspf,
            "is_valid": r.is_valid,
            "validation_errors": r.validation_errors,
            "synced_at": r.synced_at.isoformat() if r.synced_at else None,
        }
        for r in records
    ]


@router.get("/dkim")
async def get_dkim_records(
    tenant_id: str = Query(..., description="Tenant ID to query"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get DKIM records for a tenant.

    Returns all DKIM signing configurations including key status,
    alignment, and rotation dates.
    """
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id is required")

    service = DMARCService(db)
    records = service.get_dkim_records(tenant_id)

    return [
        {
            "id": r.id,
            "domain": r.domain,
            "selector": r.selector,
            "is_enabled": r.is_enabled,
            "key_size": r.key_size,
            "key_type": r.key_type,
            "is_aligned": r.is_aligned,
            "is_stale": r.is_key_stale,
            "days_since_rotation": r.days_since_rotation,
            "last_rotated": r.last_rotated.isoformat() if r.last_rotated else None,
            "next_rotation_due": r.next_rotation_due.isoformat() if r.next_rotation_due else None,
            "selector_status": r.selector_status,
            "synced_at": r.synced_at.isoformat() if r.synced_at else None,
        }
        for r in records
    ]


@router.get("/score")
async def get_domain_security_score(
    tenant_id: str = Query(..., description="Tenant ID to query"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get domain security score for a tenant.

    Returns a calculated security score (0-100) based on:
    - DMARC policy strength
    - DKIM enablement and alignment
    - SPF configuration
    """
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id is required")

    service = DMARCService(db)
    score = service.get_domain_security_score(tenant_id)

    return {
        "tenant_id": tenant_id,
        "security_score": score,
        "grade": _score_to_grade(score),
        "status": _score_to_status(score),
        "recommendations": _get_score_recommendations(score),
    }


@router.get("/trends")
async def get_compliance_trends(
    tenant_id: str | None = Query(None, description="Filter by tenant ID"),
    days: int = Query(30, description="Number of days of history", ge=1, le=90),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get DMARC compliance trends over time.

    Returns daily compliance rates showing authentication success/failure
    rates for the specified time period.
    """
    service = DMARCService(db)
    return service.get_compliance_trends(tenant_id, days)


@router.get("/reports")
async def get_dmarc_reports(
    tenant_id: str = Query(..., description="Tenant ID to query"),
    domain: str | None = Query(None, description="Filter by domain"),
    limit: int = Query(50, description="Maximum results", ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get DMARC aggregate reports for a tenant.

    Returns parsed DMARC aggregate reports with authentication breakdowns
    (DKIM/SPF pass/fail rates).
    """
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id is required")

    DMARCService(db)

    # Get reports via service
    from app.models.dmarc import DMARCReport

    query = db.query(DMARCReport).filter(DMARCReport.tenant_id == tenant_id)

    if domain:
        query = query.filter(DMARCReport.domain == domain)

    reports = query.order_by(DMARCReport.report_date.desc()).limit(limit).all()

    return [
        {
            "id": r.id,
            "domain": r.domain,
            "report_date": r.report_date.isoformat() if r.report_date else None,
            "messages_total": r.messages_total,
            "messages_passed": r.messages_passed,
            "messages_failed": r.messages_failed,
            "pct_compliant": r.pct_compliant,
            "dkim_passed": r.dkim_passed,
            "dkim_failed": r.dkim_failed,
            "spf_passed": r.spf_passed,
            "spf_failed": r.spf_failed,
            "both_passed": r.both_passed,
            "both_failed": r.both_failed,
            "source_ip_count": r.source_ip_count,
            "reporter": r.reporter,
        }
        for r in reports
    ]


@router.get("/alerts")
async def get_dmarc_alerts(
    tenant_id: str | None = Query(None, description="Filter by tenant ID"),
    acknowledged: bool | None = Query(None, description="Filter by acknowledged status"),
    severity: str | None = Query(None, description="Filter by severity"),
    limit: int = Query(20, description="Maximum results", ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get DMARC/DKIM security alerts.

    Returns active alerts for security issues like policy changes,
    key rotation failures, or authentication failures.
    """
    from app.models.dmarc import DMARCAlert

    query = db.query(DMARCAlert)

    if tenant_id:
        query = query.filter(DMARCAlert.tenant_id == tenant_id)
    if acknowledged is not None:
        query = query.filter(DMARCAlert.is_acknowledged == acknowledged)
    if severity:
        query = query.filter(DMARCAlert.severity == severity)

    alerts = query.order_by(DMARCAlert.created_at.desc()).limit(limit).all()

    return [
        {
            "id": a.id,
            "tenant_id": a.tenant_id,
            "alert_type": a.alert_type,
            "severity": a.severity,
            "domain": a.domain,
            "message": a.message,
            "details": a.details,
            "is_acknowledged": a.is_acknowledged,
            "acknowledged_by": a.acknowledged_by,
            "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in alerts
    ]


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    user: str = Query(..., description="User acknowledging the alert"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Acknowledge a DMARC/DKIM alert.

    Marks an alert as acknowledged with the user and timestamp.
    """
    service = DMARCService(db)
    alert = await service.acknowledge_alert(alert_id, user)

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return {
        "id": alert.id,
        "is_acknowledged": alert.is_acknowledged,
        "acknowledged_by": alert.acknowledged_by,
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
    }


@router.post("/sync")
async def sync_dmarc_data(
    tenant_id: str = Query(..., description="Tenant ID to sync"),
    sync_type: str = Query("all", description="Type of sync: dmarc, dkim, reports, all"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Trigger DMARC/DKIM sync for a tenant.

    Manually triggers synchronization of DMARC records, DKIM configuration,
    or aggregate reports for the specified tenant.
    """
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id is required")

    service = DMARCService(db)
    results = {"dmarc": 0, "dkim": 0, "reports": 0}

    try:
        if sync_type in ("dmarc", "all"):
            dmarc_records = await service.sync_dmarc_records(tenant_id)
            results["dmarc"] = len(dmarc_records)

        if sync_type in ("dkim", "all"):
            dkim_records = await service.sync_dkim_records(tenant_id)
            results["dkim"] = len(dkim_records)

        if sync_type in ("reports", "all"):
            reports = await service.sync_dmarc_reports(tenant_id)
            results["reports"] = len(reports)

        # Invalidate cache after sync
        await service.invalidate_cache(tenant_id)

        return {
            "status": "success",
            "tenant_id": tenant_id,
            "sync_type": sync_type,
            "records_synced": results,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}") from e


# Helper functions


def _score_to_grade(score: float) -> str:
    """Convert numerical score to letter grade."""
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"


def _score_to_status(score: float) -> str:
    """Convert numerical score to status."""
    if score >= 80:
        return "compliant"
    elif score >= 60:
        return "at_risk"
    else:
        return "non_compliant"


def _get_score_recommendations(score: float) -> list[dict[str, str]]:
    """Get recommendations based on security score."""
    recommendations = []

    if score < 100:
        recommendations.append(
            {
                "priority": "high",
                "message": "Consider upgrading DMARC policy to 'reject' for maximum protection",
            }
        )

    if score < 80:
        recommendations.append(
            {
                "priority": "high",
                "message": "Enable DKIM signing for all domains",
            }
        )

    if score < 60:
        recommendations.append(
            {
                "priority": "critical",
                "message": "DMARC policy is set to 'none' - upgrade to at least 'quarantine'",
            }
        )

    return recommendations
