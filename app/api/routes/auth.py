"""Authentication API routes.

Provides OAuth2 token endpoints, user info, and session management.
Supports both internal JWT tokens and Azure AD OAuth2 integration.
"""

import base64
import hashlib
import hmac
import logging
import os
import secrets
from datetime import timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.services.auth_service import (
    create_token_response_with_cookies,
    handle_authorization_code,
    handle_refresh_token,
    sync_user_tenant_mappings,
)
from app.core.auth import (
    User,
    azure_ad_validator,
    blacklist_token,
    get_current_user,
    jwt_manager,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.models.tenant import Tenant, UserTenant
from app.schemas.auth import (
    AzureADLoginRequest,
    LogoutResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserInfoResponse,
)
from app.schemas.auth import (
    TenantAccessInfo as TenantAccessInfo,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


# Dev-only credentials — never used outside ENVIRONMENT=development
_DEV_USERNAME = "admin"
_DEV_PASSWORD = "admin"

# Backward-compatible private aliases for downstream imports/tests.
_handle_refresh_token = handle_refresh_token
_handle_authorization_code = handle_authorization_code
_sync_user_tenant_mappings = sync_user_tenant_mappings


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    request: Request = None,
) -> TokenResponse:
    """OAuth2 token endpoint for internal authentication.

    In production/staging, direct login is disabled — all authentication
    flows go through Azure AD OAuth2. In development mode only, a
    restricted dev credential pair is accepted.

    Args:
        form_data: OAuth2 username/password form

    Returns:
        TokenResponse with access and refresh tokens
    """
    settings = get_settings()

    # ── Reject direct login outside development / explicit browser-test harness ──
    allow_direct_login = getattr(settings, "allows_direct_login", None)
    if not isinstance(allow_direct_login, bool):
        is_development = getattr(settings, "is_development", False) is True
        is_test = getattr(settings, "is_test", False) is True
        e2e_harness = getattr(settings, "e2e_harness", False) is True
        allow_direct_login = is_development or (is_test and e2e_harness)

    if not allow_direct_login:
        logger.warning("Direct login attempt blocked in %s environment", settings.environment)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Direct login disabled. Use Azure AD OAuth2 authentication.",
        )

    # ── Development-only: validate dev credentials ──────────────────
    if (
        not form_data.username
        or not form_data.password
        or form_data.username != _DEV_USERNAME
        or form_data.password != _DEV_PASSWORD
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create user ID from username
    user_id = f"user:{form_data.username}"

    # Get user tenant mappings from database
    user_tenant_mappings = (
        db.query(UserTenant)
        .filter(UserTenant.user_id == user_id, UserTenant.is_active == True)  # noqa: E712
        .all()
    )

    tenant_ids = [m.tenant.tenant_id for m in user_tenant_mappings if m.tenant]
    roles = list({m.role for m in user_tenant_mappings}) or ["admin"]  # dev user gets admin

    # Generate tokens
    access_token = jwt_manager.create_access_token(
        user_id=user_id,
        email=form_data.username if "@" in form_data.username else None,
        name=form_data.username,
        roles=roles,
        tenant_ids=tenant_ids,
    )

    refresh_token = jwt_manager.create_refresh_token(user_id=user_id)

    logger.info(f"User logged in: {user_id}")

    token_response = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )

    return create_token_response_with_cookies(token_response, request)


