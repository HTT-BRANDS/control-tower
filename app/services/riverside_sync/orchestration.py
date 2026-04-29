"""Riverside sync orchestration across tenants and tables."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.circuit_breaker import RIVERSIDE_SYNC_BREAKER, circuit_breaker
from app.core.database import get_db_context
from app.core.retry import RIVERSIDE_SYNC_POLICY, retry_with_backoff
from app.models.tenant import Tenant
from app.services.riverside_sync.common import ProgressTracker, _resolve_package_attr, logger


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
    logger.info(f"Starting batch sync for all tenants at {datetime.now(UTC)}")

    progress = ProgressTracker()
    results = {
        "mfa": {},
        "devices": {},
        "requirements": {},
        "maturity": {},
    }

    async def _do_sync(session: Session) -> dict:
        # Start monitoring
        monitoring = _resolve_package_attr("_get_monitoring_service")(session)
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
                            mfa_result = await _resolve_package_attr("sync_tenant_mfa")(
                                tenant.tenant_id,
                                session,
                            )
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
                            req_result = await _resolve_package_attr("sync_requirement_status")(
                                tenant.tenant_id,
                                session,
                            )
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
                            maturity_result = await _resolve_package_attr("sync_maturity_scores")(
                                tenant.tenant_id,
                                session,
                            )
                            tenant_results["maturity"] = maturity_result
                            results["maturity"][tenant.tenant_id] = maturity_result
                        except Exception as e:
                            logger.error(f"Maturity sync failed for {tenant.name}: {e}")
                            tenant_results["maturity"] = {"status": "error", "error": str(e)}
                            results["maturity"][tenant.tenant_id] = tenant_results["maturity"]
                            if not skip_failed:
                                raise

                    # Check if ALL enabled sync ops failed for this tenant
                    tenant_failed = True
                    if (
                        include_mfa
                        and tenant_results["mfa"]
                        and tenant_results["mfa"].get("status") != "error"
                    ):
                        tenant_failed = False
                    if (
                        include_requirements
                        and tenant_results["requirements"]
                        and tenant_results["requirements"].get("status") != "error"
                    ):
                        tenant_failed = False
                    if (
                        include_maturity
                        and tenant_results["maturity"]
                        and tenant_results["maturity"].get("status") != "error"
                    ):
                        tenant_failed = False

                    if tenant_failed:
                        progress.increment_failed(
                            f"All sync operations failed for {tenant.name}",
                            tenant.tenant_id,
                        )
                        logger.warning(f"All sync operations failed for tenant: {tenant.name}")
                    else:
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
                error_message="; ".join(e["error"][:100] for e in progress.errors)
                if progress.errors
                else None,
                final_records={
                    "records_processed": progress.completed + progress.failed,
                    "errors_count": progress.failed,
                    "error_details": progress.errors[:10],
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
        results["mfa"] = await _resolve_package_attr("sync_tenant_mfa")(tenant_id, db)
    except Exception as e:
        logger.error(f"MFA sync failed: {e}")
        results["mfa"] = {"status": "error", "error": str(e)}

    try:
        results["devices"] = await _resolve_package_attr("sync_tenant_devices")(tenant_id, db)
    except Exception as e:
        logger.error(f"Device sync failed: {e}")
        results["devices"] = {"status": "error", "error": str(e)}

    try:
        results["requirements"] = await _resolve_package_attr("sync_requirement_status")(
            tenant_id,
            db,
        )
    except Exception as e:
        logger.error(f"Requirement sync failed: {e}")
        results["requirements"] = {"status": "error", "error": str(e)}

    try:
        results["maturity"] = await _resolve_package_attr("sync_maturity_scores")(tenant_id, db)
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
