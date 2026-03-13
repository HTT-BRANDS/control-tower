"""Identity data synchronization module."""

import logging
from datetime import datetime, timedelta

from app.api.services.graph_client import GraphClient
from app.api.services.monitoring_service import MonitoringService
from app.core.circuit_breaker import IDENTITY_SYNC_BREAKER, circuit_breaker
from app.core.database import get_db_context
from app.core.retry import IDENTITY_SYNC_POLICY, retry_with_backoff
from app.models.identity import IdentitySnapshot, PrivilegedUser
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

# Common privileged role names for detection
PRIVILEGED_ROLE_NAMES = {
    "Global Administrator",
    "Global Reader",
    "Privileged Role Administrator",
    "User Administrator",
    "Groups Administrator",
    "Application Administrator",
    "Cloud Application Administrator",
    "Security Administrator",
    "Compliance Administrator",
    "Exchange Administrator",
    "SharePoint Administrator",
    "Teams Administrator",
    "Intune Administrator",
    "Billing Administrator",
    "Authentication Administrator",
    "Password Administrator",
}


def _is_privileged_role(role_name: str, role_description: str) -> bool:
    """Check if a role is considered privileged.

    Args:
        role_name: The display name of the role
        role_description: The description of the role

    Returns:
        True if the role is privileged
    """
    return (
        role_name in PRIVILEGED_ROLE_NAMES
        or "admin" in role_name.lower()
        or "administrator" in role_description.lower()
    )


