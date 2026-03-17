"""Shared pytest fixtures for unit tests."""

import pytest

from app.core.circuit_breaker import circuit_breaker_registry

# Import fixtures from parent conftest to make authed_client available
from tests.conftest import (  # noqa: F401
    mock_authz,
    mock_user,
    authed_client,
)


@pytest.fixture(autouse=True)
def reset_circuit_breakers():
    """Reset all circuit breakers before each test."""
    # Run before test
    circuit_breaker_registry.reset_all()
    yield
    # Reset after test as well
    circuit_breaker_registry.reset_all()
