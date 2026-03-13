"""Riverside compliance data synchronization module.

This module provides scheduled sync functionality for Riverside compliance
tracking, running every 4 hours to keep data fresh for the July 8, 2026 deadline.
"""

import logging
from datetime import datetime

from app.api.services.monitoring_service import MonitoringService
from app.api.services.riverside_service import RiversideService
from app.core.circuit_breaker import RIVERSIDE_SYNC_BREAKER, circuit_breaker
from app.core.database import get_db_context
from app.core.retry import RIVERSIDE_SYNC_POLICY, retry_with_backoff

logger = logging.getLogger(__name__)


@circuit_breaker(RIVERSIDE_SYNC_BREAKER)
@retry_with_backoff(RIVERSIDE_SYNC_POLICY)
async def sync_riverside():
    """Sync Riverside compliance data from all tenants.

    This function orchestrates the sync of:
    - MFA enrollment status
    - Device compliance (MDM, EDR)
    - Requirement status from Graph API
    - Maturity score calculations

    Data is stored in:
    - RiversideCompliance: Overall maturity and deadline tracking
    - RiversideMFA: MFA enrollment metrics
    - RiversideDeviceCompliance: Device compliance metrics
    - RiversideRequirement: Individual requirement status
    """
    logger.info(f"Starting Riverside compliance sync at {datetime.utcnow()}")

    total_tenants = 0
    total_errors = 0
    results = {
        "mfa_synced": 0,
        "device_synced": 0,
        "requirements_synced": 0,
        "maturity_calculated": 0,
    }
    log_id = None

    try:
        with get_db_context() as db:
            # Start monitoring
            monitoring = MonitoringService(db)
            log_entry = monitoring.start_sync_job(job_type="riverside")
            log_id = log_entry.id

            # Initialize service
            service = RiversideService(db)

            try:
                # Sync MFA data
                logger.info("Syncing MFA data...")
                mfa_results = await service.sync_riverside_mfa()
                results["mfa_synced"] = sum(
                    1
                    for r in mfa_results.values()
                    if isinstance(r, dict) and r.get("status") == "success"
                )
                total_errors += sum(
                    1
                    for r in mfa_results.values()
                    if isinstance(r, dict) and r.get("status") == "error"
                )

                # Sync device compliance
                logger.info("Syncing device compliance data...")
                device_results = await service.sync_riverside_device_compliance()
                results["device_synced"] = sum(
                    1
                    for r in device_results.values()
                    if isinstance(r, dict) and r.get("status") == "success"
                )
                total_errors += sum(
                    1
                    for r in device_results.values()
                    if isinstance(r, dict) and r.get("status") == "error"
                )

                # Sync requirements
                logger.info("Syncing requirement status...")
                req_results = await service.sync_riverside_requirements()
                results["requirements_synced"] = req_results.get("requirements_synced", 0)

                # Calculate maturity scores
                logger.info("Calculating maturity scores...")
                maturity_results = await service.sync_riverside_maturity_scores()
                results["maturity_calculated"] = sum(
                    1
                    for r in maturity_results.values()
                    if isinstance(r, dict) and r.get("status") == "success"
                )

                total_tenants = len(mfa_results)

                logger.info(
                    f"Riverside sync completed: {results['mfa_synced']} MFA, "
                    f"{results['device_synced']} device, "
                    f"{results['requirements_synced']} requirements, "
                    f"{results['maturity_calculated']} maturity scores"
                )

                # Complete monitoring
                monitoring.complete_sync_job(
                    log_id=log_id,
                    status="success",
                    items_processed=sum(results.values()),
                    items_failed=total_errors,
                    message=f"Synced {total_tenants} tenants",
                )

            except Exception as e:
                logger.error(f"Riverside sync failed: {e}")
                monitoring.complete_sync_job(
                    log_id=log_id,
                    status="failed",
                    items_processed=0,
                    items_failed=total_tenants,
                    message=f"Error: {e!s}",
                )
                raise

    except Exception as e:
        logger.error(f"Riverside sync error: {e}")
        raise

    return results
