"""Riverside MFA table synchronization."""

from datetime import UTC, datetime

from azure.core.exceptions import HttpResponseError
from sqlalchemy import Date, cast
from sqlalchemy.orm import Session

from app.api.services.graph_client import ADMIN_ROLE_TEMPLATE_IDS
from app.core.circuit_breaker import RIVERSIDE_SYNC_BREAKER, CircuitBreakerError, circuit_breaker
from app.core.database import get_db_context
from app.core.retry import RIVERSIDE_SYNC_POLICY, retry_with_backoff
from app.models.riverside import RiversideMFA
from app.models.tenant import Tenant
from app.services.riverside_sync.common import SyncError, _resolve_package_attr, logger


@circuit_breaker(RIVERSIDE_SYNC_BREAKER)
@retry_with_backoff(RIVERSIDE_SYNC_POLICY)
async def sync_tenant_mfa(
    tenant_id: str,
    db: Session | None = None,
    snapshot_date: datetime | None = None,
    include_method_details: bool = False,
    batch_size: int = 100,
) -> dict:
    """Sync MFA enrollment data for a specific tenant from Microsoft Graph API.

    Fetches MFA registration status using the new Graph API integration,
    calculates coverage percentages, and tracks admin account MFA protection status.

    This enhanced version uses the new MFA data collection methods from GraphClient
    including paginated queries and detailed authentication method information.

    Args:
        tenant_id: Azure tenant ID to sync
        db: Database session (creates context if None)
        snapshot_date: Optional snapshot date (defaults to now)
        include_method_details: If True, include detailed method breakdown
        batch_size: Number of users per batch for pagination (default 100)

    Returns:
        Dict with MFA sync results:
        - status: "success" or "error"
        - total_users: total user count
        - mfa_enrolled: number of MFA-enrolled users
        - mfa_coverage_pct: MFA coverage percentage
        - admin_accounts: total admin accounts
        - admin_mfa_pct: admin MFA coverage percentage
        - unprotected_users: users without MFA
        - method_breakdown: dict of method types and counts (if include_method_details)
        - users_without_mfa: list of users without MFA (if include_method_details)

    Raises:
        SyncError: If sync fails and circuit breaker/retry exhausted
    """
    snapshot_date = snapshot_date or datetime.now(UTC)

    logger.info(
        f"Syncing MFA data for tenant: {tenant_id} (include_details={include_method_details})"
    )

    async def _do_sync(session: Session) -> dict:
        # Get tenant
        tenant = session.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
        if not tenant:
            raise SyncError(f"Tenant {tenant_id} not found", tenant_id)

        try:
            graph_client = _resolve_package_attr("_get_graph_client")(tenant_id)

            # Get all users with pagination for large tenants
            users = await graph_client.get_users_paginated(batch_size=batch_size)
            total_users = len(users)

            # Get MFA registration details with pagination
            registrations = await graph_client.get_mfa_registration_details_paginated(
                batch_size=batch_size
            )

            # Get directory roles for admin MFA tracking
            directory_roles = await graph_client.get_directory_roles()

            # Build set of admin user IDs
            admin_user_ids: set[str] = set()
            for role in directory_roles:
                role_template_id = role.get("roleTemplateId", "")
                if role_template_id in ADMIN_ROLE_TEMPLATE_IDS:
                    for member in role.get("members", []):
                        user_id = member.get("id")
                        if user_id:
                            admin_user_ids.add(user_id)

            # Build user lookup by UPN
            {u.get("userPrincipalName", "").lower(): u for u in users}

            # Build registration lookup by UPN
            registration_lookup: dict[str, dict] = {
                reg.get("userPrincipalName", "").lower(): reg for reg in registrations
            }

            # Calculate MFA metrics
            mfa_enrolled = 0
            admin_accounts_total = len(admin_user_ids)
            admin_accounts_mfa = 0
            method_breakdown: dict[str, int] = {}
            users_without_mfa: list[dict] = []

            for user in users:
                upn = user.get("userPrincipalName", "").lower()
                user_id = user.get("id", "")
                is_admin = user_id in admin_user_ids

                reg = registration_lookup.get(upn, {})
                is_mfa_registered = reg.get("isMfaRegistered", False)
                methods = reg.get("methodsRegistered", []) if reg else []

                if is_mfa_registered:
                    mfa_enrolled += 1
                    if is_admin:
                        admin_accounts_mfa += 1

                    # Count methods
                    for method in methods:
                        method_type = method.lower() if isinstance(method, str) else str(method)
                        method_breakdown[method_type] = method_breakdown.get(method_type, 0) + 1
                else:
                    if include_method_details or is_admin:
                        users_without_mfa.append(
                            {
                                "user_id": user_id,
                                "user_principal_name": upn,
                                "display_name": user.get("displayName", ""),
                                "is_admin": is_admin,
                            }
                        )

            # Calculate percentages
            mfa_coverage_pct = (mfa_enrolled / total_users * 100) if total_users > 0 else 0.0
            admin_mfa_pct = (
                (admin_accounts_mfa / admin_accounts_total * 100)
                if admin_accounts_total > 0
                else 0.0
            )
            unprotected_users = total_users - mfa_enrolled

            # Check for existing record for today
            existing = (
                session.query(RiversideMFA)
                .filter(
                    RiversideMFA.tenant_id == tenant.id,
                    cast(RiversideMFA.snapshot_date, Date) == snapshot_date.date(),
                )
                .first()
            )

            if existing:
                # Update existing record
                existing.total_users = total_users
                existing.mfa_enrolled_users = mfa_enrolled
                existing.mfa_coverage_percentage = round(mfa_coverage_pct, 2)
                existing.admin_accounts_total = admin_accounts_total
                existing.admin_accounts_mfa = admin_accounts_mfa
                existing.admin_mfa_percentage = round(admin_mfa_pct, 2)
                existing.unprotected_users = unprotected_users
                existing.snapshot_date = snapshot_date
            else:
                # Create new record
                mfa_record = RiversideMFA(
                    tenant_id=tenant.id,
                    total_users=total_users,
                    mfa_enrolled_users=mfa_enrolled,
                    mfa_coverage_percentage=round(mfa_coverage_pct, 2),
                    admin_accounts_total=admin_accounts_total,
                    admin_accounts_mfa=admin_accounts_mfa,
                    admin_mfa_percentage=round(admin_mfa_pct, 2),
                    unprotected_users=unprotected_users,
                    snapshot_date=snapshot_date,
                )
                session.add(mfa_record)

            session.commit()

            logger.info(
                f"MFA sync completed for {tenant.name}: "
                f"{mfa_coverage_pct:.1f}% coverage, {admin_mfa_pct:.1f}% admin MFA, "
                f"{len(method_breakdown)} method types registered"
            )

            result = {
                "status": "success",
                "total_users": total_users,
                "mfa_enrolled": mfa_enrolled,
                "mfa_coverage_pct": round(mfa_coverage_pct, 2),
                "admin_accounts": admin_accounts_total,
                "admin_mfa_pct": round(admin_mfa_pct, 2),
                "unprotected_users": unprotected_users,
            }

            if include_method_details:
                result["method_breakdown"] = method_breakdown
                result["users_without_mfa"] = users_without_mfa[:100]  # Limit to first 100

            return result

        except HttpResponseError as e:
            session.rollback()
            error_msg = f"Azure API error syncing MFA: {e.status_code} - {e.message}"
            logger.error(error_msg)
            raise SyncError(error_msg, tenant_id, status_code=e.status_code) from e
        except CircuitBreakerError as e:
            session.rollback()
            error_msg = f"Circuit breaker open for MFA sync: {e}"
            logger.error(error_msg)
            raise SyncError(error_msg, tenant_id) from e
        except Exception as e:
            session.rollback()
            error_msg = f"Unexpected error syncing MFA: {e}"
            logger.error(error_msg)
            raise SyncError(error_msg, tenant_id) from e

    if db:
        return await _do_sync(db)
    else:
        with get_db_context() as session:
            return await _do_sync(session)
