"""Authentication API routes.

Provides OAuth2 token endpoints, user info, and session management.
Supports both internal JWT tokens and Azure AD OAuth2 integration.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth import (
    TokenData,
    User,
    azure_ad_validator,
    blacklist_token,
    get_current_user,
    jwt_manager,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.models.tenant import Tenant, UserTenant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


# ============================================================================
# Schemas
# ============================================================================


class TokenResponse(BaseModel):
    """OAuth2 token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until access token expires
    scope: str | None = None


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""

    refresh_token: str


class UserInfoResponse(BaseModel):
    """Current user info response."""

    id: str
    email: str | None = None
    name: str | None = None
    roles: list[str]
    tenant_ids: list[str]
    accessible_tenants: list[dict[str, Any]] = []
    auth_provider: str
    is_active: bool


class AzureADLoginRequest(BaseModel):
    """Azure AD OAuth2 callback request."""

    code: str
    redirect_uri: str
    code_verifier: str | None = None  # PKCE


class LogoutResponse(BaseModel):
    """Logout response."""

    message: str
    revoked: bool


class TenantAccessInfo(BaseModel):
    """Tenant access information."""

    tenant_id: str
    name: str
    role: str
    permissions: dict[str, bool]


# ============================================================================
# Internal Authentication
# ============================================================================

# Dev-only credentials — never used outside ENVIRONMENT=development
_DEV_USERNAME = "admin"
_DEV_PASSWORD = "admin"  # noqa: S105


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
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

    # ── Production / Staging: reject direct login entirely ──────────
    if not settings.is_development:
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

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/token", response_model=TokenResponse)
async def token_endpoint(
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
        return await _handle_refresh_token(refresh_token, db)
    elif grant_type == "authorization_code":
        return await _handle_authorization_code(code, redirect_uri, client_id, client_secret)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported grant type: {grant_type}",
        )


async def _handle_refresh_token(
    refresh_token: str | None,
    db: Session,
) -> TokenResponse:
    """Handle refresh token grant."""
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token required",
        )

    try:
        # Validate refresh token
        payload = jwt_manager.decode_token(refresh_token)

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        # Get user info from database
        user_tenant_mappings = (
            db.query(UserTenant)
            .filter(UserTenant.user_id == user_id, UserTenant.is_active == True)  # noqa: E712
            .all()
        )

        tenant_ids = [m.tenant.tenant_id for m in user_tenant_mappings if m.tenant]
        roles = list({m.role for m in user_tenant_mappings}) or ["admin"]  # dev user gets admin

        # Generate new tokens
        settings = get_settings()
        new_access_token = jwt_manager.create_access_token(
            user_id=user_id,
            roles=roles,
            tenant_ids=tenant_ids,
        )
        new_refresh_token = jwt_manager.create_refresh_token(user_id=user_id)

        logger.info(f"Token refreshed for user: {user_id}")

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from e


async def _handle_authorization_code(
    code: str | None,
    redirect_uri: str | None,
    client_id: str | None,
    client_secret: str | None,
) -> TokenResponse:
    """Handle authorization code grant with Azure AD."""
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code required",
        )

    settings = get_settings()

    # Exchange code for tokens with Azure AD
    token_endpoint = settings.azure_ad_token_endpoint

    async with httpx.AsyncClient() as client:
        token_request = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri or "http://localhost:8000/auth/callback",
            "client_id": client_id or settings.azure_ad_client_id,
        }

        if client_secret:
            token_request["client_secret"] = client_secret

        response = await client.post(
            token_endpoint,
            data=token_request,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if response.status_code != 200:
            logger.error(f"Azure AD token exchange failed: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to exchange authorization code",
            )

        token_data = response.json()

        # Validate the ID token and create our own tokens
        id_token = token_data.get("id_token")
        if id_token:
            validated = await azure_ad_validator.validate_token(id_token)

            # Create internal tokens
            access_token = jwt_manager.create_access_token(
                user_id=validated.sub,
                email=validated.email,
                name=validated.name,
                roles=validated.roles,
                tenant_ids=validated.tenant_ids,
            )

            refresh_token = jwt_manager.create_refresh_token(user_id=validated.sub)

            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=settings.jwt_access_token_expire_minutes * 60,
            )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to process authorization code",
    )


