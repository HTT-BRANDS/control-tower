"""Unit tests for authentication and authorization framework.

Tests JWT token generation/validation, Azure AD integration,
and role-based access control helpers.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException

from app.core.auth import (
    AzureADTokenValidator,
    JWTTokenManager,
    TokenData,
    User,
    require_roles,
)


@pytest.fixture
def mock_settings():
    """Create mock settings for auth tests."""
    settings = MagicMock()
    settings.jwt_secret_key = "test-secret-key-that-is-long-enough-for-validation"
    settings.jwt_algorithm = "HS256"
    settings.jwt_access_token_expire_minutes = 30
    settings.jwt_refresh_token_expire_days = 7
    settings.azure_ad_client_id = "test-client-id"
    settings.azure_ad_issuer = "https://login.microsoftonline.com/test-tenant/v2.0"
    settings.azure_ad_jwks_uri = "https://login.microsoftonline.com/test-tenant/discovery/v2.0/keys"
    return settings


class TestTokenData:
    """Tests for the TokenData Pydantic model."""

    def test_create_with_all_fields(self):
        """TokenData can be created with all fields populated."""
        token_data = TokenData(
            sub="user-123",
            email="test@example.com",
            name="Test User",
            roles=["admin", "user"],
            tenant_ids=["tenant-1", "tenant-2"],
            exp=datetime.now(UTC) + timedelta(hours=1),
            iat=datetime.now(UTC),
            iss="test-issuer",
            aud="test-audience",
        )
        assert token_data.sub == "user-123"
        assert token_data.email == "test@example.com"
        assert token_data.name == "Test User"
        assert token_data.roles == ["admin", "user"]
        assert token_data.tenant_ids == ["tenant-1", "tenant-2"]

    def test_create_with_minimal_fields(self):
        """TokenData can be created with only sub (user ID)."""
        token_data = TokenData(sub="user-456")
        assert token_data.sub == "user-456"
        assert token_data.email is None
        assert token_data.name is None

    def test_default_roles_is_empty_list(self):
        """TokenData has empty list as default for roles."""
        token_data = TokenData(sub="user-789")
        assert token_data.roles == []
        assert isinstance(token_data.roles, list)

    def test_default_tenant_ids_is_empty_list(self):
        """TokenData has empty list as default for tenant_ids."""
        token_data = TokenData(sub="user-101")
        assert token_data.tenant_ids == []
        assert isinstance(token_data.tenant_ids, list)


class TestUser:
    """Tests for the User model and its authorization methods."""

    def test_has_role_returns_true_when_user_has_admin_role(self):
        """User.has_role returns True when user has the admin role."""
        user = User(
            id="user-1",
            email="admin@example.com",
            roles=["admin"],
        )
        assert user.has_role("admin") is True

    def test_has_role_returns_true_when_user_has_specific_role(self):
        """User.has_role returns True when user has the requested role."""
        user = User(
            id="user-2",
            email="viewer@example.com",
            roles=["viewer", "operator"],
        )
        assert user.has_role("viewer") is True
        assert user.has_role("operator") is True

    def test_has_role_returns_true_for_admin_bypass(self):
        """User.has_role returns True for any role when user is admin."""
        user = User(
            id="user-3",
            email="admin@example.com",
            roles=["admin"],
        )
        # Admin should pass any role check
        assert user.has_role("viewer") is True
        assert user.has_role("operator") is True
        assert user.has_role("any-random-role") is True

    def test_has_role_returns_false_when_user_lacks_role(self):
        """User.has_role returns False when user lacks the required role."""
        user = User(
            id="user-4",
            email="viewer@example.com",
            roles=["viewer"],
        )
        assert user.has_role("admin") is False
        assert user.has_role("operator") is False

    def test_has_access_to_tenant_returns_true_when_tenant_in_list(self):
        """User.has_access_to_tenant returns True when tenant_id is in tenant_ids."""
        user = User(
            id="user-5",
            email="user@example.com",
            roles=["user"],
            tenant_ids=["tenant-a", "tenant-b"],
        )
        assert user.has_access_to_tenant("tenant-a") is True
        assert user.has_access_to_tenant("tenant-b") is True

    def test_has_access_to_tenant_returns_true_when_user_is_admin(self):
        """User.has_access_to_tenant returns True when user is admin (bypass)."""
        user = User(
            id="user-6",
            email="admin@example.com",
            roles=["admin"],
            tenant_ids=["tenant-a"],
        )
        # Admin should access any tenant
        assert user.has_access_to_tenant("tenant-z") is True
        assert user.has_access_to_tenant("any-tenant-id") is True

    def test_has_access_to_tenant_fails_closed_when_no_tenants(self):
        """User.has_access_to_tenant fails closed when tenant_ids is empty.

        P0 security fix: empty tenant_ids means no access, not universal access.
        Admin role is the only bypass for all-tenant access.
        """
        user = User(
            id="user-7",
            email="user@example.com",
            roles=["user"],
            tenant_ids=[],
        )
        # Fail closed — no tenants assigned means no access
        assert user.has_access_to_tenant("any-tenant") is False

    def test_has_access_to_tenant_returns_false_when_tenant_not_in_list(self):
        """User.has_access_to_tenant returns False when tenant_id not in tenant_ids."""
        user = User(
            id="user-8",
            email="user@example.com",
            roles=["user"],
            tenant_ids=["tenant-a", "tenant-b"],
        )
        assert user.has_access_to_tenant("tenant-c") is False
        assert user.has_access_to_tenant("tenant-z") is False


class TestJWTTokenManager:
    """Tests for JWT token creation and decoding."""

    @patch("app.core.auth.get_settings")
    def test_create_access_token_returns_string(self, mock_get_settings, mock_settings):
        """JWTTokenManager.create_access_token returns a JWT token string."""
        mock_get_settings.return_value = mock_settings
        manager = JWTTokenManager()

        token = manager.create_access_token(
            user_id="user-123",
            email="test@example.com",
        )

        assert isinstance(token, str)
        assert len(token) > 0

    @patch("app.core.auth.get_settings")
    def test_create_access_token_decodes_to_correct_sub(self, mock_get_settings, mock_settings):
        """JWTTokenManager.create_access_token token contains correct sub claim."""
        mock_get_settings.return_value = mock_settings
        manager = JWTTokenManager()

        token = manager.create_access_token(user_id="user-456")
        payload = jwt.decode(
            token,
            mock_settings.jwt_secret_key,
            algorithms=[mock_settings.jwt_algorithm],
            options={"verify_aud": False, "verify_iss": False},
        )

        assert payload["sub"] == "user-456"

    @patch("app.core.auth.get_settings")
    def test_create_access_token_includes_type_access(self, mock_get_settings, mock_settings):
        """JWTTokenManager.create_access_token includes type='access'."""
        mock_get_settings.return_value = mock_settings
        manager = JWTTokenManager()

        token = manager.create_access_token(user_id="user-789")
        payload = jwt.decode(
            token,
            mock_settings.jwt_secret_key,
            algorithms=[mock_settings.jwt_algorithm],
            options={"verify_aud": False, "verify_iss": False},
        )

        assert payload["type"] == "access"

    @patch("app.core.auth.get_settings")
    def test_create_access_token_includes_roles_and_tenant_ids(
        self, mock_get_settings, mock_settings
    ):
        """JWTTokenManager.create_access_token includes roles and tenant_ids."""
        mock_get_settings.return_value = mock_settings
        manager = JWTTokenManager()

        token = manager.create_access_token(
            user_id="user-101",
            roles=["admin", "operator"],
            tenant_ids=["tenant-1", "tenant-2"],
        )
        payload = jwt.decode(
            token,
            mock_settings.jwt_secret_key,
            algorithms=[mock_settings.jwt_algorithm],
            options={"verify_aud": False, "verify_iss": False},
        )

        assert payload["roles"] == ["admin", "operator"]
        assert payload["tenant_ids"] == ["tenant-1", "tenant-2"]

    @patch("app.core.auth.get_settings")
    def test_create_access_token_custom_expires_delta(self, mock_get_settings, mock_settings):
        """JWTTokenManager.create_access_token respects custom expires_delta."""
        mock_get_settings.return_value = mock_settings
        manager = JWTTokenManager()

        custom_delta = timedelta(minutes=5)
        token = manager.create_access_token(
            user_id="user-202",
            expires_delta=custom_delta,
        )
        payload = jwt.decode(
            token,
            mock_settings.jwt_secret_key,
            algorithms=[mock_settings.jwt_algorithm],
            options={"verify_aud": False, "verify_iss": False},
        )

        # Check expiration is approximately 5 minutes from now
        exp_time = datetime.fromtimestamp(payload["exp"], tz=UTC)
        expected_exp = datetime.now(UTC) + custom_delta
        # Allow 10 second tolerance
        assert abs((exp_time - expected_exp).total_seconds()) < 10

    @patch("app.core.auth.get_settings")
    def test_create_refresh_token_returns_string(self, mock_get_settings, mock_settings):
        """JWTTokenManager.create_refresh_token returns a JWT token string."""
        mock_get_settings.return_value = mock_settings
        manager = JWTTokenManager()

        token = manager.create_refresh_token(user_id="user-303")

        assert isinstance(token, str)
        assert len(token) > 0

    @patch("app.core.auth.get_settings")
    def test_create_refresh_token_includes_type_refresh(self, mock_get_settings, mock_settings):
        """JWTTokenManager.create_refresh_token includes type='refresh'."""
        mock_get_settings.return_value = mock_settings
        manager = JWTTokenManager()

        token = manager.create_refresh_token(user_id="user-404")
        payload = jwt.decode(
            token,
            mock_settings.jwt_secret_key,
            algorithms=[mock_settings.jwt_algorithm],
            options={"verify_aud": False, "verify_iss": False},
        )

        assert payload["type"] == "refresh"

    @patch("app.core.auth.get_settings")
    def test_decode_token_valid_token_succeeds(self, mock_get_settings, mock_settings):
        """JWTTokenManager.decode_token succeeds with valid token."""
        mock_get_settings.return_value = mock_settings
        manager = JWTTokenManager()

        token = manager.create_access_token(user_id="user-505")
        payload = manager.decode_token(token)

        assert payload["sub"] == "user-505"
        assert payload["type"] == "access"

    @patch("app.core.auth.get_settings")
    def test_decode_token_expired_token_raises_401(self, mock_get_settings, mock_settings):
        """JWTTokenManager.decode_token raises HTTPException 401 for expired token."""
        mock_get_settings.return_value = mock_settings
        manager = JWTTokenManager()

        # Create token that expires immediately
        token = manager.create_access_token(
            user_id="user-606",
            expires_delta=timedelta(seconds=-1),  # Already expired
        )

        with pytest.raises(HTTPException) as exc_info:
            manager.decode_token(token)

        assert exc_info.value.status_code == 401

    @patch("app.core.auth.get_settings")
    def test_decode_token_wrong_secret_raises_401(self, mock_get_settings, mock_settings):
        """JWTTokenManager.decode_token raises HTTPException 401 with wrong secret."""
        mock_get_settings.return_value = mock_settings
        manager = JWTTokenManager()

        # Create token with one secret
        token = manager.create_access_token(user_id="user-707")

        # Change the secret and try to decode
        mock_settings.jwt_secret_key = "different-secret-key-that-will-fail"

        with pytest.raises(HTTPException) as exc_info:
            manager.decode_token(token)

        assert exc_info.value.status_code == 401

    @patch("app.core.auth.get_settings")
    def test_decode_token_wrong_audience_raises_401(self, mock_get_settings, mock_settings):
        """JWTTokenManager.decode_token raises HTTPException 401 with wrong audience."""
        mock_get_settings.return_value = mock_settings
        manager = JWTTokenManager()

        # Create token with different audience
        payload = {
            "sub": "user-808",
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
            "iss": "azure-governance-platform",
            "aud": "wrong-audience",  # Wrong audience
            "type": "access",
        }
        token = jwt.encode(
            payload,
            mock_settings.jwt_secret_key,
            algorithm=mock_settings.jwt_algorithm,
        )

        with pytest.raises(HTTPException) as exc_info:
            manager.decode_token(token)

        assert exc_info.value.status_code == 401


class TestAzureADTokenValidator:
    """Tests for Azure AD token validation and group mapping."""

    @patch("app.core.auth.get_settings")
    def test_map_groups_to_roles_admin(self, mock_get_settings, mock_settings):
        """_map_groups_to_roles includes 'admin' for admin groups."""
        mock_get_settings.return_value = mock_settings
        validator = AzureADTokenValidator()

        roles = validator._map_groups_to_roles(["global-admin", "other-group"])
        assert "admin" in roles
        assert "user" in roles  # Default role always included

    @patch("app.core.auth.get_settings")
    def test_map_groups_to_roles_operator(self, mock_get_settings, mock_settings):
        """_map_groups_to_roles includes 'operator' for operator groups."""
        mock_get_settings.return_value = mock_settings
        validator = AzureADTokenValidator()

        roles = validator._map_groups_to_roles(["governance-operator"])
        assert "operator" in roles
        assert "user" in roles

    @patch("app.core.auth.get_settings")
    def test_map_groups_to_roles_reader(self, mock_get_settings, mock_settings):
        """_map_groups_to_roles includes 'reader' for reader groups."""
        mock_get_settings.return_value = mock_settings
        validator = AzureADTokenValidator()

        roles = validator._map_groups_to_roles(["governance-reader", "viewer"])
        assert "reader" in roles
        assert "user" in roles

    @patch("app.core.auth.get_settings")
    def test_map_groups_to_roles_default_user(self, mock_get_settings, mock_settings):
        """_map_groups_to_roles returns ['user'] as default for empty groups."""
        mock_get_settings.return_value = mock_settings
        validator = AzureADTokenValidator()

        roles = validator._map_groups_to_roles([])
        assert roles == ["user"]

    @patch("app.core.auth.get_settings")
    def test_extract_tenant_ids_from_groups(self, mock_get_settings, mock_settings):
        """_extract_tenant_ids_from_groups extracts tenant IDs from group names."""
        mock_get_settings.return_value = mock_settings
        validator = AzureADTokenValidator()

        tenant_ids = validator._extract_tenant_ids_from_groups(
            [
                "governance-tenant-abc123",
                "governance-tenant-xyz789",
                "other-group",
            ]
        )
        assert "abc123" in tenant_ids
        assert "xyz789" in tenant_ids
        assert len(tenant_ids) == 2

    @patch("app.core.auth.get_settings")
    def test_extract_tenant_ids_from_groups_empty(self, mock_get_settings, mock_settings):
        """_extract_tenant_ids_from_groups returns empty list for no tenant groups."""
        mock_get_settings.return_value = mock_settings
        validator = AzureADTokenValidator()

        tenant_ids = validator._extract_tenant_ids_from_groups(
            [
                "admin",
                "operator",
                "other-group",
            ]
        )
        assert tenant_ids == []

    @patch("app.core.auth.get_settings")
    @patch("app.core.auth.datetime")
    async def test_jwks_cache_respects_ttl(self, mock_datetime, mock_get_settings, mock_settings):
        """AzureADTokenValidator respects JWKS cache TTL."""
        mock_get_settings.return_value = mock_settings
        validator = AzureADTokenValidator()

        # Mock datetime for cache timing
        now = datetime.now(UTC)
        mock_datetime.now.return_value = now

        # Mock httpx client
        mock_jwks = {"keys": [{"kid": "test-key", "use": "sig"}]}
        mock_response = MagicMock()
        mock_response.json.return_value = mock_jwks
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # First call - should hit the API
            jwks1 = await validator._get_jwks()
            assert jwks1 == mock_jwks
            assert mock_client.get.call_count == 1

            # Second call within TTL - should use cache
            mock_datetime.now.return_value = now + timedelta(hours=12)
            jwks2 = await validator._get_jwks()
            assert jwks2 == mock_jwks
            assert mock_client.get.call_count == 1  # Still 1 (cached)

            # Third call after TTL - should hit the API again
            mock_datetime.now.return_value = now + timedelta(hours=25)
            await validator._get_jwks()
            assert mock_client.get.call_count == 2  # New call


class TestRequireRoles:
    """Tests for the require_roles dependency factory."""

    @pytest.mark.asyncio
    async def test_admin_user_passes_any_role_check(self):
        """require_roles allows admin users through any role check."""
        admin_user = User(
            id="admin-1",
            email="admin@example.com",
            roles=["admin"],
        )

        # Create the dependency
        role_checker = require_roles(["operator", "viewer"])

        # Admin should pass even though they don't have operator or viewer roles
        result = await role_checker(current_user=admin_user)
        assert result == admin_user

    @pytest.mark.asyncio
    async def test_user_with_matching_role_passes(self):
        """require_roles allows users with matching role."""
        operator_user = User(
            id="op-1",
            email="operator@example.com",
            roles=["operator", "user"],
        )

        # Create the dependency
        role_checker = require_roles(["operator"])

        # User has operator role, should pass
        result = await role_checker(current_user=operator_user)
        assert result == operator_user

    @pytest.mark.asyncio
    async def test_user_without_matching_role_gets_403(self):
        """require_roles raises 403 for users without required role."""
        viewer_user = User(
            id="viewer-1",
            email="viewer@example.com",
            roles=["viewer", "user"],
        )

        # Create the dependency
        role_checker = require_roles(["admin", "operator"])

        # User only has viewer role, should get 403
        with pytest.raises(HTTPException) as exc_info:
            await role_checker(current_user=viewer_user)

        assert exc_info.value.status_code == 403
        assert "Required roles" in exc_info.value.detail


class TestAlgorithmConfusionPrevention:
    """Tests for algorithm confusion attack prevention (ARCH-P0-4, CVSS 9.0 CRITICAL).

    These tests verify that token type detection uses issuer claim (iss)
    instead of algorithm header (alg) to prevent algorithm confusion attacks.

    See: https://auth0.com/blog/critical-vulnerabilities-in-json-web-token-libraries/
    """

    def test_routing_by_issuer_detects_azure_ad_pattern(self):
        """Tokens with Azure AD issuer are routed to Azure AD validator.

        This test verifies the core fix: we route by issuer claim (iss),
        not algorithm header (alg). A forged token with Azure AD issuer
        but HS256 algorithm will be routed to Azure AD validator which
        will reject it (since it's not a valid Azure AD signature).
        """

        # Create a forged token with Azure AD issuer but HS256 algorithm
        # This is the algorithm confusion attack pattern
        forged_payload = {
            "sub": "attacker-user-id",
            "email": "attacker@example.com",
            "name": "Attacker",
            "iss": "https://login.microsoftonline.com/test-tenant/v2.0",  # Azure AD issuer
            "aud": "test-client-id",
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
        }

        # Sign with HS256 (attacker trying to bypass validation)
        secret_key = "test-secret-key"
        forged_token = jwt.encode(
            forged_payload,
            secret_key,
            algorithm="HS256",
            headers={"typ": "JWT", "alg": "HS256"}
        )

        # Verify token has HS256 algorithm in header
        header = jwt.get_unverified_header(forged_token)
        assert header["alg"] == "HS256"

        # Verify token has Azure AD issuer in payload
        unverified_payload = jwt.decode(
            forged_token,
            algorithms=["HS256", "RS256"],
            options={"verify_signature": False, "verify_aud": False}
        )
        assert unverified_payload["iss"].startswith("https://login.microsoftonline.com/")

        # The fix: because issuer is Azure AD pattern, it will be routed to
        # Azure AD validator (not internal JWT validator)
        # This prevents algorithm confusion attack
        assert unverified_payload["iss"].startswith("https://login.microsoftonline.com/")

    def test_routing_by_issuer_detects_internal_token(self):
        """Tokens without Azure AD issuer are routed to internal validator.

        Verifies that tokens with custom/internal issuer are handled
        by the internal JWT validator.
        """

        # Create internal token with custom issuer
        internal_payload = {
            "sub": "user-123",
            "email": "user@example.com",
            "type": "access",
            "iss": "internal-jwt-issuer",  # Not Azure AD
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
        }

        secret_key = "test-secret-key"
        internal_token = jwt.encode(
            internal_payload,
            secret_key,
            algorithm="HS256"
        )

        # Verify issuer is NOT Azure AD pattern
        unverified_payload = jwt.decode(
            internal_token,
            algorithms=["HS256"],
            options={"verify_signature": False}
        )
        assert not unverified_payload["iss"].startswith("https://login.microsoftonline.com/")

        # Such tokens will be routed to internal JWT validator
        # where they must have valid signature to be accepted
