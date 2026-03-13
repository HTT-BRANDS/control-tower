"""DMARC/DKIM data synchronization module.

Runs daily to sync DMARC records, DKIM configuration, and aggregate
reports for all Riverside tenants with email security compliance.
"""

import logging
from datetime import datetime

from app.api.services.dmarc_service import DMARCService
from app.api.services.monitoring_service import MonitoringService
from app.core.circuit_breaker import DMARC_SYNC_BREAKER, circuit_breaker
from app.core.database import get_db_context
from app.core.retry import DMARC_SYNC_POLICY, retry_with_backoff
from app.models.dmarc import DKIMRecord, DMARCAlert, DMARCRecord
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

# Riverside tenant IDs for prioritization
RIVERSIDE_TENANTS = ["riverside-htt", "riverside-bcc", "riverside-fn", "riverside-tll"]


@circuit_breaker(DMARC_SYNC_BREAKER)
@retry_with_backoff(DMARC_SYNC_POLICY)
async def sync_dmarc_dkim():
    """Sync DMARC/DKIM data for all tenants.

    Fetches DMARC DNS records, DKIM signing configuration, and aggregate
    reports for all active tenants. Prioritizes Riverside tenants for
    the July 2026 compliance deadline.
    """
    logger.info(f"Starting DMARC/DKIM sync at {datetime.utcnow()}")

    total_dmarc = 0
    total_dkim = 0
    total_reports = 0
    total_alerts_created = 0
    total_errors = 0
    log_id = None

    try:
        with get_db_context() as db:
            # Start monitoring
            monitoring = MonitoringService(db)
            log_entry = monitoring.start_sync_job(job_type="dmarc")
            log_id = log_entry.id

            # Get all active tenants
            tenants = db.query(Tenant).filter(Tenant.is_active).all()

            # Prioritize Riverside tenants
            priority_tenants = []
            other_tenants = []

            for tenant in tenants:
                if tenant.id in RIVERSIDE_TENANTS:
                    priority_tenants.append(tenant)
                else:
                    other_tenants.append(tenant)

            # Process Riverside tenants first
            all_tenants = priority_tenants + other_tenants

            logger.info(
                f"Found {len(priority_tenants)} Riverside tenants "
                f"and {len(other_tenants)} other tenants to sync"
            )

            service = DMARCService(db)

            for tenant in all_tenants:
                is_riverside = tenant.id in RIVERSIDE_TENANTS
                tenant_type = "Riverside" if is_riverside else "other"

                logger.info(
                    f"Syncing DMARC/DKIM for {tenant_type} tenant: {tenant.name} ({tenant.id})"
                )

                try:
                    # Sync DMARC records
                    dmarc_records = await service.sync_dmarc_records(tenant.id)
                    total_dmarc += len(dmarc_records)

                    # Sync DKIM records
                    dkim_records = await service.sync_dkim_records(tenant.id)
                    total_dkim += len(dkim_records)

                    # Sync DMARC reports (if RUA endpoint configured)
                    reports = await service.sync_dmarc_reports(tenant.id)
                    total_reports += len(reports)

                    # Check for security issues and create alerts
                    alerts = await _check_security_issues(
                        service, tenant, dmarc_records, dkim_records
                    )
                    total_alerts_created += len(alerts)

                    # Check for stale DKIM keys
                    stale_alerts = await _check_stale_dkim_keys(service, tenant, dkim_records)
                    total_alerts_created += len(stale_alerts)

                    db.commit()

                    logger.info(
                        f"DMARC/DKIM sync completed for {tenant.name}: "
                        f"{len(dmarc_records)} DMARC, {len(dkim_records)} DKIM, "
                        f"{len(reports)} reports"
                    )

                except Exception as e:
                    total_errors += 1
                    logger.error(
                        f"Error syncing DMARC/DKIM for tenant {tenant.name}: {e}",
                        exc_info=True,
                    )
                    db.rollback()
                    continue

            # Invalidate cache after sync
            await service.invalidate_cache()

        # Update monitoring with final status
        if log_id:
            monitoring.complete_sync_job(
                log_id=log_id,
                status="completed" if total_errors == 0 else "completed_with_errors",
                final_records={
                    "records_processed": total_dmarc + total_dkim + total_reports,
                    "records_created": total_dmarc + total_dkim + total_reports,
                    "records_updated": 0,
                    "alerts_created": total_alerts_created,
                    "errors_count": total_errors,
                },
            )

        logger.info(
            f"DMARC/DKIM sync completed: {total_dmarc} DMARC records, "
            f"{total_dkim} DKIM records, {total_reports} reports, "
            f"{total_alerts_created} alerts, {total_errors} errors"
        )

    except Exception as e:
        logger.error(f"Fatal error during DMARC/DKIM sync: {e}", exc_info=True)
        if log_id:
            with get_db_context() as db:
                monitoring = MonitoringService(db)
                monitoring.complete_sync_job(
                    log_id=log_id,
                    status="failed",
                    error_message=str(e)[:1000],
                    final_records={
                        "records_processed": total_dmarc + total_dkim + total_reports,
                        "records_created": total_dmarc + total_dkim + total_reports,
                        "records_updated": 0,
                        "alerts_created": total_alerts_created,
                        "errors_count": total_errors + 1,
                    },
                )
        raise


