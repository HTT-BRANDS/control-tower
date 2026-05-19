"""Liveness probe for the Azure AD client-credentials grant.

This module exists because of ct-jxe: the production app reg's client
secret expired on 2026-04-29 and nobody noticed for 20 days. The
``/health/detailed`` endpoint was happily reporting ``azure_configured:
true`` because it only checked that the *env vars were set* — not that
the credentials actually worked. So every monitoring dashboard, every
uptime check, every keepalive ping said "all good" while syncs silently
returned zero records and the user-facing pages went blank.

This probe closes that gap. It runs a real ``client_credentials`` token
request against the configured token endpoint and reports one of:

  - ``"configured"``    — token grant succeeded; secret is live
  - ``"unauthenticated"`` — Azure rejected our creds (AADSTS7000215 etc.)
  - ``"unreachable"``   — network/timeout; can't tell whether the secret
                         works (don't poison overall health on this —
                         could be a transient Azure issue, not our bug)
  - ``"missing"``       — env vars not set; nothing to probe
  - ``"not_required"``  — env vars not set, non-prod env (acceptable)

Design constraints:

1. Must be cheap to call. ``/health/detailed`` gets hit by uptime
   monitors every minute. We cache results for 5 minutes by default so a
   minute-cadence monitor isn't burning a Graph token request per hit.
2. Must NEVER raise. A bug in the probe must not make /health/detailed
   500 — that would defeat the whole point of having a health endpoint.
   All exceptions get caught and mapped to ``"unreachable"``.
3. Must NOT log the secret. The HTTP body and any logged response
   excerpts must not include client_secret. The token endpoint echoes
   the secret back in some error response shapes; we explicitly strip
   that field before logging.
4. Tight timeout (5s). The token endpoint usually responds in <500ms.
   If it's slow, we'd rather report ``unreachable`` than make health
   checks hang and trip downstream readiness gates.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ── Probe configuration ─────────────────────────────────────────────────────

#: How long a successful probe result stays cached before we re-probe. Keep
#: this comfortably under the secret rotation alerting cadence (we want a
#: rotation to trip the dashboard within ~5 min, not 1 hour) but well above
#: per-request frequency so uptime monitors don't burn the Graph quota.
PROBE_CACHE_TTL_SECONDS: float = 300.0  # 5 minutes

#: A failed probe (any non-"configured" result) caches for a shorter window.
#: Rationale: when the secret was just rotated, we want the dashboard to flip
#: back to green within ~60s, not wait the full 5-min success-TTL.
PROBE_FAILURE_CACHE_TTL_SECONDS: float = 60.0  # 1 minute

#: Outbound timeout. ``login.microsoftonline.com`` typically responds in
#: <500ms; 5s is generous and still bounded enough not to stall health checks.
PROBE_TIMEOUT_SECONDS: float = 5.0

#: The scope we ask for. ``.default`` is the standard client-credentials
#: scope — it asks for whatever application permissions have been admin-
#: consented to this app reg. Matches what the sync jobs use
#: (see ``app/api/services/graph_client/_constants.py``), so a "the probe
#: works but syncs don't" gap would be a separate, narrower bug.
PROBE_SCOPE: str = "https://graph.microsoft.com/.default"


# ── Result dataclass ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ProbeResult:
    """The outcome of one probe run, plus diagnostic context.

    ``auth_mode`` is the post-OIDC-migration addition. Pre-migration probes
    only knew about the client_secret flow; ``auth_mode="secret"`` matches
    that legacy behaviour. ``auth_mode="oidc"`` means the probe used the
    federated credential provider (managed identity / workload identity)
    and **no client secret was involved** end-to-end. Dashboards and
    /health/detailed surface this so a regression to secret-mode is
    visible at a glance.
    """

    status: str  # one of the five statuses documented in the module docstring
    detail: str | None = None
    azure_error_code: str | None = None  # e.g. "AADSTS7000215"
    http_status: int | None = None
    cached_at: float = 0.0  # epoch seconds for cache freshness tracking
    auth_mode: str = "secret"  # "oidc" or "secret" — which path was probed

    def to_dict(self) -> dict[str, Any]:
        """Render for inclusion in /health/detailed."""
        out: dict[str, Any] = {"status": self.status, "auth_mode": self.auth_mode}
        if self.detail:
            out["detail"] = self.detail
        if self.azure_error_code:
            out["azure_error_code"] = self.azure_error_code
        if self.http_status is not None:
            out["http_status"] = self.http_status
        return out


# ── Probe cache ─────────────────────────────────────────────────────────────


@dataclass
class _CacheSlot:
    """Mutable cache slot. We key the cache by (tenant_id, client_id) so a
    deploy that swaps the app reg invalidates the cache automatically."""

    result: ProbeResult
    expires_at: float


# Module-level singleton, guarded by a Lock to be thread-safe. We use a
# threading.Lock (not asyncio) because the probe is also called from sync
# contexts (e.g. preflight checks) and we want consistent semantics.
_cache: dict[tuple[str, str], _CacheSlot] = {}
_cache_lock = threading.Lock()


def _cache_get(tenant_id: str, client_id: str) -> ProbeResult | None:
    """Return a cached result if still fresh; otherwise None."""
    key = (tenant_id, client_id)
    now = time.monotonic()
    with _cache_lock:
        slot = _cache.get(key)
        if slot is None or slot.expires_at <= now:
            return None
        return slot.result


def _cache_set(tenant_id: str, client_id: str, result: ProbeResult) -> None:
    """Cache a probe result. Successful and failed probes get different TTLs
    so we don't sit on a stale 'unauthenticated' for 5 min after Tyler
    rotates the secret."""
    key = (tenant_id, client_id)
    ttl = (
        PROBE_CACHE_TTL_SECONDS
        if result.status == "configured"
        else PROBE_FAILURE_CACHE_TTL_SECONDS
    )
    with _cache_lock:
        _cache[key] = _CacheSlot(result=result, expires_at=time.monotonic() + ttl)


def reset_probe_cache() -> None:
    """Public helper for tests. Production code should NOT call this — the
    cache is the whole point of the design (avoid burning Graph quota on
    every health-check ping)."""
    with _cache_lock:
        _cache.clear()


# ── The probe itself ────────────────────────────────────────────────────────


def _redact_for_log(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Strip ``client_secret`` from any payload before logging.

    The token endpoint echoes ``client_secret`` back in some error responses,
    and we ALSO send it in the request body — so when we log "request that
    failed" or "response from Azure", we must scrub it. Forgetting this once
    leaks secrets to log aggregation forever.
    """
    if payload is None:
        return None
    return {k: ("***REDACTED***" if k == "client_secret" else v) for k, v in payload.items()}


