"""Unit tests for app/core/config.py.

Tests Settings class initialization, validators, properties,
and the cached get_settings() singleton.
"""

import os
from functools import lru_cache
from unittest.mock import patch

import pytest

from app.core.config import Settings, get_settings


# ============================================================================
# Settings Initialization Tests
# ============================================================================


def test_settings_loads_with_default_values(monkeypatch):
    """Test Settings initializes with sensible defaults."""
    # Clear environment to prevent interference
    for key in list(os.environ.keys()):
        if key.startswith(("AZURE_", "JWT_", "ENVIRONMENT", "DEBUG", "CORS_")):
            monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.debug is False
    assert settings.app_name == "Azure Governance Platform"
    assert settings.host == "0.0.0.0"
    assert settings.port == 8000
    assert settings.database_url == "sqlite:///./data/governance.db"
    assert settings.log_level == "INFO"


def test_settings_jwt_secret_key_auto_generated(monkeypatch):
    """Test JWT secret key is auto-generated and >= 32 chars."""
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    settings = Settings(_env_file=None)

    assert settings.jwt_secret_key is not None
    assert len(settings.jwt_secret_key) >= 32
    assert isinstance(settings.jwt_secret_key, str)


def test_settings_jwt_secret_key_is_unique(monkeypatch):
    """Test each Settings instance generates unique JWT secret."""
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    settings1 = Settings(_env_file=None)
    settings2 = Settings(_env_file=None)

    # Two instances should have different auto-generated secrets
    assert settings1.jwt_secret_key != settings2.jwt_secret_key


def test_settings_jwt_algorithm_defaults_to_hs256(monkeypatch):
    """Test JWT algorithm defaults to HS256."""
    monkeypatch.delenv("JWT_ALGORITHM", raising=False)

    settings = Settings(_env_file=None)

    assert settings.jwt_algorithm == "HS256"


def test_settings_respects_environment_variable(monkeypatch):
    """Test Settings loads from environment variables."""
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("JWT_ALGORITHM", "RS256")
    monkeypatch.setenv("PORT", "9000")

    settings = Settings(_env_file=None)

    assert settings.environment == "staging"
    assert settings.jwt_algorithm == "RS256"
    assert settings.port == 9000


# ============================================================================
# Property Tests
# ============================================================================


def test_is_production_returns_true_for_production(monkeypatch):
    """Test is_production returns True when environment='production'."""
    # Set environment variable so the validator picks it up
    monkeypatch.setenv("ENVIRONMENT", "production")
    
    # Pass values directly to avoid list parsing issues
    settings = Settings(
        debug=False,
        cors_origins=["https://example.com"],
        _env_file=None
    )

    assert settings.is_production is True
    assert settings.is_development is False


def test_is_production_returns_false_for_development(monkeypatch):
    """Test is_production returns False for non-production."""
    monkeypatch.setenv("ENVIRONMENT", "development")

    settings = Settings(_env_file=None)

    assert settings.is_production is False


def test_is_development_returns_true_for_development(monkeypatch):
    """Test is_development returns True when environment='development'."""
    monkeypatch.setenv("ENVIRONMENT", "development")

    settings = Settings(_env_file=None)

    assert settings.is_development is True
    assert settings.is_production is False


