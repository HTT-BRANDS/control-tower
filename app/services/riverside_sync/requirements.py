"""Riverside requirement status synchronization."""

from datetime import UTC, datetime

from azure.core.exceptions import HttpResponseError
from sqlalchemy.orm import Session

from app.core.circuit_breaker import RIVERSIDE_SYNC_BREAKER, CircuitBreakerError, circuit_breaker
from app.core.database import get_db_context
from app.core.retry import RIVERSIDE_SYNC_POLICY, retry_with_backoff
from app.models.riverside import RequirementStatus, RiversideRequirement
from app.models.tenant import Tenant
from app.services.riverside_sync.common import SyncError, _resolve_package_attr, logger


@circuit_breaker(RIVERSIDE_SYNC_BREAKER)
@retry_with_backoff(RIVERSIDE_SYNC_POLICY)
async def sync_requirement_status(
    tenant_id: str,
    db: Session | None = None,
) -> dict:
    """Sync requirement status progress for a specific tenant.

    Checks Azure resources and configuration against requirement criteria,
    updating requirement status based on actual tenant compliance state.

    Args:
        tenant_id: Azure tenant ID to sync
        db: Database session (creates context if None)

    Returns:
        Dict with requirement sync results:
        - status: "success" or "error"
        - requirements_checked: number of requirements checked
        - requirements_updated: number of requirements updated
        - updates: list of requirement status changes

    Raises:
        SyncError: If sync fails and circuit breaker/retry exhausted
    """
    logger.info(f"Syncing requirement status for tenant: {tenant_id}")

    async def _do_sync(session: Session) -> dict:
        # Get tenant
        tenant = session.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
        if not tenant:
            raise SyncError(f"Tenant {tenant_id} not found", tenant_id)

        try:
            graph_client = _resolve_package_attr("_get_graph_client")(tenant_id)

            # Get requirements for this tenant
            requirements = (
                session.query(RiversideRequirement)
                .filter(RiversideRequirement.tenant_id == tenant.id)
                .all()
            )

            requirements_checked = 0
            requirements_updated = 0
            updates: list[dict] = []

            # Check Conditional Access policies for MFA enforcement
            ca_policies = await graph_client.get_conditional_access_policies()

            # Analyze policies for MFA enforcement
            has_mfa_policy = False
            for policy in ca_policies:
                policy_name = policy.get("displayName", "").lower()
                grant_controls = policy.get("grantControls", {})
                built_in_controls = grant_controls.get("builtInControls", [])

                # Check for MFA enforcement
                if "mfa" in policy_name or "mfa" in str(built_in_controls).lower():
                    has_mfa_policy = True
                    break

            # Check each requirement and update status based on Azure state
            for req in requirements:
                requirements_checked += 1
                old_status = req.status
                new_status = old_status

                # MFA-related requirements
                if "MFA" in req.requirement_id.upper() or "mfa" in req.title.lower():
                    if has_mfa_policy and old_status == RequirementStatus.NOT_STARTED:
                        new_status = RequirementStatus.IN_PROGRESS

                # Update if status changed
                if new_status != old_status:
                    req.status = new_status
                    req.updated_at = datetime.now(UTC)
                    requirements_updated += 1
                    updates.append(
                        {
                            "requirement_id": req.requirement_id,
                            "title": req.title,
                            "old_status": old_status.value,
                            "new_status": new_status.value,
                        }
                    )

            session.commit()

            logger.info(
                f"Requirement sync completed for {tenant.name}: "
                f"{requirements_checked} checked, {requirements_updated} updated"
            )

            return {
                "status": "success",
                "requirements_checked": requirements_checked,
                "requirements_updated": requirements_updated,
                "updates": updates,
            }

        except HttpResponseError as e:
            session.rollback()
            error_msg = f"Azure API error syncing requirements: {e.status_code} - {e.message}"
            logger.error(error_msg)
            raise SyncError(error_msg, tenant_id, status_code=e.status_code) from e
        except CircuitBreakerError as e:
            error_msg = f"Circuit breaker open for requirement sync: {e}"
            logger.error(error_msg)
            raise SyncError(error_msg, tenant_id) from e
        except Exception as e:
            session.rollback()
            error_msg = f"Unexpected error syncing requirements: {e}"
            logger.error(error_msg)
            raise SyncError(error_msg, tenant_id) from e

    if db:
        return await _do_sync(db)
    else:
        with get_db_context() as session:
            return await _do_sync(session)