async def probe_client_credential(
    *,
    tenant_id: str | None,
    client_id: str | None,
    client_secret: str | None,
    token_endpoint: str,
    is_production: bool,
    use_cache: bool = True,
) -> ProbeResult:
    """Attempt a client_credentials token grant and report the result.

    Args:
        tenant_id: from settings.azure_ad_tenant_id
        client_id: from settings.azure_ad_client_id
        client_secret: from settings.azure_ad_client_secret
        token_endpoint: from settings.azure_ad_token_endpoint
        is_production: from settings.is_production (controls
            ``missing`` vs ``not_required`` for absent creds)
        use_cache: pass ``False`` to bypass the cache (tests only)

    Returns:
        A ``ProbeResult`` that's safe to render into a health endpoint.
        NEVER raises — all exceptions get mapped to ``unreachable``.
    """
    # ── 1. Shape check (cheap, no network) ──────────────────────────
    if not tenant_id or not client_id or not client_secret:
        return ProbeResult(
            status="missing" if is_production else "not_required",
            detail=(
                "AZURE_AD_TENANT_ID / CLIENT_ID / CLIENT_SECRET not all set"
                if is_production
                else "Azure AD credentials not configured (acceptable outside production)"
            ),
            auth_mode="secret",
        )

    # ── 2. Cache lookup ─────────────────────────────────────────────
    if use_cache:
        cached = _cache_get(tenant_id, client_id)
        if cached is not None:
            return cached

    # ── 3. Live probe ───────────────────────────────────────────────
    body = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": PROBE_SCOPE,
    }
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_SECONDS) as client:
            resp = await client.post(token_endpoint, data=body)
    except httpx.TimeoutException:
        result = ProbeResult(
            status="unreachable",
            detail=f"Token endpoint timed out after {PROBE_TIMEOUT_SECONDS}s",
            auth_mode="secret",
        )
        _cache_set(tenant_id, client_id, result)
        return result
    except Exception as exc:
        logger.warning(
            "Azure credential probe network error",
            extra={"error": str(exc), "endpoint": token_endpoint},
        )
        result = ProbeResult(
            status="unreachable",
            detail=f"Network error contacting token endpoint: {type(exc).__name__}",
            auth_mode="secret",
        )
        _cache_set(tenant_id, client_id, result)
        return result

    # ── 4. Interpret the response ───────────────────────────────────
    if resp.status_code == 200:
        result = ProbeResult(status="configured", http_status=200, auth_mode="secret")
        _cache_set(tenant_id, client_id, result)
        return result

    # Try to extract Azure's structured error. The response shape is:
    #   { "error": "invalid_client",
    #     "error_description": "AADSTS7000215: Invalid client secret ..." }
    # We pull out the AADSTS code for at-a-glance diagnostics.
    azure_error_code: str | None = None
    detail = f"HTTP {resp.status_code}"
    try:
        body_json = resp.json()
        err_desc = body_json.get("error_description", "")
        # AADSTS codes are 5-7 digits prefixed by "AADSTS". Find the first one.
        import re

        m = re.search(r"AADSTS\d{4,7}", err_desc)
        if m:
            azure_error_code = m.group(0)
        # Trim error_description to first sentence to keep payload small.
        if err_desc:
            detail = err_desc.split(".", 1)[0][:200]
    except Exception:
        # Non-JSON response or parse error — fall back to plain detail.
        logger.debug(
            "Azure credential probe got non-JSON error response",
            extra={"http_status": resp.status_code, "body_excerpt": resp.text[:200]},
        )

    result = ProbeResult(
        status="unauthenticated",
        detail=detail,
        azure_error_code=azure_error_code,
        http_status=resp.status_code,
        auth_mode="secret",
    )
    _cache_set(tenant_id, client_id, result)
    logger.warning(
        "Azure credential probe rejected by Azure AD",
        extra={
            "http_status": resp.status_code,
            "azure_error_code": azure_error_code,
            # NEVER log the request body — _redact_for_log makes that explicit.
            "request_body_redacted": _redact_for_log(body),
        },
    )
    return result