@router.post("/token", response_model=TokenResponse)
async def token_endpoint(
    request: Request,
    grant_type: str = Form(...),
    code: str | None = Form(None),
    refresh_token: str | None = Form(None),
    redirect_uri: str | None = Form(None),
    client_id: str | None = Form(None),
    client_secret: str | None = Form(None),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """OAuth2 token endpoint supporting multiple grant types.

    Supports:
    - authorization_code: Exchange auth code for tokens
    - refresh_token: Exchange refresh token for new access token

    Args:
        grant_type: OAuth2 grant type
        code: Authorization code (for authorization_code grant)
        refresh_token: Refresh token (for refresh_token grant)
        redirect_uri: Redirect URI used in auth request
        client_id: OAuth2 client ID
        client_secret: OAuth2 client secret

    Returns:
        TokenResponse with new tokens
    """
    if grant_type == "refresh_token":
        return await handle_refresh_token(refresh_token, db, request)
    elif grant_type == "authorization_code":
        return await handle_authorization_code(
            code, redirect_uri, client_id, client_secret, request
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported grant type: {grant_type}",
        )


# ============================================================================
# Azure AD OAuth2
# ============================================================================


def generate_code_verifier() -> str:
    """Generate a PKCE code verifier (random 128-character base64url string)."""
    return base64.urlsafe_b64encode(secrets.token_bytes(96)).rstrip(b"=").decode("ascii")


def generate_code_challenge(verifier: str) -> str:
    """Generate PKCE code challenge from verifier (SHA256 hash, base64url encoded)."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


@router.get("/azure/login")
async def azure_login_redirect() -> dict[str, str]:
    """Get Azure AD OAuth2 authorization endpoint URL.

    Returns:
        Dictionary with authorization URL and PKCE parameters
    """
    settings = get_settings()

    # Build authorization URL
    auth_url = settings.azure_ad_authorization_endpoint

    return {
        "authorization_endpoint": auth_url,
        "token_endpoint": settings.azure_ad_token_endpoint,
        "jwks_uri": settings.azure_ad_jwks_uri,
        "scopes": " ".join(settings.oauth2_scopes),
        "client_id": settings.azure_ad_client_id or "",
    }


@router.post("/azure/callback", response_model=TokenResponse)
async def azure_oauth_callback(
    request: AzureADLoginRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Handle Azure AD OAuth2 callback.

    Exchanges authorization code for tokens and creates internal JWT tokens.

    Args:
        request: Authorization code and PKCE verifier

    Returns:
        TokenResponse with internal access and refresh tokens
    """
    settings = get_settings()

    # ── Validate redirect URI against whitelist ─────────────────
    if request.redirect_uri not in settings.allowed_redirect_uris:
        logger.warning(
            f"Rejected OAuth callback with unauthorized redirect_uri: {request.redirect_uri[:100]}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid redirect URI",
        )

    # ── Log OAuth state presence for audit trail ────────────────
    if request.state is not None:
        logger.debug("OAuth callback includes state parameter (CSRF token present)")
    else:
        logger.warning("OAuth callback missing state parameter — client may not be validating CSRF")

    # ── Pre-flight: verify Azure AD is configured ───────────────
    if not settings.azure_ad_client_id or not settings.azure_ad_client_secret:
        logger.error(
            "Azure AD OAuth2 not configured: missing AZURE_AD_CLIENT_ID or AZURE_AD_CLIENT_SECRET"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure AD authentication is not configured. Contact your administrator.",
        )

    # ── Step 1: Exchange code for tokens with Azure AD ──────────
    token_request = {
        "grant_type": "authorization_code",
        "code": request.code,
        "redirect_uri": request.redirect_uri,
        "client_id": settings.azure_ad_client_id,
        "client_secret": settings.azure_ad_client_secret,
    }

    if request.code_verifier:
        token_request["code_verifier"] = request.code_verifier

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                settings.azure_ad_token_endpoint,
                data=token_request,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except httpx.HTTPError as e:
        logger.error(f"Azure AD token exchange network error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to reach Azure AD. Please try again.",
        ) from e

    if response.status_code != 200:
        error_body = response.text[:500]
        logger.error(f"Azure AD token exchange failed (HTTP {response.status_code}): {error_body}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to authenticate with Azure AD",
        )

    token_data = response.json()

    # ── Step 2: Validate the ID token ───────────────────────────
    id_token = token_data.get("id_token")
    if not id_token:
        logger.error(f"No ID token in Azure AD response. Keys received: {list(token_data.keys())}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No ID token received from Azure AD",
        )

    try:
        validated = await azure_ad_validator.validate_token(id_token)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ID token validation failed with unexpected error: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to validate Azure AD token",
        ) from e

    # ── Step 3: Sync user tenant mappings ───────────────────────
    # Determine admin status early (needed for fail-closed decision)
    admin_emails_str = os.environ.get("ADMIN_EMAILS", "")
    admin_emails = [e.strip().lower() for e in admin_emails_str.split(",") if e.strip()]

    roles = validated.roles
    if validated.email and validated.email.lower() in admin_emails:
        if "admin" not in roles:
            roles = list(set(roles + ["admin"]))
            logger.info(f"Granting admin role to {validated.email} (in ADMIN_EMAILS)")

    is_admin = "admin" in roles

    try:
        resolved_tenant_ids = await sync_user_tenant_mappings(db, validated)
    except Exception as e:
        logger.error(
            f"User tenant sync failed: {type(e).__name__}: {e}",
            exc_info=True,
        )
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable. Please retry.",
            ) from e
        resolved_tenant_ids = []

    logger.info(
        f"Azure AD callback: user={validated.sub}, "
        f"azure_tid={validated.azure_tenant_id}, "
        f"group_tenant_ids={validated.tenant_ids}, "
        f"resolved_tenant_ids={resolved_tenant_ids}, "
        f"is_admin={is_admin}"
    )

    # If no tenants resolved, grant access to ALL tenants for admin users
    if not resolved_tenant_ids and is_admin:
        try:
            all_tenants = db.query(Tenant).filter(Tenant.is_active == True).all()  # noqa: E712
            resolved_tenant_ids = [t.tenant_id for t in all_tenants]
            logger.info(
                f"Admin user with no tenant mappings, granting access to all "
                f"{len(resolved_tenant_ids)} tenants"
            )
        except OperationalError as e:
            logger.error(f"Database connection error querying admin tenants: {e}")
            resolved_tenant_ids = []
        except Exception as e:
            logger.error(f"Failed to query tenants for admin fallback: {e}")
            resolved_tenant_ids = []

    # Create internal tokens — use resolved tenant IDs (includes tid fallback)
    access_token = jwt_manager.create_access_token(
        user_id=validated.sub,
        email=validated.email,
        name=validated.name,
        roles=roles,
        tenant_ids=resolved_tenant_ids,
    )

    refresh_token = jwt_manager.create_refresh_token(user_id=validated.sub)

    logger.info(f"Azure AD login successful: {validated.sub}")

    token_response = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )

    return create_token_response_with_cookies(token_response, http_request)


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserInfoResponse:
    """Get current user information.

    Returns:
        UserInfoResponse with user details and accessible tenants
    """
    # Get detailed tenant access info
    from app.models.tenant import Tenant

    accessible_tenants = []

    if current_user.tenant_ids:
        tenants = db.query(Tenant).filter(Tenant.tenant_id.in_(current_user.tenant_ids)).all()

        for tenant in tenants:
            mapping = (
                db.query(UserTenant)
                .filter(
                    UserTenant.user_id == current_user.id,
                    UserTenant.tenant_id == tenant.id,
                )
                .first()
            )

            accessible_tenants.append(
                {
                    "tenant_id": tenant.tenant_id,
                    "name": tenant.name,
                    "role": mapping.role if mapping else "viewer",
                    "permissions": {
                        "can_manage_resources": mapping.can_manage_resources if mapping else False,
                        "can_view_costs": mapping.can_view_costs if mapping else True,
                        "can_manage_compliance": mapping.can_manage_compliance
                        if mapping
                        else False,
                    }
                    if mapping
                    else {},
                }
            )

    return UserInfoResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        roles=current_user.roles,
        tenant_ids=current_user.tenant_ids,
        accessible_tenants=accessible_tenants,
        auth_provider=current_user.auth_provider,
        is_active=current_user.is_active,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token_endpoint(
    token_request: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Refresh access token using refresh token.

    Args:
        request: Contains refresh token

    Returns:
        TokenResponse with new access and refresh tokens
    """
    return await handle_refresh_token(token_request.refresh_token, db, request)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> LogoutResponse:
    """Logout user and revoke tokens.

    In a stateless JWT system, this is mainly for client-side cleanup.
    For true revocation, implement a token blacklist.

    Args:
        request: FastAPI request
        current_user: Authenticated user

    Returns:
        LogoutResponse confirming logout
    """
    # Get token from header for blacklisting
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        # Add token to blacklist
        blacklist_token(token)
        logger.info(f"Token revoked for logout: {current_user.id}")

    logger.info(f"User logged out: {current_user.id}")

    return LogoutResponse(
        message="Successfully logged out",
        revoked=True,
    )


@router.get("/health")
async def auth_health_check() -> dict[str, Any]:
    """Check authentication system health.

    Returns:
        Health status of auth components
    """
    settings = get_settings()

    return {
        "status": "healthy",
        "jwt_configured": bool(settings.jwt_secret_key),
        "azure_ad_configured": all(
            [
                settings.azure_ad_tenant_id,
                settings.azure_ad_client_id,
                settings.azure_ad_client_secret,
            ]
        ),
        "token_endpoint": "/api/v1/auth/token",
        "authorization_endpoint": "/api/v1/auth/azure/login",
    }


@router.post("/staging-token", include_in_schema=False)
async def staging_test_token(
    x_staging_admin_key: str = Header(default="", alias="X-Staging-Admin-Key"),
) -> dict:
    """Issue a short-lived admin JWT for staging E2E test suites.

    STAGING ONLY — this endpoint is hard-disabled in production.
    The caller must supply the X-Staging-Admin-Key header whose value
    matches the STAGING_ADMIN_KEY environment variable.

    Returns a 1-hour admin JWT that can be used as a Bearer token.

    ct-wvn: previously the signature was
    ``x_staging_admin_key: str | None = None, request: Request = None``
    which made FastAPI treat ``x_staging_admin_key`` as a query parameter
    (not a header) and ``request`` as a default-None body argument (not
    an injected ``Request``). The endpoint then always 404'd because the
    header value never reached the code. Now we use the proper ``Header``
    dependency with ``default=""`` so a missing header yields a clean
    404 (matching the existing defensive 'looks like the endpoint
    doesn't exist' design) rather than a 422 validation error that would
    leak the endpoint's presence.
    """
    settings = get_settings()

    # Hard block in production — belt-and-suspenders
    if settings.environment == "production":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    if settings.environment not in ("staging", "development"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    provided_key = x_staging_admin_key
    expected_key = os.getenv("STAGING_ADMIN_KEY", "")

    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    # Constant-time comparison to prevent timing attacks
    if not provided_key or not hmac.compare_digest(provided_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    # Issue a 60-minute admin JWT
    access_token = jwt_manager.create_access_token(
        user_id="e2e-test-runner",
        email="e2e@staging.local",
        name="E2E Test Runner",
        roles=["admin"],
        tenant_ids=[],
        expires_delta=timedelta(minutes=60),
    )
    refresh_token = jwt_manager.create_refresh_token(user_id="e2e-test-runner")

    logger.info("Issued staging E2E test token")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 3600,
    }