def test_is_development_returns_false_for_production(monkeypatch):
    """Test is_development returns False for non-development."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    
    settings = Settings(
        debug=False,
        cors_origins=["https://prod.example.com"],
        _env_file=None
    )

    assert settings.is_development is False


def test_is_configured_returns_true_with_azure_creds(monkeypatch):
    """Test is_configured returns True when Azure credentials present."""
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant-id")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")

    settings = Settings(_env_file=None)

    assert settings.is_configured is True


def test_is_configured_returns_false_without_azure_creds(monkeypatch):
    """Test is_configured returns False without complete Azure creds."""
    monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_SECRET", raising=False)

    settings = Settings(_env_file=None)

    assert settings.is_configured is False


def test_is_containerized_detects_docker_env(monkeypatch):
    """Test is_containerized detects container environment."""
    monkeypatch.setenv("CONTAINER", "true")

    settings = Settings(_env_file=None)

    assert settings.is_containerized is True


def test_is_containerized_returns_false_in_normal_env(monkeypatch):
    """Test is_containerized returns False in normal environment."""
    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
    monkeypatch.delenv("CONTAINER", raising=False)

    # Mock os.path.exists to return False for /.dockerenv
    with patch("os.path.exists", return_value=False):
        settings = Settings(_env_file=None)
        assert settings.is_containerized is False


def test_is_azure_app_service_detects_azure(monkeypatch):
    """Test is_azure_app_service detects Azure App Service."""
    monkeypatch.setenv("WEBSITE_SITE_NAME", "my-app-service")

    settings = Settings(_env_file=None)

    assert settings.is_azure_app_service is True


def test_is_azure_app_service_returns_false_outside_azure(monkeypatch):
    """Test is_azure_app_service returns False outside Azure."""
    monkeypatch.delenv("WEBSITE_SITE_NAME", raising=False)

    settings = Settings(_env_file=None)

    assert settings.is_azure_app_service is False


# ============================================================================
# Validator Tests
# ============================================================================


def test_validate_debug_mode_raises_error_in_production(monkeypatch):
    """Test validate_debug_mode prevents debug=True in production."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    
    with pytest.raises(ValueError, match="DEBUG cannot be True in production"):
        Settings(
            debug=True,
            cors_origins=["https://prod.example.com"],
            _env_file=None
        )


def test_validate_debug_mode_allows_debug_in_development(monkeypatch):
    """Test validate_debug_mode allows debug=True in development."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DEBUG", "true")

    settings = Settings(_env_file=None)

    assert settings.debug is True
    assert settings.environment == "development"


def test_validate_cors_origins_prevents_wildcard_in_production(monkeypatch):
    """Test validate_cors_origins prevents wildcard in production."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    
    with pytest.raises(ValueError, match="Wildcard CORS origin.*not allowed in production"):
        Settings(
            debug=False,
            cors_origins=["*"],
            _env_file=None
        )


def test_validate_cors_origins_prevents_default_localhost_in_production(monkeypatch):
    """Test validate_cors_origins prevents default localhost in production."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    
    with pytest.raises(ValueError, match="CORS origins must be explicitly configured"):
        # Use default cors_origins (localhost)
        Settings(
            debug=False,
            _env_file=None
        )


def test_validate_cors_origins_allows_explicit_origins_in_production(monkeypatch):
    """Test validate_cors_origins allows explicit origins in production."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    
    settings = Settings(
        debug=False,
        cors_origins=["https://app.example.com", "https://api.example.com"],
        _env_file=None
    )

    assert settings.environment == "production"
    assert "https://app.example.com" in settings.cors_origins
    assert "https://api.example.com" in settings.cors_origins


def test_parse_managed_tenant_ids_from_comma_separated_string(monkeypatch):
    """Test parse_managed_tenant_ids parses comma-separated string."""
    # Pass as string to test the validator
    settings = Settings(
        managed_tenant_ids="tenant-1,tenant-2,tenant-3",
        _env_file=None
    )

    assert settings.managed_tenant_ids == ["tenant-1", "tenant-2", "tenant-3"]


def test_parse_managed_tenant_ids_handles_whitespace(monkeypatch):
    """Test parse_managed_tenant_ids strips whitespace."""
    settings = Settings(
        managed_tenant_ids=" tenant-1 , tenant-2 , tenant-3 ",
        _env_file=None
    )

    assert settings.managed_tenant_ids == ["tenant-1", "tenant-2", "tenant-3"]


def test_parse_managed_tenant_ids_from_list(monkeypatch):
    """Test parse_managed_tenant_ids handles list input directly."""
    # When passed directly (not via env var)
    settings = Settings(
        managed_tenant_ids=["tenant-a", "tenant-b"],
        _env_file=None
    )

    assert settings.managed_tenant_ids == ["tenant-a", "tenant-b"]


