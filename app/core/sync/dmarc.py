"""DMARC/DKIM data synchronization module.

Runs daily to sync DMARC records, DKIM configuration, and aggregate
reports for all Riverside tenants with email security compliance.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.exc import DataError, IntegrityError, ProgrammingError

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
    logger.info(f"Starting DMARC/DKIM sync at {datetime.now(UTC)}")

    total_dmarc = 0
    total_dkim = 0
    total_reports = 0
    total_alerts_created = 0
    total_errors = 0
    log_id = None

    try:
        # Start monitoring and get tenant list with a short-lived session
        with get_db_context() as db:
            monitoring = MonitoringService(db)
            log_entry = monitoring.start_sync_job(job_type="dmarc")
            log_id = log_entry.id
            tenants = db.query(Tenant).filter(Tenant.is_active).all()
            # Extract data and apply priority sorting
            priority_data = []
            other_data = []
            for t in tenants:
                entry = (t.id, t.name, t.tenant_id)
                if t.id in RIVERSIDE_TENANTS:
                    priority_data.append(entry)
                else:
                    other_data.append(entry)
            tenant_data = priority_data + other_data

        logger.info(
            f"Found {len(priority_data)} Riverside tenants "
            f"and {len(other_data)} other tenants to sync"
        )

        for tenant_id, tenant_name, _azure_tenant_id in tenant_data:
            is_riverside = tenant_id in RIVERSIDE_TENANTS
            tenant_type = "Riverside" if is_riverside else "other"
            logger.info(f"Syncing DMARC/DKIM for {tenant_type} tenant: {tenant_name} ({tenant_id})")

            try:
                with get_db_context() as tenant_db:
                    service = DMARCService(tenant_db)

                    # Sync DMARC records
                    dmarc_records = await service.sync_dmarc_records(tenant_id)
                    total_dmarc += len(dmarc_records)

                    # Sync DKIM records
                    dkim_records = await service.sync_dkim_records(tenant_id)
                    total_dkim += len(dkim_records)

                    # Sync DMARC reports (if RUA endpoint configured)
                    reports = await service.sync_dmarc_reports(tenant_id)
                    total_reports += len(reports)

                    # Check for security issues and create alerts
                    alerts = await _check_security_issues(
                        service, tenant_id, dmarc_records, dkim_records
                    )
                    total_alerts_created += len(alerts)

                    # Check for stale DKIM keys
                    stale_alerts = await _check_stale_dkim_keys(service, tenant_id, dkim_records)
                    total_alerts_created += len(stale_alerts)

                    tenant_db.commit()

                    logger.info(
                        f"DMARC/DKIM sync completed for {tenant_name}: "
                        f"{len(dmarc_records)} DMARC, {len(dkim_records)} DKIM, "
                        f"{len(reports)} reports"
                    )

            except (IntegrityError, DataError, ProgrammingError) as e:
                total_errors += 1
                logger.error(f"Data error syncing DMARC/DKIM for tenant {tenant_name}: {e}")
                continue
            except Exception as e:
                total_errors += 1
                logger.error(
                    f"Error syncing DMARC/DKIM for tenant {tenant_name}: {e}",
                    exc_info=True,
                )
                continue

        # Invalidate cache after sync
        try:
            with get_db_context() as db:
                service = DMARCService(db)
                await service.invalidate_cache()
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {e}")

        # Update monitoring with final status
        if log_id:
            with get_db_context() as db:
                monitoring = MonitoringService(db)
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
                    error_message=str(e)[:5000],
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
    tenant_id: str,
    dmarc_records: list[DMARCRecord],
    dkim_records: list[DKIMRecord],
) -> list[DMARCAlert]:
    """Check for security issues and create alerts."""
    alerts = []

    # Check for weak DMARC policies
    for record in dmarc_records:
        if record.policy == "none":
            alert = await service.create_alert(
                tenant_id=tenant_id,
                alert_type="weak_dmarc_policy",
                severity="high",
                message=f"DMARC policy for {record.domain} is set to 'none' - emails can be spoofed",
                domain=record.domain,
                details={"current_policy": "none", "recommended_policy": "reject"},
            )
            alerts.append(alert)

        elif record.policy == "quarantine" and record.pct < 100:
            alert = await service.create_alert(
                tenant_id=tenant_id,
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
            tenant_id=tenant_id,
            alert_type="missing_dkim",
            severity="high",
            message=f"DKIM is not enabled for {domain} - DMARC may fail legitimate emails",
            domain=domain,
            details={"recommendation": "Enable DKIM signing for this domain"},
        )
        alerts.append(alert)

    return alerts


async def _check_stale_dkim_keys(
    service: DMARCService, tenant_id: str, dkim_records: list[DKIMRecord]
) -> list[DMARCAlert]:
    """Check for stale DKIM keys and create alerts."""
    alerts = []

    for record in dkim_records:
        if record.is_key_stale:
            days = record.days_since_rotation or "unknown"
            alert = await service.create_alert(
                tenant_id=tenant_id,
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
