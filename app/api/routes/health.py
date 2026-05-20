"""Health check API routes.

Provides API-specific health status endpoints for monitoring and load balancers.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.cache import cache_manager
from app.core.config import get_settings
from app.core.database import _IS_SQLITE, _get_engine, get_db
from app.core.scheduler import get_scheduler

router = APIRouter(
    prefix="/api/v1/health",
    tags=["System"],
)


def _get_data_freshness_threshold() -> timedelta:
    """Return the data freshness threshold from settings (configurable via env)."""
    settings = get_settings()
    return timedelta(hours=settings.sync_stale_threshold_hours)


def _latest_timestamp(*values: datetime | None) -> datetime | None:
    """Return the newest non-null timestamp."""
    present = [value for value in values if value is not None]
    return max(present) if present else None


def _latest_cost_freshness(db: Session, tenant_id: str, snapshot_ts: datetime | None):
    """Return cost freshness from snapshots or zero-cost tenant sync markers.

    Cost snapshots skip zero-cost rows by design. A tenant can therefore have a
    successful Cost Management API sync and still have no CostSnapshot rows.
    The per-tenant marker lets /healthz/data report "freshly checked, $0" as
    fresh instead of stale/missing. Tiny distinction, enormous dashboard drama.
    """
    from app.core.sync.costs import COST_TENANT_FRESHNESS_JOB_TYPE
    from app.models.monitoring import SyncJobLog

    marker_ts = (
        db.query(func.max(SyncJobLog.ended_at))
        .filter(
            SyncJobLog.job_type == COST_TENANT_FRESHNESS_JOB_TYPE,
            SyncJobLog.tenant_id == tenant_id,
            SyncJobLog.status == "completed",
        )
        .scalar()
    )
    return _latest_timestamp(snapshot_ts, marker_ts)


def _build_scheduler_check(
    request: Request, include_jobs: bool, has_auth: bool
) -> tuple[dict[str, Any], str | None]:
    """Return scheduler health payload and optional overall-status override."""
    scheduler_status = getattr(request.app.state, "scheduler_status", None)
    if scheduler_status == "disabled_for_test":
        payload: dict[str, Any] = {
            "status": "disabled_for_test",
            "reason": "Background schedulers intentionally disabled for browser-test harness",
            "active_jobs": 0,
        }
        if include_jobs:
            payload["jobs"] = [] if has_auth else "redacted (auth required)"
        return payload, None

    scheduler = get_scheduler()
    if scheduler and scheduler.running:
        jobs = scheduler.get_jobs()
        payload = {
            "status": "healthy",
            "active_jobs": len(jobs),
        }
        if include_jobs:
            payload["jobs"] = (
                [
                    {
                        "id": job.id,
                        "name": job.name,
                        "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                    }
                    for job in jobs[:10]
                ]
                if has_auth
                else "redacted (auth required)"
            )
        return payload, None

    return {"status": "degraded", "error": "Scheduler not running"}, "degraded"


async def _summarize_azure_configuration(settings: Any) -> dict[str, Any]:
    """Report Azure AD configuration with a LIVE liveness probe.

    Five possible statuses (ct-czv tri-state + ct-jxe additions):

        * ``"configured"``      — creds present AND token grant succeeded.
        * ``"unauthenticated"`` — creds present but Azure rejected them
                                  (e.g. expired secret, missing admin
                                  consent). PROMOTES to overall degraded.
        * ``"unreachable"``     — couldn't reach the token endpoint. Does
                                  NOT promote — likely transient.
        * ``"not_required"``    — creds absent, non-prod (acceptable).
        * ``"missing"``         — creds absent, prod (real problem).

    Why this is async now: the probe makes a real HTTPS call to
    ``login.microsoftonline.com``. Results are cached for 5 minutes
    (60s for failures, so rotations recover fast). See
    ``app/core/azure_credential_probe.py`` for the full design.
    """
    from app.core.azure_credential_probe import probe_active_credential

    # ``probe_active_credential`` dispatches on settings.use_oidc_federation:
    #   - True  -> probes the federated path via OIDCCredentialProvider
    #   - False -> probes the legacy client_secret path via HTTPS POST
    # The result.auth_mode field tells you which path was exercised, so a
    # mid-migration regression (e.g. USE_OIDC_FEDERATION silently flipped
    # back to false in App Service settings) is visible at a glance.
    result = await probe_active_credential(settings=settings)

    payload = result.to_dict()
    # Stamp environment for parity with the pre-ct-jxe payload shape, so
    # consumers (UI dot indicator, alert routing) don't need a migration.
    if result.status in {"missing", "not_required", "unauthenticated"}:
        payload["environment"] = settings.environment
    return payload


@router.get("")
async def api_health_check(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get API health status.

    Returns the overall health status of the API and its dependencies.
    This endpoint can be accessed without authentication for load balancer health checks,
    but will include additional details when authenticated.

    Returns:
        Health status including:
        - API status (healthy/degraded/unhealthy)
        - Version and environment info
        - Database connectivity status
        - Cache status
        - Scheduler status
        - Azure configuration status
    """
    settings = get_settings()
    checks: dict[str, Any] = {}
    overall_status = "healthy"

    # Check database connectivity with pool stats
    try:
        start = datetime.now(UTC)
        db.execute(text("SELECT 1"))
        db_time_ms = (datetime.now(UTC) - start).total_seconds() * 1000

        pool_stats = {}
        if not _IS_SQLITE:
            engine = _get_engine()
            pool = engine.pool
            pool_stats = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
            }

        checks["database"] = {
            "status": "healthy",
            "response_time_ms": round(db_time_ms, 2),
            "pool": pool_stats if pool_stats else "n/a (SQLite)",
        }
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "degraded"

    # Check cache via the shared, timeout-bounded probe.
    # The basic /api/v1/health endpoint keeps the payload tight: only status
    # + backend + hit_rate. The /detailed sibling below uses the full payload.
    cache_probe = await cache_manager.check_health()
    if cache_probe["status"] == "healthy":
        checks["cache"] = {
            "status": "healthy",
            "backend": cache_probe.get("backend", "unknown"),
            "hit_rate_percent": cache_probe.get("hit_rate_percent", 0),
        }
    else:
        checks["cache"] = cache_probe
        if cache_probe["status"] != "disabled" and overall_status == "healthy":
            overall_status = "degraded"

    # Check scheduler
    try:
        checks["scheduler"], scheduler_overall = _build_scheduler_check(
            request=request,
            include_jobs=False,
            has_auth=False,
        )
        if scheduler_overall and overall_status == "healthy":
            overall_status = scheduler_overall
    except Exception as e:
        checks["scheduler"] = {"status": "degraded", "error": str(e)}
        if overall_status == "healthy":
            overall_status = "degraded"

    # Check Azure configuration (without making actual API calls)
    azure_configured = all(
        [
            settings.azure_ad_tenant_id,
            settings.azure_ad_client_id,
            settings.azure_ad_client_secret,
        ]
    )
    checks["azure_configured"] = azure_configured

    response: dict[str, Any] = {
        "status": overall_status,
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": checks,
    }

    # Check if user is authenticated for additional details
    auth_header = request.headers.get("Authorization")
    has_auth = bool(auth_header and auth_header.startswith("Bearer "))
    if has_auth:
        response["authenticated"] = True

    return response