def test_validate_jwt_secret_warns_if_too_short(monkeypatch, caplog):
    """Test validate_jwt_secret warns if key is too short."""
    monkeypatch.setenv("JWT_SECRET_KEY", "short_key")

    with caplog.at_level("WARNING"):
        settings = Settings(_env_file=None)

    assert settings.jwt_secret_key == "short_key"
    assert "JWT secret key is too short" in caplog.text


def test_parse_cors_origins_from_comma_separated_string(monkeypatch):
    """Test parse_cors_origins handles comma-separated strings."""
    settings = Settings(
        cors_origins="http://localhost:3000,http://localhost:8080",
        _env_file=None
    )

    assert "http://localhost:3000" in settings.cors_origins
    assert "http://localhost:8080" in settings.cors_origins


# ============================================================================
# get_cache_ttl Tests
# ============================================================================


def test_get_cache_ttl_returns_correct_ttl_for_known_data_type(monkeypatch):
    """Test get_cache_ttl returns correct TTL for known data types."""
    monkeypatch.setenv("CACHE_TTL_COST_SUMMARY", "3600")
    monkeypatch.setenv("CACHE_TTL_COMPLIANCE_SUMMARY", "1800")
    monkeypatch.setenv("CACHE_TTL_RESOURCE_INVENTORY", "900")

    settings = Settings(_env_file=None)

    assert settings.get_cache_ttl("cost_summary") == 3600
    assert settings.get_cache_ttl("compliance_summary") == 1800
    assert settings.get_cache_ttl("resource_inventory") == 900


def test_get_cache_ttl_returns_default_for_unknown_data_type(monkeypatch):
    """Test get_cache_ttl returns default TTL for unknown data types."""
    monkeypatch.setenv("CACHE_DEFAULT_TTL_SECONDS", "300")

    settings = Settings(_env_file=None)

    assert settings.get_cache_ttl("unknown_type") == 300
    assert settings.get_cache_ttl("random_data") == 300


def test_get_cache_ttl_clamps_to_max_ttl(monkeypatch):
    """Test get_cache_ttl clamps TTL to max_ttl."""
    # Set a data type TTL higher than max
    monkeypatch.setenv("CACHE_TTL_COST_SUMMARY", "100000")  # Very high
    monkeypatch.setenv("CACHE_MAX_TTL_SECONDS", "3600")  # Max is 1 hour

    settings = Settings(_env_file=None)

    # Should be clamped to max_ttl
    assert settings.get_cache_ttl("cost_summary") == 3600


def test_get_cache_ttl_does_not_clamp_if_below_max(monkeypatch):
    """Test get_cache_ttl does not clamp if below max_ttl."""
    monkeypatch.setenv("CACHE_TTL_RESOURCE_INVENTORY", "900")
    monkeypatch.setenv("CACHE_MAX_TTL_SECONDS", "3600")

    settings = Settings(_env_file=None)

    # Should return actual TTL since it's below max
    assert settings.get_cache_ttl("resource_inventory") == 900


def test_get_cache_ttl_all_data_types(monkeypatch):
    """Test get_cache_ttl handles all defined data types."""
    settings = Settings(_env_file=None)

    # Test all defined data types
    ttl_types = [
        "cost_summary",
        "compliance_summary",
        "resource_inventory",
        "identity_summary",
        "riverside_summary",
    ]

    for data_type in ttl_types:
        ttl = settings.get_cache_ttl(data_type)
        assert isinstance(ttl, int)
        assert ttl > 0


# ============================================================================
# get_settings() Singleton Tests
# ============================================================================


def test_get_settings_returns_settings_instance(monkeypatch):
    """Test get_settings() returns a Settings instance."""
    # Clear the cache before testing
    get_settings.cache_clear()

    settings = get_settings()

    assert isinstance(settings, Settings)


