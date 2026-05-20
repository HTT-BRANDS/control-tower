"""Sync utility functions for data safety and audit trail.

Provides helpers to prevent column overflow errors that can poison
SQLAlchemy sessions and cascade to kill ALL sync jobs (ADR-0010).
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.core.tenants_config import get_app_id_for_tenant
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass(frozen=True)
class SyncEligibilityDecision:
    """Structured answer for whether a tenant should be scheduled to sync."""

    eligible: bool
    auth_mode: str
    reason: str
    resolved_app_id: str | None = None


def safe_truncate(
    value: str | None,
    max_len: int,
    field_name: str,
    context: dict | None = None,
) -> str | None:
    """Safely truncate a string value to fit a database column.

    Returns the value unchanged if it fits, or truncates with a structured
    warning log for audit trail (STRIDE T-1, R-1).

    Args:
        value: The string value to check/truncate.
        max_len: Maximum allowed length.
        field_name: Name of the field (for logging).
        context: Optional context dict (e.g. tenant, subscription).

    Returns:
        The original value, truncated value, or None.
    """
    if value is None:
        return None
    if len(value) <= max_len:
        return value

    logger.warning(
        "Truncating oversized field",
        extra={
            "field_name": field_name,
            "original_length": len(value),
            "max_length": max_len,
            "context": context or {},
        },
    )
    return value[:max_len]


def build_sync_eligibility_decision(
    *,
    tenant_is_active: bool,
    tenant_id: str,
    tenant_client_id: str | None,
    tenant_client_secret_ref: str | None,
    use_uami_auth: bool,
    use_oidc_federation: bool,
    key_vault_url: str | None,
    azure_client_id: str | None,
    azure_client_secret: str | None,
    resolved_app_id: str | None,
) -> SyncEligibilityDecision:
    """Return a pure, reusable sync eligibility decision.

    This keeps scheduler logic, tests, and read-only production investigation
    tooling aligned around the same rules instead of letting each invent its
    own little religion.
    """
    if not tenant_is_active:
        return SyncEligibilityDecision(False, "inactive", "tenant_inactive")

    if use_uami_auth:
        app_id = resolved_app_id or tenant_client_id
        return SyncEligibilityDecision(
            eligible=bool(app_id),
            auth_mode="uami",
            reason="uami_app_id_resolved" if app_id else "missing_app_id_for_uami",
            resolved_app_id=app_id,
        )

    if use_oidc_federation:
        app_id = resolved_app_id or tenant_client_id
        return SyncEligibilityDecision(
            eligible=bool(app_id),
            auth_mode="oidc",
            reason="oidc_app_id_resolved" if app_id else "missing_app_id_for_oidc",
            resolved_app_id=app_id,
        )

    has_shared_credentials = bool(azure_client_id and azure_client_secret)
    if not key_vault_url:
        return SyncEligibilityDecision(
            eligible=has_shared_credentials,
            auth_mode="shared_secret",
            reason=(
                "shared_settings_credentials_available"
                if has_shared_credentials
                else "missing_shared_settings_credentials"
            ),
        )

    if tenant_client_id and tenant_client_secret_ref:
        return SyncEligibilityDecision(
            True,
            "key_vault_secret",
            "explicit_per_tenant_secret_ref",
            resolved_app_id=tenant_client_id,
        )

    standard_app_id = resolved_app_id or tenant_client_id
    if standard_app_id:
        return SyncEligibilityDecision(
            True,
            "key_vault_secret",
            "standard_per_tenant_secret_names",
            resolved_app_id=standard_app_id,
        )

    return SyncEligibilityDecision(
        False,
        "key_vault_secret",
        "missing_key_vault_app_id",
    )


def explain_tenant_sync_eligibility(tenant: Tenant) -> SyncEligibilityDecision:
    """Return structured sync eligibility details for a tenant."""
    return build_sync_eligibility_decision(
        tenant_is_active=bool(tenant.is_active),
        tenant_id=tenant.tenant_id,
        tenant_client_id=tenant.client_id,
        tenant_client_secret_ref=tenant.client_secret_ref,
        use_uami_auth=bool(settings.use_uami_auth),
        use_oidc_federation=bool(settings.use_oidc_federation),
        key_vault_url=str(settings.key_vault_url) if settings.key_vault_url else None,
        azure_client_id=str(settings.azure_client_id) if settings.azure_client_id else None,
        azure_client_secret=(
            str(settings.azure_client_secret) if settings.azure_client_secret else None
        ),
        resolved_app_id=get_app_id_for_tenant(tenant.tenant_id),
    )


def tenant_is_sync_eligible(tenant: Tenant) -> bool:
    """Return whether a tenant is configured for scheduled Azure sync.

    Eligibility is intentionally stricter than ``tenant.is_active`` so
    background jobs do not hammer Azure with obviously incomplete or fake
    tenant records.

    A tenant merely existing in ``tenants_config`` is NOT sufficient in
    secret mode. Scheduled jobs must only run when the tenant has an actual
    credential path available; otherwise the scheduler will repeatedly invoke
    syncs that can never authenticate and will spam alerts/logs.
    """
    return explain_tenant_sync_eligibility(tenant).eligible


def get_sync_eligible_tenants(tenants: Iterable[Tenant]) -> list[Tenant]:
    """Filter a tenant iterable down to scheduled-sync eligible tenants."""
    return [tenant for tenant in tenants if tenant_is_sync_eligible(tenant)]


def determine_sync_outcome(
    *,
    job_type: str,
    records_processed: int,
    errors_count: int,
    eligible_tenants: int,
    subscriptions_seen: int | None = None,
) -> tuple[str, str | None, dict[str, Any]]:
    """Return final monitoring status and actionable error text for a sync job.

    A scheduler run that processes zero records is not a healthy sync in
    production data domains. It usually means credential resolution, tenant
    consent, RBAC, or subscription enumeration broke upstream. Treating that
    as ``completed`` makes health checks green while dashboards stay blank.
    That is not observability; that is a tiny clown car.
    """
    details: dict[str, Any] = {
        "records_processed": records_processed,
        "errors_count": errors_count,
        "eligible_tenants": eligible_tenants,
    }
    if subscriptions_seen is not None:
        details["subscriptions_seen"] = subscriptions_seen

    if errors_count > 0:
        return (
            "failed",
            f"{job_type} sync completed with {errors_count} error(s); "
            f"{records_processed} record(s) processed.",
            details,
        )

    if eligible_tenants == 0:
        return (
            "failed",
            f"{job_type} sync found zero sync-eligible tenants. Check tenant credential "
            "configuration, KEY_VAULT_URL, OIDC/UAMI mode, and tenant secret refs.",
            details,
        )

    if records_processed == 0:
        subscription_hint = (
            f" subscriptions_seen={subscriptions_seen}." if subscriptions_seen is not None else ""
        )
        return (
            "failed",
            f"{job_type} sync processed zero records across {eligible_tenants} eligible "
            f"tenant(s).{subscription_hint} Check Azure credentials, tenant consent, "
            "RBAC roles, and subscription enumeration.",
            details,
        )

    return "completed", None, details
