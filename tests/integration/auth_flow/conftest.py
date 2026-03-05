"""Shared fixtures and helpers for auth flow integration tests."""

from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from app.core.auth import _token_blacklist
from app.core.config import get_settings


def create_test_token(
    user_id: str,
    roles: list[str] | None = None,
    tenant_ids: list[str] | None = None,
    expired: bool = False,
) -> str:
    """Create a test JWT token with custom claims.

    Args:
        user_id: User ID for the token
        roles: List of user roles
        tenant_ids: List of accessible tenant IDs
        expired: Whether to create an expired token

    Returns:
        Encoded JWT token
    """
    settings = get_settings()

    if expired:
        expires_delta = timedelta(minutes=-30)  # Already expired
    else:
        expires_delta = timedelta(minutes=30)

    expire = datetime.now(UTC) + expires_delta

    to_encode = {
        "sub": user_id,
        "email": "test@example.com",
        "name": "Test User",
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
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_test_refresh_token(
    user_id: str,
    expired: bool = False,
) -> str:
    """Create a test JWT refresh token.

    Args:
        user_id: User ID for the token
        expired: Whether to create an expired token

    Returns:
        Encoded JWT refresh token
    """
    settings = get_settings()

    if expired:
        expires_delta = timedelta(days=-1)  # Already expired
    else:
        expires_delta = timedelta(days=7)

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
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


@pytest.fixture(autouse=True)
def clear_token_blacklist():
    """Clear the token blacklist before each test for isolation."""
    _token_blacklist.clear()
    yield
    _token_blacklist.clear()