def _parse_last_sign_in(sign_in_datetime: str | None) -> datetime | None:
    """Parse ISO format sign-in datetime string.

    Args:
        sign_in_datetime: ISO format datetime string from Graph API

    Returns:
        Parsed datetime or None if parsing fails
    """
    if not sign_in_datetime:
        return None
    try:
        return datetime.fromisoformat(sign_in_datetime.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


def _process_user_activity(
    user: dict,
    stale_30d_threshold: datetime,
    stale_90d_threshold: datetime,
) -> tuple[bool, bool, bool]:
    """Process user sign-in activity to determine active/stale status.

    Args:
        user: User dictionary from Graph API
        stale_30d_threshold: 30-day stale threshold
        stale_90d_threshold: 90-day stale threshold

    Returns:
        Tuple of (is_active, is_stale_30d, is_stale_90d)
    """
    sign_in_activity = user.get("signInActivity", {})
    last_sign_in = sign_in_activity.get("lastSignInDateTime")
    last_sign_in_dt = _parse_last_sign_in(last_sign_in)

    is_active = False
    is_stale_30d = False
    is_stale_90d = False

    if last_sign_in_dt:
        # Active: signed in within last 30 days
        is_active = last_sign_in_dt >= stale_30d_threshold
        # Stale thresholds
        if last_sign_in_dt < stale_90d_threshold:
            is_stale_90d = True
            is_stale_30d = True
        elif last_sign_in_dt < stale_30d_threshold:
            is_stale_30d = True
    else:
        # Never signed in - count as stale
        is_stale_30d = True
        is_stale_90d = True

    return is_active, is_stale_30d, is_stale_90d


@circuit_breaker(IDENTITY_SYNC_BREAKER)
@retry_with_backoff(IDENTITY_SYNC_POLICY)
async def sync_identity():
    """Sync identity data from all tenants.

    Fetches identity data from Microsoft Graph API for all active tenants,
    including users, guest users, directory roles, MFA registration status,
    and service principals. Stores aggregated results in IdentitySnapshot
    and detailed privileged user information in PrivilegedUser models.
    """
    logger.info(f"Starting identity sync at {datetime.utcnow()}")

    snapshot_date = datetime.utcnow().date()
    total_snapshots = 0
    total_privileged_users = 0
    total_errors = 0
    log_id = None

    try:
        with get_db_context() as db:
            # Start monitoring
            monitoring = MonitoringService(db)
            log_entry = monitoring.start_sync_job(job_type="identity")
            log_id = log_entry.id
            # Get all active tenants
            tenants = db.query(Tenant).filter(Tenant.is_active).all()
            logger.info(f"Found {len(tenants)} active tenants to sync for identity")

            for tenant in tenants:
                logger.info(f"Syncing identity for tenant: {tenant.name} ({tenant.tenant_id})")

                try:
                    # Initialize GraphClient for this tenant
                    graph_client = GraphClient(tenant.tenant_id)

                    # Fetch all required data from Graph API
                    users = await graph_client.get_users()
                    guest_users = await graph_client.get_guest_users()
                    directory_roles = await graph_client.get_directory_roles()
                    service_principals = await graph_client.get_service_principals()

                    # Fetch MFA status (may fail if permissions are missing)
                    mfa_data = {}
                    try:
                        mfa_response = await graph_client.get_mfa_status()
                        mfa_users = mfa_response.get("value", [])
                        mfa_data = {user.get("userPrincipalName", ""): user for user in mfa_users}
                    except Exception as e:
                        logger.warning(f"Could not fetch MFA status for tenant {tenant.name}: {e}")

                    # Calculate date thresholds for stale account detection
                    now = datetime.utcnow()
                    stale_30d_threshold = now - timedelta(days=30)
                    stale_90d_threshold = now - timedelta(days=90)

                    # Process users and calculate metrics
                    total_user_count = len(users)
                    active_user_count = 0
                    stale_30d_count = 0
                    stale_90d_count = 0

                    # Track user details for privileged user processing
                    user_lookup = {}

                    for user in users:
                        user_principal_name = user.get("userPrincipalName", "")
                        user_id = user.get("id", "")

                        # Process activity
                        is_active, is_stale_30d, is_stale_90d = _process_user_activity(
                            user,
                            stale_30d_threshold,
                            stale_90d_threshold,
                        )

                        if is_active:
                            active_user_count += 1
                        if is_stale_30d:
                            stale_30d_count += 1
                        if is_stale_90d:
                            stale_90d_count += 1

                        # Store user details for privileged user processing
                        sign_in_activity = user.get("signInActivity", {})
                        last_sign_in = sign_in_activity.get("lastSignInDateTime")
                        user_lookup[user_id] = {
                            "userPrincipalName": user_principal_name,
                            "displayName": user.get("displayName", ""),
                            "userType": user.get("userType", "Member"),
                            "lastSignIn": _parse_last_sign_in(last_sign_in),
                        }

                    # Calculate MFA statistics
                    mfa_enabled_count = sum(
                        1 for info in mfa_data.values() if info.get("isMfaRegistered", False)
                    )
                    mfa_disabled_count = len(mfa_data) - mfa_enabled_count

                    # If we couldn't fetch MFA data, estimate from total users
                    if not mfa_data:
                        mfa_enabled_count = 0
                        mfa_disabled_count = total_user_count

                    # Process directory roles to identify privileged users
                    privileged_user_count = 0
                    privileged_users_data = []

                    for role in directory_roles:
                        role_name = role.get("displayName", "")
                        role_description = role.get("description", "")

                        if not _is_privileged_role(role_name, role_description):
                            continue

                        members = role.get("members", [])
                        for member in members:
                            member_type = member.get("@odata.type", "")
                            member_id = member.get("id", "")

                            # Only process user members (not service principals)
                            if "#microsoft.graph.user" not in member_type:
                                continue

                            user_info = user_lookup.get(
                                member_id,
                                {
                                    "userPrincipalName": member.get("userPrincipalName", ""),
                                    "displayName": member.get("displayName", ""),
                                    "userType": "Member",
                                    "lastSignIn": None,
                                },
                            )

                            upn = user_info.get("userPrincipalName", "")
                            display_name = user_info.get("displayName", "")
                            user_type = user_info.get("userType", "Member")
                            last_sign_in = user_info.get("lastSignIn")

                            # Check MFA status for this user
                            mfa_info = mfa_data.get(upn, {})
                            mfa_enabled = 1 if mfa_info.get("isMfaRegistered", False) else 0

                            # Default to permanent assignment
                            is_permanent = 1

                            privileged_users_data.append(
                                {
                                    "tenant_id": tenant.id,
                                    "user_principal_name": upn,
                                    "display_name": display_name,
                                    "user_type": user_type,
                                    "role_name": role_name,
                                    "role_scope": "Directory",
                                    "is_permanent": is_permanent,
                                    "mfa_enabled": mfa_enabled,
                                    "last_sign_in": last_sign_in,
                                }
                            )
                            privileged_user_count += 1

                    # Delete existing privileged user records for this tenant
                    db.query(PrivilegedUser).filter(PrivilegedUser.tenant_id == tenant.id).delete()

                    # Create new privileged user records
                    for priv_user_data in privileged_users_data:
                        privileged_user = PrivilegedUser(
                            tenant_id=priv_user_data["tenant_id"],
                            user_principal_name=priv_user_data["user_principal_name"],
                            display_name=priv_user_data["display_name"],
                            user_type=priv_user_data["user_type"],
                            role_name=priv_user_data["role_name"],
                            role_scope=priv_user_data["role_scope"],
                            is_permanent=priv_user_data["is_permanent"],
                            mfa_enabled=priv_user_data["mfa_enabled"],
                            last_sign_in=priv_user_data["last_sign_in"],
                            synced_at=datetime.utcnow(),
                        )
                        db.add(privileged_user)
                        total_privileged_users += 1

                    # Create IdentitySnapshot
                    snapshot = IdentitySnapshot(
                        tenant_id=tenant.id,
                        snapshot_date=snapshot_date,
                        total_users=total_user_count,
                        active_users=active_user_count,
                        guest_users=len(guest_users),
                        mfa_enabled_users=mfa_enabled_count,
                        mfa_disabled_users=mfa_disabled_count,
                        privileged_users=privileged_user_count,
                        stale_accounts_30d=stale_30d_count,
                        stale_accounts_90d=stale_90d_count,
                        service_principals=len(service_principals),
                        synced_at=datetime.utcnow(),
                    )
                    db.add(snapshot)
                    total_snapshots += 1

                    # Commit changes for this tenant
                    db.commit()

                    logger.info(
                        f"Identity sync completed for tenant {tenant.name}: "
                        f"{total_user_count} users, {len(guest_users)} guests, "
                        f"{privileged_user_count} privileged users, "
                        f"{len(service_principals)} service principals"
                    )

                except Exception as e:
                    total_errors += 1
                    logger.error(
                        f"Error syncing identity for tenant {tenant.name}: {e}",
                        exc_info=True,
                    )
                    continue

        # Update monitoring with final status
        if log_id:
            monitoring.complete_sync_job(
                log_id=log_id,
                status="completed" if total_errors == 0 else "failed",
                final_records={
                    "records_processed": total_snapshots + total_privileged_users,
                    "records_created": total_snapshots + total_privileged_users,
                    "records_updated": 0,
                    "errors_count": total_errors,
                },
            )

        logger.info(
            f"Identity sync completed: {total_snapshots} snapshots, "
            f"{total_privileged_users} privileged user records synced, "
            f"{total_errors} errors encountered"
        )

    except Exception as e:
        logger.error(f"Fatal error during identity sync: {e}", exc_info=True)
        # Update monitoring with failure status
        if log_id:
            with get_db_context() as db:
                monitoring = MonitoringService(db)
                monitoring.complete_sync_job(
                    log_id=log_id,
                    status="failed",
                    error_message=str(e)[:1000],
                    final_records={
                        "records_processed": total_snapshots + total_privileged_users,
                        "records_created": total_snapshots + total_privileged_users,
                        "records_updated": 0,
                        "errors_count": total_errors + 1,
                    },
                )
        raise