@router.get("/detailed")
async def api_health_check_detailed(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get detailed API health status with component metrics.

    This endpoint provides more comprehensive health information including
    detailed metrics for each component. Can be accessed without authentication
    but some sensitive details may be redacted.

    Returns:
        Detailed health status with metrics for all components.
    """
    settings = get_settings()
    checks: dict[str, Any] = {}
    overall_status = "healthy"

    # Check authentication status
    auth_header = request.headers.get("Authorization")
    has_auth = bool(auth_header and auth_header.startswith("Bearer "))

    # Detailed database check
    try:
        from app.core.database import get_db_stats

        start = datetime.now(UTC)
        db.execute(text("SELECT 1"))
        db_time_ms = (datetime.now(UTC) - start).total_seconds() * 1000
        db_stats = get_db_stats(db)

        pool_stats = {}
        if not _IS_SQLITE:
            engine = _get_engine()
            pool = engine.pool
            pool_stats = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
            }

        checks["database"] = {
            "status": "healthy",
            "response_time_ms": round(db_time_ms, 2),
            "pool": pool_stats if pool_stats else "n/a (SQLite)",
            "stats": db_stats if has_auth else "redacted (auth required)",
        }
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "degraded"

    # Detailed cache check via the shared, timeout-bounded probe.
    # /detailed surfaces the full metrics payload (hits/misses/avg latency).
    cache_probe = await cache_manager.check_health(
        probe_key="health_check_detailed",
    )
    checks["cache"] = cache_probe
    if cache_probe["status"] not in {"healthy", "disabled"} and overall_status == "healthy":
        overall_status = "degraded"

    # Scheduler details
    try:
        checks["scheduler"], scheduler_overall = _build_scheduler_check(
            request=request,
            include_jobs=True,
            has_auth=has_auth,
        )
        if scheduler_overall and overall_status == "healthy":
            overall_status = scheduler_overall
    except Exception as e:
        checks["scheduler"] = {"status": "degraded", "error": str(e)}
        if overall_status == "healthy":
            overall_status = "degraded"

    # Azure configuration — tri-state plus a LIVE probe (post-ct-jxe).
    #
    # ct-czv AC #2 originally introduced tri-state so a deliberately un-
    # configured non-prod env doesn't poison the rollup. ct-jxe then
    # showed that even tri-state wasn't enough: production sat on an
    # expired client secret for 20 days while every health check
    # cheerfully reported "configured" (because the env vars were
    # SHAPE-correct, even though Azure rejected them on every actual
    # token request).
    #
    # `_summarize_azure_configuration` now does a real client-credentials
    # grant against the token endpoint (5-minute cache, 5s timeout,
    # never raises). New states:
    #   - "unauthenticated" -> Azure rejected creds (rotate the secret!).
    #                          Promotes overall to "degraded".
    #   - "unreachable"     -> we couldn't reach login.microsoftonline.com.
    #                          Does NOT promote — could be a transient
    #                          Azure-side network blip, not our bug.
    checks["azure_configured"] = await _summarize_azure_configuration(settings)
    azure_status = checks["azure_configured"]["status"]
    if azure_status in {"missing", "unauthenticated"} and overall_status == "healthy":
        overall_status = "degraded"

    # JWT configuration
    checks["jwt_configured"] = bool(settings.jwt_secret_key)

    response: dict[str, Any] = {
        "status": overall_status,
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": checks,
    }

    if has_auth:
        response["authenticated"] = True

    return response


@router.get("/data")
async def data_freshness_check(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Per-tenant sync freshness across all data domains.

    Returns a mapping ``{tenant_key: {domain: iso8601 | null, ..., stale: bool}}``
    used by the UI header indicator to answer the question "is data actually
    flowing?" at a glance. A tenant is ``stale`` when any domain's most recent
    ``synced_at`` is older than ``_get_data_freshness_threshold()`` (or missing).

    No authentication required — returns no sensitive data, just timestamps
    and freshness booleans, so the unauthenticated app shell can render
    the green/amber dot.
    """
    # Lazy imports to avoid importing models at module load (keeps the
    # existing /health endpoint cheap).
    from app.models.compliance import ComplianceSnapshot
    from app.models.cost import CostSnapshot
    from app.models.dmarc import DKIMRecord, DMARCRecord
    from app.models.identity import IdentitySnapshot
    from app.models.resource import Resource
    from app.models.riverside import (
        RiversideCompliance,
        RiversideDeviceCompliance,
        RiversideMFA,
        RiversideThreatData,
    )
    from app.models.tenant import Tenant

    now = datetime.now(UTC)
    tenants = db.query(Tenant).filter(Tenant.is_active == True).all()  # noqa: E712

    # Each entry: (domain_name, model_class, timestamp_column_name).
    # Using a list of tuples (not a dict) lets us decouple the domain name
    # from the model's timestamp attribute — different domains use different
    # column conventions (synced_at vs created_at vs updated_at vs snapshot_date).
    #
    # bd-c56t phase 1 added DMARC + Riverside MFA.
    # bd-dais phase 2 added DKIM + remaining sync-driven Riverside tables.
    # RiversideRequirement is intentionally OMITTED — it's a config catalog
    # (requirements + status), not a periodic sync target, so freshness on it
    # would generate false-positive staleness alerts.
    domains: list[tuple[str, Any, str]] = [
        ("resources", Resource, "synced_at"),
        ("costs", CostSnapshot, "synced_at"),
        ("compliance", ComplianceSnapshot, "synced_at"),
        ("identity", IdentitySnapshot, "synced_at"),
        ("dmarc", DMARCRecord, "synced_at"),
        ("dkim", DKIMRecord, "synced_at"),
        ("riverside_mfa", RiversideMFA, "created_at"),
        ("riverside_compliance", RiversideCompliance, "updated_at"),
        ("riverside_device_compliance", RiversideDeviceCompliance, "snapshot_date"),
        ("riverside_threat_data", RiversideThreatData, "snapshot_date"),
    ]
    required_domains = {"resources", "costs", "compliance", "identity"}
    optional_domains = {name for name, _, _ in domains} - required_domains

    result: dict[str, Any] = {}
    overall_any_stale = False
    overall_optional_stale = False

    for tenant in tenants:
        per_tenant: dict[str, Any] = {}
        tenant_stale = False
        tenant_optional_stale = False
        for name, model, ts_col in domains:
            ts_attr = getattr(model, ts_col, None)
            last = None
            if ts_attr is not None:
                try:
                    last = db.query(func.max(ts_attr)).filter(model.tenant_id == tenant.id).scalar()
                    if name == "costs":
                        last = _latest_cost_freshness(db, tenant.id, last)
                except Exception:  # pragma: no cover — per-domain isolation
                    # Graceful degradation: one failing domain must not 500 the
                    # whole endpoint (bd-c56t AC: endpoint returns 200 regardless
                    # of individual domain health).
                    last = None
            if last is None:
                per_tenant[name] = None
                if name in required_domains:
                    tenant_stale = True
                else:
                    tenant_optional_stale = True
                continue
            # SQLite may return naive datetimes — normalise to UTC for comparison
            last_utc = last if last.tzinfo else last.replace(tzinfo=UTC)
            per_tenant[name] = last_utc.isoformat()
            if now - last_utc > _get_data_freshness_threshold():
                if name in required_domains:
                    tenant_stale = True
                else:
                    tenant_optional_stale = True

        per_tenant["stale"] = tenant_stale
        per_tenant["optional_stale"] = tenant_optional_stale
        overall_any_stale = overall_any_stale or tenant_stale
        overall_optional_stale = overall_optional_stale or tenant_optional_stale
        key = getattr(tenant, "name", None) or tenant.tenant_id
        result[key] = per_tenant

    return {
        "timestamp": now.isoformat(),
        "threshold_hours": int(_get_data_freshness_threshold().total_seconds() // 3600),
        "domains_covered": [name for name, _, _ in domains],
        "required_domains": sorted(required_domains),
        "optional_domains": sorted(optional_domains),
        "any_stale": overall_any_stale,
        "any_optional_stale": overall_optional_stale,
        "tenants": result,
    }
