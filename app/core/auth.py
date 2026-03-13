"""Authentication and authorization framework.

Implements OAuth2/JWT authentication with Azure AD/Entra ID integration.
Features:
- JWT token generation and validation
- Azure AD OAuth2 token validation
- User extraction from JWT claims
- Role-based access control helpers
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# OAuth2 scheme for token endpoint
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


class TokenData(BaseModel):
    """Token payload data."""

    sub: str  # User ID
    email: str | None = None
    name: str | None = None
    roles: list[str] = []
    tenant_ids: list[str] = []  # Tenants user has access to
    exp: datetime | None = None
    iat: datetime | None = None
    iss: str | None = None
    aud: str | None = None


class User(BaseModel):
    """Authenticated user model."""

    id: str
    email: str | None = None
    name: str | None = None
    roles: list[str] = []
    tenant_ids: list[str] = []
    is_active: bool = True
    auth_provider: str = "internal"  # "internal" or "azure_ad"

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles or "admin" in self.roles

    def has_access_to_tenant(self, tenant_id: str) -> bool:
        """Check if user has access to a specific tenant."""
        if "admin" in self.roles or not self.tenant_ids:
            return True
        return tenant_id in self.tenant_ids


class AzureADTokenValidator:
    """Validator for Azure AD OAuth2 tokens."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._jwks_cache: dict[str, Any] | None = None
        self._jwks_cache_time: datetime | None = None
        self._jwks_cache_ttl = timedelta(hours=24)

    async def _get_jwks(self) -> dict[str, Any]:
        """Fetch JWKS from Azure AD with caching."""
        if self._jwks_cache and self._jwks_cache_time:
            if datetime.now(UTC) - self._jwks_cache_time < self._jwks_cache_ttl:
                return self._jwks_cache

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.settings.azure_ad_jwks_uri)
                response.raise_for_status()
                self._jwks_cache = response.json()
                self._jwks_cache_time = datetime.now(UTC)
                return self._jwks_cache
        except Exception as e:
            logger.error(f"Failed to fetch Azure AD JWKS: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to validate token: JWKS unavailable",
            ) from e

    def _get_signing_key(self, jwks: dict[str, Any], kid: str) -> dict[str, Any] | None:
        """Get signing key from JWKS by key ID."""
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                return key
        return None

    async def validate_token(self, token: str) -> TokenData:
        """Validate an Azure AD JWT token.

        Args:
            token: The JWT token to validate

        Returns:
            TokenData: Extracted token data

        Raises:
            HTTPException: If token is invalid
        """
        try:
            # Decode without verification to get header
            unverified = jwt.get_unverified_header(token)
            kid = unverified.get("kid")

            if not kid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: missing key ID",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Get JWKS and find signing key
            jwks = await self._get_jwks()
            signing_key = self._get_signing_key(jwks, kid)

            if not signing_key:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: signing key not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Validate token
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self.settings.azure_ad_client_id,
                issuer=self.settings.azure_ad_issuer,
            )

            # Extract Azure AD claims
            # oid = object ID (user ID in Azure AD)
            # upn = user principal name (email)
            # groups = Azure AD group memberships
            user_id = payload.get("oid") or payload.get("sub")
            email = payload.get("upn") or payload.get("email") or payload.get("preferred_username")
            name = payload.get("name")

            # Extract groups (tenant permissions)
            groups = payload.get("groups", [])
            if isinstance(groups, str):
                groups = [groups]

            exp = payload.get("exp")
            iat = payload.get("iat")
            return TokenData(
                sub=user_id,
                email=email,
                name=name,
                roles=self._map_groups_to_roles(groups),
                tenant_ids=self._extract_tenant_ids_from_groups(groups),
                exp=datetime.fromtimestamp(exp, tz=UTC) if exp else None,
                iat=datetime.fromtimestamp(iat, tz=UTC) if iat else None,
                iss=payload.get("iss"),
                aud=payload.get("aud"),
            )

        except JWTError as e:
            logger.warning(f"JWT validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {e}",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

    def _map_groups_to_roles(self, groups: list[str]) -> list[str]:
        """Map Azure AD groups to application roles.

        This is a simplified mapping. In production, you'd have a
        mapping configuration in the database or config.
        """
        roles = ["user"]  # Default role

        # Common Azure AD group patterns for governance platform
        admin_groups = ["admin", "administrator", "global-admin", "governance-admin"]
        operator_groups = ["operator", "governance-operator", "platform-operator"]
        reader_groups = ["reader", "viewer", "governance-reader"]

        for group in groups:
            group_lower = group.lower()
            if any(admin in group_lower for admin in admin_groups):
                roles.append("admin")
            if any(operator in group_lower for operator in operator_groups):
                roles.append("operator")
            if any(reader in group_lower for reader in reader_groups):
                roles.append("reader")

        return list(set(roles))

    def _extract_tenant_ids_from_groups(self, groups: list[str]) -> list[str]:
        """Extract tenant IDs from Azure AD group names.

        Expected pattern: "governance-tenant-{tenant_id}" or similar.
        """
        tenant_ids = []
        for group in groups:
            # Pattern: governance-tenant-<tenant_id>
            if "tenant-" in group.lower():
                parts = group.split("tenant-")
                if len(parts) > 1:
                    tenant_id = parts[1].split("-")[0]  # Get first segment after tenant-
                    if tenant_id:
                        tenant_ids.append(tenant_id)
        return tenant_ids


class JWTTokenManager:
    """Manager for internal JWT tokens."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def create_access_token(
        self,
        user_id: str,
        email: str | None = None,
        name: str | None = None,
        roles: list[str] | None = None,
        tenant_ids: list[str] | None = None,
        expires_delta: timedelta | None = None,
    ) -> str:
        """Create a new JWT access token.

        Args:
            user_id: Unique user identifier
            email: User email
            name: User display name
            roles: User roles
            tenant_ids: Tenants user can access
            expires_delta: Custom expiration time

        Returns:
            Encoded JWT token
        """
        if expires_delta is None:
            expires_delta = timedelta(minutes=self.settings.jwt_access_token_expire_minutes)

        expire = datetime.now(UTC) + expires_delta

        to_encode = {
            "sub": user_id,
            "email": email,
            "name": name,
            "roles": roles or ["user"],
            "tenant_ids": tenant_ids or [],
            "exp": expire,
            "iat": datetime.now(UTC),
            "iss": "azure-governance-platform",
            "aud": "azure-governance-api",
            "type": "access",
        }

        return jwt.encode(
            to_encode,
            self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm,
        )

    def create_refresh_token(
        self,
        user_id: str,
        expires_delta: timedelta | None = None,
    ) -> str:
        """Create a new JWT refresh token.

        Args:
            user_id: Unique user identifier
            expires_delta: Custom expiration time

        Returns:
            Encoded JWT refresh token
        """
        if expires_delta is None:
            expires_delta = timedelta(days=self.settings.jwt_refresh_token_expire_days)

        expire = datetime.now(UTC) + expires_delta

        to_encode = {
            "sub": user_id,
            "exp": expire,
            "iat": datetime.now(UTC),
            "iss": "azure-governance-platform",
            "aud": "azure-governance-api",
            "type": "refresh",
        }

        return jwt.encode(
            to_encode,
            self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm,
        )

    def decode_token(self, token: str) -> dict[str, Any]:
        """Decode and validate a JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded token payload

        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm],
                audience="azure-governance-api",
                issuer="azure-governance-platform",
            )
            return payload
        except JWTError as e:
            logger.warning(f"Token decode failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {e}",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e


# Global instances
azure_ad_validator = AzureADTokenValidator()
jwt_manager = JWTTokenManager()

# Token blacklist (Redis-backed with in-memory fallback)
# Re-exported for use by app.api.routes.auth and other modules
from app.core.token_blacklist import (  # noqa: E402, F401
    TokenBlacklist,
    _token_blacklist,
    blacklist_token,
    get_blacklist_backend,
    get_blacklist_size,
    is_token_blacklisted,
)


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
) -> User:
    """Dependency to get the current authenticated user.

    Supports both:
    - Internal JWT tokens (from our /auth/login endpoint)
    - Azure AD tokens (from external OAuth2 flow)

    Args:
        request: FastAPI request object
        token: JWT token from Authorization header

    Returns:
        Authenticated User object

    Raises:
        HTTPException: If authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Try to get token from header if not provided by OAuth2 scheme
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    # Fall back to cookie-based auth (for browser page navigations)
    if not token:
        token = request.cookies.get("access_token")

    if not token:
        raise credentials_exception

    # Check if token is blacklisted
    if is_token_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Detect token type and validate accordingly
    try:
        unverified = jwt.get_unverified_header(token)
        algorithm = unverified.get("alg", "")

        if algorithm == "RS256":
            # Azure AD token (asymmetric signing)
            token_data = await azure_ad_validator.validate_token(token)
            return User(
                id=token_data.sub,
                email=token_data.email,
                name=token_data.name,
                roles=token_data.roles,
                tenant_ids=token_data.tenant_ids,
                is_active=True,
                auth_provider="azure_ad",
            )
        else:
            # Internal JWT token (symmetric signing)
            payload = jwt_manager.decode_token(token)

            user_id: str = payload.get("sub")
            if user_id is None:
                raise credentials_exception

            token_type = payload.get("type")
            if token_type != "access":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            return User(
                id=user_id,
                email=payload.get("email"),
                name=payload.get("name"),
                roles=payload.get("roles", ["user"]),
                tenant_ids=payload.get("tenant_ids", []),
                is_active=True,
                auth_provider="internal",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected auth error: {e}")
        raise credentials_exception from e


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency to get current user and verify they are active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return current_user


def require_roles(required_roles: list[str]):
    """Dependency factory to require specific roles.

    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(user: User = Depends(require_roles(["admin"]))):
            ...
    """

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if "admin" in current_user.roles:
            return current_user

        has_required = any(role in current_user.roles for role in required_roles)
        if not has_required:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required roles: {', '.join(required_roles)}",
            )
        return current_user

    return role_checker


# Convenience alias
get_current_user_dependency = get_current_user