# ============================================================================
# Azure AD OAuth2
# ============================================================================


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
        resolved_tenant_ids = await _sync_user_tenant_mappings(db, validated)
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

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


async def _sync_user_tenant_mappings(db: Session, token_data: TokenData) -> list[str]:
    """Sync user tenant mappings based on Azure AD token claims.

    Creates UserTenant records for any tenants the user has access to
    via Azure AD group memberships. Falls back to the Azure AD 'tid'
    claim when no group-based tenant IDs are found.

    Individual tenant failures are logged but do not abort the entire
    sync — the user can still authenticate with partial access.

    Returns:
        List of resolved Azure tenant IDs the user has access to.
    """
    import uuid

    from app.models.tenant import Tenant

    # Start with group-based tenant IDs; fall back to tid claim
    candidate_ids = list(token_data.tenant_ids)
    if not candidate_ids and token_data.azure_tenant_id:
        candidate_ids = [token_data.azure_tenant_id]
        logger.info(
            f"No group-based tenants for {token_data.sub}, "
            f"falling back to Azure AD tid: {token_data.azure_tenant_id}"
        )

    resolved: list[str] = []

    for tenant_id in candidate_ids:
        try:
            # Find tenant by Azure tenant ID
            tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
            if not tenant:
                logger.debug(f"No local tenant record for Azure tenant {tenant_id}, skipping")
                continue

            resolved.append(tenant_id)

            # Ensure a UserTenant mapping exists
            existing = (
                db.query(UserTenant)
                .filter(
                    UserTenant.user_id == token_data.sub,
                    UserTenant.tenant_id == tenant.id,
                )
                .first()
            )

            if not existing:
                mapping = UserTenant(
                    id=str(uuid.uuid4()),
                    user_id=token_data.sub,
                    tenant_id=tenant.id,
                    role="viewer",  # Default role
                    is_active=True,
                    can_view_costs=True,
                    granted_by="azure_ad_sync",
                    granted_at=datetime.utcnow(),
                )
                db.add(mapping)
                db.commit()

                logger.info(f"Created user tenant mapping: {token_data.sub} -> {tenant_id}")
        except OperationalError as e:
            logger.error(f"Database connection error syncing tenant {tenant_id}: {e}")
            db.rollback()
            continue
        except SQLAlchemyError as e:
            logger.error(f"Database error syncing tenant mapping for {tenant_id}: {e}")
            db.rollback()
            continue
        except Exception as e:
            logger.error(f"Failed to sync tenant mapping for {tenant_id}: {type(e).__name__}: {e}")
            db.rollback()
            continue

    return resolved


# ============================================================================
# User Info & Session Management
# ============================================================================


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
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Refresh access token using refresh token.

    Args:
        request: Contains refresh token

    Returns:
        TokenResponse with new access and refresh tokens
    """
    return await _handle_refresh_token(request.refresh_token, db)


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


# ============================================================================
# Staging-only: E2E test token endpoint
# ============================================================================


@router.post("/staging-token", include_in_schema=False)
async def staging_test_token(
    x_staging_admin_key: str | None = None,
    request: Request = None,
) -> dict:
    """Issue a short-lived admin JWT for staging E2E test suites.

    STAGING ONLY — this endpoint is hard-disabled in production.
    The caller must supply the X-Staging-Admin-Key header whose value
    matches the STAGING_ADMIN_KEY environment variable.

    Returns a 1-hour admin JWT that can be used as a Bearer token.
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
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staging token endpoint only available in staging/development",
        )

    # Check the admin key header (from header OR query param for flexibility)
    header_key = request.headers.get("x-staging-admin-key") if request else None
    provided_key = x_staging_admin_key or header_key
    expected_key = os.getenv("STAGING_ADMIN_KEY", "")

    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STAGING_ADMIN_KEY not configured on this server",
        )

    if not provided_key or provided_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid staging admin key",
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