async def _check_security_issues(
    service: DMARCService,
    tenant: Tenant,
    dmarc_records: list[DMARCRecord],
    dkim_records: list[DKIMRecord],
) -> list[DMARCAlert]:
    """Check for security issues and create alerts."""
    alerts = []

    # Check for weak DMARC policies
    for record in dmarc_records:
        if record.policy == "none":
            alert = await service.create_alert(
                tenant_id=tenant.id,
                alert_type="weak_dmarc_policy",
                severity="high",
                message=f"DMARC policy for {record.domain} is set to 'none' - emails can be spoofed",
                domain=record.domain,
                details={"current_policy": "none", "recommended_policy": "reject"},
            )
            alerts.append(alert)

        elif record.policy == "quarantine" and record.pct < 100:
            alert = await service.create_alert(
                tenant_id=tenant.id,
                alert_type="dmarc_partial_enforcement",
                severity="medium",
                message=f"DMARC policy for {record.domain} is only enforcing {record.pct}%",
                domain=record.domain,
                details={"current_pct": record.pct, "recommended_pct": 100},
            )
            alerts.append(alert)

    # Check for missing DKIM on domains with DMARC
    dmarc_domains = {r.domain for r in dmarc_records}
    dkim_domains = {r.domain for r in dkim_records if r.is_enabled}
    missing_dkim = dmarc_domains - dkim_domains

    for domain in missing_dkim:
        alert = await service.create_alert(
            tenant_id=tenant.id,
            alert_type="missing_dkim",
            severity="high",
            message=f"DKIM is not enabled for {domain} - DMARC may fail legitimate emails",
            domain=domain,
            details={"recommendation": "Enable DKIM signing for this domain"},
        )
        alerts.append(alert)

    return alerts


async def _check_stale_dkim_keys(
    service: DMARCService, tenant: Tenant, dkim_records: list[DKIMRecord]
) -> list[DMARCAlert]:
    """Check for stale DKIM keys and create alerts."""
    alerts = []

    for record in dkim_records:
        if record.is_key_stale:
            days = record.days_since_rotation or "unknown"
            alert = await service.create_alert(
                tenant_id=tenant.id,
                alert_type="stale_dkim_key",
                severity="medium",
                message=f"DKIM key for {record.domain} has not been rotated in {days} days",
                domain=record.domain,
                details={
                    "days_since_rotation": days,
                    "recommended_rotation_days": 180,
                },
            )
            alerts.append(alert)

    return alerts