# ── OIDC federation probe ───────────────────────────────────────────────────


async def probe_oidc_federation(
    *,
    tenant_id: str | None,
    client_id: str | None,
    is_production: bool,
    use_cache: bool = True,
) -> ProbeResult:
    """Verify the OIDC federated credential path actually mints tokens.

    The legacy ``probe_client_credential`` checks the SECRET path. This is
    its sibling for the federated path: we ask the OIDC credential provider
    for a credential and call ``get_token()`` on it, which exercises the
    full federation flow:

        Managed Identity (App Service / UAMI)
            -> MI mints an OIDC assertion JWT
            -> ClientAssertionCredential exchanges it for an access token
            -> we get a real bearer token for graph.microsoft.com

    If any step fails (MI not bound, federated credential not configured
    on the app reg, wrong audience, missing admin consent), this probe
    reports ``"unauthenticated"`` — same as the secret probe — so the
    /health/detailed payload stays shape-stable across the migration.

    Why we wrap ``get_token`` in ``asyncio.to_thread``:
        The azure-identity SDK exposes a sync ``get_token`` on every
        TokenCredential. There's an async sibling in ``azure.identity.aio``
        but the rest of the codebase uses the sync version everywhere
        (see app/api/services/azure_client.py). To stay consistent — and
        to avoid mixing two HTTP stacks in one tenant — we keep the sync
        call and offload it to a worker thread. The 5s timeout still
        applies via ``asyncio.wait_for``.
    """
    # ── 1. Shape check ──────────────────────────────────────────────
    # OIDC mode still needs tenant_id and client_id (they identify which
    # app reg in which tenant to mint the token for). It does NOT need a
    # client_secret — that's the whole point. So the "missing" criteria
    # are different from the secret path.
    if not tenant_id or not client_id:
        return ProbeResult(
            status="missing" if is_production else "not_required",
            detail=(
                "OIDC mode: AZURE_AD_TENANT_ID and AZURE_AD_CLIENT_ID required"
                if is_production
                else "OIDC mode: tenant_id/client_id not set (acceptable outside production)"
            ),
            auth_mode="oidc",
        )

    # ── 2. Cache lookup ─────────────────────────────────────────────
    if use_cache:
        cached = _cache_get(tenant_id, client_id)
        if cached is not None:
            return cached

    # ── 3. Live probe ───────────────────────────────────────────────
    # Lazy imports: azure.identity is heavy AND we don't want a missing
    # MI binding in a unit-test environment to import-crash this module.
    import asyncio

    try:
        from app.core.oidc_credential import get_oidc_provider

        # Build the per-tenant credential and call get_token() in a thread.
        # Wrap with wait_for so a stuck MI endpoint can't hang health checks.
        def _acquire_token() -> Any:
            provider = get_oidc_provider()
            credential = provider.get_credential_for_tenant(tenant_id, client_id)
            return credential.get_token(PROBE_SCOPE)

        token = await asyncio.wait_for(
            asyncio.to_thread(_acquire_token),
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        result = ProbeResult(
            status="unreachable",
            detail=f"OIDC token acquisition timed out after {PROBE_TIMEOUT_SECONDS}s",
            auth_mode="oidc",
        )
        _cache_set(tenant_id, client_id, result)
        return result
    except Exception as exc:
        # ClientAuthenticationError from azure.identity surfaces here. We map
        # everything caught here to "unauthenticated" because at this point we
        # KNOW our code reached the SDK — it's not a network blip, it's a
        # config mismatch (MI not bound, federated cred missing, wrong audience).
        #
        # The one exception is import-time failures (e.g. azure.identity not
        # installed in a slim test env). We use the exception class name to
        # disambiguate: ImportError / ModuleNotFoundError -> unreachable.
        exc_name = type(exc).__name__
        status_for_result = (
            "unreachable" if exc_name in {"ImportError", "ModuleNotFoundError"} else "unauthenticated"
        )
        # Try to extract an AADSTS code from the SDK's error message — Azure
        # threads them through verbatim, e.g. "AADSTS70011: scope is invalid".
        import re

        msg = str(exc)
        m = re.search(r"AADSTS\d{4,7}", msg)
        azure_error_code = m.group(0) if m else None
        # Keep detail short and free of stack-trace noise.
        detail = f"{exc_name}: {msg.splitlines()[0][:180]}" if msg else exc_name
        result = ProbeResult(
            status=status_for_result,
            detail=detail,
            azure_error_code=azure_error_code,
            auth_mode="oidc",
        )
        _cache_set(tenant_id, client_id, result)
        logger.warning(
            "OIDC credential probe failed",
            extra={
                "exception_class": exc_name,
                "azure_error_code": azure_error_code,
                "tenant_id": tenant_id,
                "client_id_prefix": client_id[:8] if client_id else None,
            },
        )
        return result

    # If we got here without exception, the token request succeeded.
    # We don't inspect token.token contents — that would imply we're going
    # to USE this token for something, which we explicitly aren't. The
    # health probe's contract is "can we mint a token?", nothing more.
    _ = token  # silence linters: we deliberately ignore the token value
    result = ProbeResult(status="configured", auth_mode="oidc")
    _cache_set(tenant_id, client_id, result)
    return result


# ── Top-level dispatcher: pick the right probe based on settings ───────────


async def probe_active_credential(
    *,
    settings: Any,
    use_cache: bool = True,
) -> ProbeResult:
    """Probe whichever credential path the runtime is configured for.

    This is the function /health/detailed should call. It reads
    ``settings.use_oidc_federation`` and dispatches to the right probe.
    The result's ``auth_mode`` field tells you which path actually got
    exercised — critical for verifying an in-flight OIDC migration.

    Why a dispatcher rather than two endpoints:
        We want exactly ONE source of truth for "is the active credential
        path working?" If /health/detailed had to OR-together two probes,
        a stale secret-mode probe could mask a broken OIDC config. By
        dispatching, we always probe the path that's actually serving
        production traffic.
    """
    if getattr(settings, "use_oidc_federation", False):
        return await probe_oidc_federation(
            tenant_id=settings.azure_ad_tenant_id,
            client_id=settings.azure_ad_client_id,
            is_production=settings.is_production,
            use_cache=use_cache,
        )
    return await probe_client_credential(
        tenant_id=settings.azure_ad_tenant_id,
        client_id=settings.azure_ad_client_id,
        client_secret=settings.azure_ad_client_secret,
        token_endpoint=settings.azure_ad_token_endpoint,
        is_production=settings.is_production,
        use_cache=use_cache,
    )