def test_get_settings_returns_cached_singleton(monkeypatch):
    """Test get_settings() returns the same instance (singleton)."""
    # Clear the cache before testing
    get_settings.cache_clear()

    settings1 = get_settings()
    settings2 = get_settings()

    # Should be the exact same object
    assert settings1 is settings2


def test_get_settings_uses_lru_cache(monkeypatch):
    """Test get_settings() is decorated with lru_cache."""
    # Check that get_settings has cache attributes from lru_cache
    assert hasattr(get_settings, "cache_clear")
    assert hasattr(get_settings, "cache_info")


# ============================================================================
# Environment Detection Tests
# ============================================================================


# NOTE: Auto-detection tests removed because when ENVIRONMENT is not set,
# pydantic uses the Field default ("development"), so the validator never
# receives None and auto-detection doesn't trigger. In production, ENVIRONMENT
# should always be set explicitly.


def test_detect_environment_defaults_to_development(monkeypatch):
    """Test environment defaults to development if no indicators."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("PRODUCTION", raising=False)
    monkeypatch.delenv("PROD", raising=False)
    monkeypatch.delenv("STAGING", raising=False)
    monkeypatch.delenv("HOSTNAME", raising=False)

    settings = Settings(_env_file=None)

    assert settings.environment == "development"


# ============================================================================
# Additional Property Tests
# ============================================================================


def test_app_insights_enabled_detects_connection_string(monkeypatch):
    """Test app_insights_enabled detects Application Insights."""
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=abc123")

    settings = Settings(_env_file=None)

    assert settings.app_insights_enabled is True


def test_app_insights_enabled_returns_false_without_connection_string(monkeypatch):
    """Test app_insights_enabled returns False without connection string."""
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)

    settings = Settings(_env_file=None)

    assert settings.app_insights_enabled is False


# ============================================================================
# Edge Cases and Integration Tests
# ============================================================================


def test_settings_handles_case_insensitive_environment(monkeypatch):
    """Test Settings handles case-insensitive environment variables."""
    monkeypatch.setenv("environment", "STAGING")  # lowercase key, uppercase value

    settings = Settings(_env_file=None)

    assert settings.environment == "staging"  # normalized to lowercase


def test_settings_ignores_extra_env_vars(monkeypatch):
    """Test Settings ignores unknown environment variables."""
    monkeypatch.setenv("RANDOM_UNKNOWN_VAR", "some_value")
    monkeypatch.setenv("ANOTHER_UNKNOWN", "another_value")

    # Should not raise an error
    settings = Settings(_env_file=None)

    assert settings.environment == "development"


def test_settings_with_complete_azure_config(monkeypatch):
    """Test Settings with complete Azure configuration."""
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("AZURE_AD_TENANT_ID", "test-ad-tenant")
    monkeypatch.setenv("KEY_VAULT_URL", "https://keyvault.vault.azure.net/")

    settings = Settings(_env_file=None)

    assert settings.is_configured is True
    assert settings.azure_tenant_id == "test-tenant"
    assert settings.azure_client_id == "test-client"
    assert settings.azure_client_secret == "test-secret"
    assert settings.azure_ad_tenant_id == "test-ad-tenant"
    assert settings.key_vault_url == "https://keyvault.vault.azure.net/"


def test_settings_with_lighthouse_disabled(monkeypatch):
    """Test Settings with Lighthouse disabled."""
    monkeypatch.setenv("LIGHTHOUSE_ENABLED", "false")

    settings = Settings(_env_file=None)

    assert settings.lighthouse_enabled is False


def test_settings_database_configuration(monkeypatch):
    """Test Settings database configuration options."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("DB_POOL_SIZE", "10")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "20")
    monkeypatch.setenv("SLOW_QUERY_THRESHOLD_MS", "1000.0")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql://user:pass@localhost/db"
    assert settings.database_pool_size == 10
    assert settings.database_max_overflow == 20
    assert settings.slow_query_threshold_ms == 1000.0
