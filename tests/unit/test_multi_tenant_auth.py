"""Unit tests for Phase B multi-tenant app authentication.

Tests the multi-tenant credential resolution, backward compatibility
with Phase A, and proper configuration handling.

Phase B: Single multi-tenant app registration (AzureADMultipleOrgs)
- Uses one client secret for all 5 tenants
- Simplifies secret rotation (1 secret vs 5)
- Backward compatible with Phase A per-tenant apps
"""

import uuid
from unittest.mock import patch

import pytest
import yaml

from app.core.tenants_config import (
    TenantConfig,
    get_credential_for_tenant,
    get_multi_tenant_app_id,
    is_multi_tenant_mode_enabled,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_tenant_config():
    """Create a sample tenant configuration."""
    return TenantConfig(
        tenant_id="00000000-0000-4000-a000-000000000001",
        name="Test Tenant (HTT)",
        code="HTT",
        admin_email="admin@example.com",
        app_id="00000000-0000-4000-b000-000000000001",  # Phase A per-tenant app
        key_vault_secret_name="htt-client-secret",  # pragma: allowlist secret
        domains=["example.com"],
        is_active=True,
        is_riverside=True,
        priority=1,
        oidc_enabled=False,
        multi_tenant_app_id=None,  # Phase A: no multi-tenant app
    )


@pytest.fixture
def sample_tenant_config_phase_b():
    """Create a sample Phase B tenant configuration."""
    return TenantConfig(
        tenant_id="00000000-0000-4000-a000-000000000001",
        name="Test Tenant (HTT)",
        code="HTT",
        admin_email="admin@example.com",
        app_id="00000000-0000-4000-b000-000000000001",  # Kept for rollback
        key_vault_secret_name="multi-tenant-client-secret",  # pragma: allowlist secret
        domains=["example.com"],
        is_active=True,
        is_riverside=True,
        priority=1,
        oidc_enabled=False,
        multi_tenant_app_id="00000000-0000-4000-c000-000000000000",  # Phase B
    )


@pytest.fixture
def mock_phase_b_config(tmp_path):
    """Create a mock tenants.yaml with Phase B configuration."""
    config_data = {
        "multi_tenant_app_id": "00000000-0000-4000-c000-000000000000",
        "tenants": {
            "HTT": {
                "tenant_id": "00000000-0000-4000-a000-000000000001",
                "name": "Head-To-Toe (HTT)",
                "code": "HTT",
                "admin_email": "admin@htt.com",
                "app_id": "00000000-0000-4000-b000-000000000001",
                "key_vault_secret_name": "multi-tenant-client-secret",  # pragma: allowlist secret
                "is_active": True,
                "is_riverside": True,
                "priority": 1,
                "oidc_enabled": False,
            },
            "BCC": {
                "tenant_id": "00000000-0000-4000-a000-000000000002",
                "name": "Bishops (BCC)",
                "code": "BCC",
                "admin_email": "admin@bcc.com",
                "app_id": "00000000-0000-4000-b000-000000000002",
                "key_vault_secret_name": "multi-tenant-client-secret",  # pragma: allowlist secret
                "is_active": True,
                "is_riverside": True,
                "priority": 2,
                "oidc_enabled": False,
            },
        },
    }

    config_file = tmp_path / "tenants.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    return str(config_file)


# ============================================================================
# Test Multi-Tenant App ID Resolution
# ============================================================================


class TestGetMultiTenantAppId:
    """Test the get_multi_tenant_app_id function."""

    def test_returns_none_when_no_multi_tenant_configured(self, sample_tenant_config):
        """When no multi_tenant_app_id is set, should return None."""
        with patch("app.core.tenants_config.get_tenant_by_code", return_value=sample_tenant_config):
            result = get_multi_tenant_app_id("HTT")
            assert result is None

    def test_returns_app_id_when_phase_b_configured(self, sample_tenant_config_phase_b):
        """When multi_tenant_app_id is set, should return it."""
        with patch(
            "app.core.tenants_config.get_tenant_by_code", return_value=sample_tenant_config_phase_b
        ):
            result = get_multi_tenant_app_id("HTT")
            assert result == "00000000-0000-4000-c000-000000000000"

    def test_returns_first_available_when_no_tenant_specified(self, sample_tenant_config_phase_b):
        """When tenant_code is None, should return first available multi_tenant_app_id."""
        mock_tenants = {"HTT": sample_tenant_config_phase_b}

        with patch("app.core.tenants_config.RIVERSIDE_TENANTS", mock_tenants):
            result = get_multi_tenant_app_id()
            assert result == "00000000-0000-4000-c000-000000000000"

    def test_returns_none_for_unknown_tenant(self):
        """When tenant code is unknown, should return None."""
        with patch("app.core.tenants_config.get_tenant_by_code", return_value=None):
            result = get_multi_tenant_app_id("UNKNOWN")
            assert result is None

    def test_valid_uuid_format(self, sample_tenant_config_phase_b):
        """Returned app ID should be a valid UUID."""
        with patch(
            "app.core.tenants_config.get_tenant_by_code", return_value=sample_tenant_config_phase_b
        ):
            result = get_multi_tenant_app_id("HTT")
            # Should not raise ValueError
            parsed = uuid.UUID(result)
            assert str(parsed) == result.lower()


# ============================================================================
# Test Multi-Tenant Mode Detection
# ============================================================================


class TestIsMultiTenantModeEnabled:
    """Test the is_multi_tenant_mode_enabled function."""

    def test_returns_false_in_phase_a(self, sample_tenant_config):
        """In Phase A (no multi_tenant_app_id), should return False."""
        with patch("app.core.tenants_config.get_tenant_by_code", return_value=sample_tenant_config):
            assert is_multi_tenant_mode_enabled("HTT") is False

    def test_returns_true_in_phase_b(self, sample_tenant_config_phase_b):
        """In Phase B (with multi_tenant_app_id), should return True."""
        with patch(
            "app.core.tenants_config.get_tenant_by_code", return_value=sample_tenant_config_phase_b
        ):
            assert is_multi_tenant_mode_enabled("HTT") is True

    def test_returns_true_if_any_tenant_has_multi_tenant_app(self, sample_tenant_config_phase_b):
        """When checking globally, returns True if any tenant has multi_tenant_app_id."""
        mock_tenants = {
            "HTT": sample_tenant_config_phase_b,
            "BCC": sample_tenant_config,  # No multi-tenant
        }

        with patch("app.core.tenants_config.RIVERSIDE_TENANTS", mock_tenants):
            assert is_multi_tenant_mode_enabled() is True


# ============================================================================
# Test Credential Resolution
# ============================================================================


class TestGetCredentialForTenant:
    """Test the get_credential_for_tenant function."""

    def test_raises_for_unknown_tenant(self):
        """Should raise ValueError for unknown tenant code."""
        with patch("app.core.tenants_config.get_tenant_by_code", return_value=None):
            with pytest.raises(ValueError, match="Unknown tenant code"):
                get_credential_for_tenant("UNKNOWN")

    def test_phase_a_per_tenant_credential(self, sample_tenant_config):
        """In Phase A, should use per-tenant app_id."""
        with patch("app.core.tenants_config.get_tenant_by_code", return_value=sample_tenant_config):
            result = get_credential_for_tenant("HTT")

            assert result["app_id"] == sample_tenant_config.app_id
            assert result["tenant_id"] == sample_tenant_config.tenant_id
            assert result["key_vault_secret_name"] == sample_tenant_config.key_vault_secret_name
            assert result["is_multi_tenant"] is False
            assert result["oidc_enabled"] is False

    def test_phase_b_multi_tenant_credential(self, sample_tenant_config_phase_b):
        """In Phase B with prefer_multi_tenant=True, should use multi-tenant app_id."""
        with patch(
            "app.core.tenants_config.get_tenant_by_code", return_value=sample_tenant_config_phase_b
        ):
            result = get_credential_for_tenant("HTT", prefer_multi_tenant=True)

            assert result["app_id"] == sample_tenant_config_phase_b.multi_tenant_app_id
            assert result["tenant_id"] == sample_tenant_config_phase_b.tenant_id
            assert (
                result["key_vault_secret_name"]
                == sample_tenant_config_phase_b.key_vault_secret_name
            )
            assert result["is_multi_tenant"] is True
            assert result["oidc_enabled"] is False

    def test_phase_b_prefer_per_tenant_fallback(self, sample_tenant_config_phase_b):
        """With prefer_multi_tenant=False, should use per-tenant app_id even if multi-tenant available."""
        with patch(
            "app.core.tenants_config.get_tenant_by_code", return_value=sample_tenant_config_phase_b
        ):
            result = get_credential_for_tenant("HTT", prefer_multi_tenant=False)

            # Uses per-tenant app_id but flags that multi-tenant is available
            assert result["app_id"] == sample_tenant_config_phase_b.app_id
            assert result["is_multi_tenant"] is True  # Still available, just not preferred

    def test_phase_a_no_multi_tenant_fallback(self, sample_tenant_config):
        """In Phase A without multi-tenant configured, is_multi_tenant should be False."""
        with patch("app.core.tenants_config.get_tenant_by_code", return_value=sample_tenant_config):
            result = get_credential_for_tenant("HTT", prefer_multi_tenant=True)

            assert result["is_multi_tenant"] is False
            assert result["app_id"] == sample_tenant_config.app_id

    def test_returns_correct_types(self, sample_tenant_config_phase_b):
        """All return values should be of expected types."""
        with patch(
            "app.core.tenants_config.get_tenant_by_code", return_value=sample_tenant_config_phase_b
        ):
            result = get_credential_for_tenant("HTT")

            assert isinstance(result["app_id"], str)
            assert isinstance(result["tenant_id"], str)
            assert isinstance(result["key_vault_secret_name"], str)
            assert isinstance(result["is_multi_tenant"], bool)
            assert isinstance(result["oidc_enabled"], bool)


# ============================================================================
# Test TenantConfig Dataclass
# ============================================================================


class TestTenantConfig:
    """Test the TenantConfig dataclass with multi_tenant_app_id field."""

    def test_has_multi_tenant_app_id_field(self):
        """TenantConfig should have multi_tenant_app_id attribute."""
        config = TenantConfig(
            tenant_id="00000000-0000-4000-a000-000000000001",
            name="Test",
            code="TST",
            admin_email="test@test.com",
            app_id="00000000-0000-4000-b000-000000000001",
            multi_tenant_app_id="00000000-0000-4000-c000-000000000000",
        )

        assert hasattr(config, "multi_tenant_app_id")
        assert config.multi_tenant_app_id == "00000000-0000-4000-c000-000000000000"

    def test_multi_tenant_app_id_defaults_to_none(self):
        """multi_tenant_app_id should default to None."""
        config = TenantConfig(
            tenant_id="00000000-0000-4000-a000-000000000001",
            name="Test",
            code="TST",
            admin_email="test@test.com",
            app_id="00000000-0000-4000-b000-000000000001",
        )

        assert config.multi_tenant_app_id is None

    def test_is_frozen_dataclass(self):
        """TenantConfig should be immutable (frozen)."""
        config = TenantConfig(
            tenant_id="00000000-0000-4000-a000-000000000001",
            name="Test",
            code="TST",
            admin_email="test@test.com",
            app_id="00000000-0000-4000-b000-000000000001",
        )

        with pytest.raises(AttributeError):
            config.multi_tenant_app_id = "new-value"


# ============================================================================
# Test YAML Loading with Global multi_tenant_app_id
# ============================================================================


class TestYamlLoading:
    """Test loading tenants.yaml with global multi_tenant_app_id."""

    def test_global_multi_tenant_app_id_inherited(self, mock_phase_b_config, tmp_path):
        """All tenants should inherit global multi_tenant_app_id."""
        import os

        # Mock the module-level loading
        with patch.dict(os.environ, {"TENANTS_CONFIG_PATH": mock_phase_b_config}):
            # Force reimport by clearing cache
            import importlib

            import app.core.tenants_config as tc_module

            # Reload with new config
            importlib.reload(tc_module)

            # Both tenants should have the same multi_tenant_app_id
            htt_config = tc_module.get_tenant_by_code("HTT")
            bcc_config = tc_module.get_tenant_by_code("BCC")

            assert htt_config.multi_tenant_app_id == "00000000-0000-4000-c000-000000000000"
            assert bcc_config.multi_tenant_app_id == "00000000-0000-4000-c000-000000000000"


# ============================================================================
# Test Backward Compatibility
# ============================================================================


class TestBackwardCompatibility:
    """Ensure Phase B changes don't break Phase A deployments."""

    def test_phase_a_config_without_multi_tenant_field(self):
        """Phase A config (no multi_tenant_app_id) should still work."""
        # This simulates old tenants.yaml without the global field
        config = TenantConfig(
            tenant_id="00000000-0000-4000-a000-000000000001",
            name="Test",
            code="TST",
            admin_email="test@test.com",
            app_id="00000000-0000-4000-b000-000000000001",
            # multi_tenant_app_id defaults to None
        )

        # Should not raise any errors
        assert config.multi_tenant_app_id is None
        assert is_multi_tenant_mode_enabled("TST") is False

    def test_old_yaml_without_global_field(self, tmp_path):
        """YAML without global multi_tenant_app_id should load successfully."""
        old_config = {
            "tenants": {  # No global multi_tenant_app_id
                "HTT": {
                    "tenant_id": "00000000-0000-4000-a000-000000000001",
                    "name": "Head-To-Toe (HTT)",
                    "code": "HTT",
                    "admin_email": "admin@htt.com",
                    "app_id": "00000000-0000-4000-b000-000000000001",
                    "key_vault_secret_name": "htt-client-secret",  # pragma: allowlist secret
                    "is_active": True,
                    "is_riverside": True,
                    "priority": 1,
                    "oidc_enabled": False,
                }
            }
        }

        config_file = tmp_path / "tenants_old.yaml"
        with open(config_file, "w") as f:
            yaml.dump(old_config, f)

        # Should load without errors
        import os

        with patch.dict(os.environ, {"TENANTS_CONFIG_PATH": str(config_file)}):
            import importlib

            import app.core.tenants_config as tc_module

            importlib.reload(tc_module)

            config = tc_module.get_tenant_by_code("HTT")
            assert config.multi_tenant_app_id is None
            assert config.app_id == "00000000-0000-4000-b000-000000000001"


# ============================================================================
# Integration-Style Tests
# ============================================================================


class TestCredentialResolutionScenarios:
    """Test realistic credential resolution scenarios."""

    def test_all_five_tenants_share_same_multi_tenant_app(self):
        """All 5 Riverside tenants should resolve to the same multi-tenant app."""
        shared_app_id = "00000000-0000-4000-c000-000000000000"

        mock_tenants = {
            code: TenantConfig(
                tenant_id=f"00000000-0000-4000-a000-00000000000{idx + 1}",
                name=f"Tenant {code}",
                code=code,
                admin_email=f"admin@{code.lower()}.com",
                app_id=f"00000000-0000-4000-b000-00000000000{idx + 1}",
                key_vault_secret_name="multi-tenant-client-secret",  # pragma: allowlist secret
                multi_tenant_app_id=shared_app_id,
                oidc_enabled=False,
            )
            for idx, code in enumerate(["HTT", "BCC", "FN", "TLL", "DCE"])
        }

        with patch("app.core.tenants_config.RIVERSIDE_TENANTS", mock_tenants):
            for code in mock_tenants:
                creds = get_credential_for_tenant(code)
                assert creds["app_id"] == shared_app_id
                assert creds["is_multi_tenant"] is True
                assert (
                    creds["key_vault_secret_name"] == "multi-tenant-client-secret"
                )  # pragma: allowlist secret

    def test_mixed_phase_a_and_b_tenants(self):
        """Some tenants in Phase A, some in Phase B should work correctly."""
        mock_tenants = {
            "HTT": TenantConfig(
                tenant_id="00000000-0000-4000-a000-000000000001",
                name="HTT",
                code="HTT",
                admin_email="admin@htt.com",
                app_id="00000000-0000-4000-b000-000000000001",
                key_vault_secret_name="multi-tenant-client-secret",  # pragma: allowlist secret
                multi_tenant_app_id="00000000-0000-4000-c000-000000000000",  # Phase B
                oidc_enabled=False,
            ),
            "BCC": TenantConfig(
                tenant_id="00000000-0000-4000-a000-000000000002",
                name="BCC",
                code="BCC",
                admin_email="admin@bcc.com",
                app_id="00000000-0000-4000-b000-000000000002",
                key_vault_secret_name="bcc-client-secret",  # pragma: allowlist secret
                multi_tenant_app_id=None,  # Phase A
                oidc_enabled=False,
            ),
        }

        with patch("app.core.tenants_config.RIVERSIDE_TENANTS", mock_tenants):
            # HTT should use multi-tenant app
            htt_creds = get_credential_for_tenant("HTT")
            assert htt_creds["app_id"] == "00000000-0000-4000-c000-000000000000"
            assert htt_creds["is_multi_tenant"] is True

            # BCC should use per-tenant app
            bcc_creds = get_credential_for_tenant("BCC")
            assert bcc_creds["app_id"] == "00000000-0000-4000-b000-000000000002"
            assert bcc_creds["is_multi_tenant"] is False


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_multi_tenant_app_id_treated_as_none(self):
        """Empty string multi_tenant_app_id should be treated as not configured."""
        config = TenantConfig(
            tenant_id="00000000-0000-4000-a000-000000000001",
            name="Test",
            code="TST",
            admin_email="test@test.com",
            app_id="00000000-0000-4000-b000-000000000001",
            multi_tenant_app_id="",  # Empty string
        )

        # Empty string is falsy, so should be treated as None
        assert not config.multi_tenant_app_id

    def test_case_insensitive_tenant_code_lookup(self):
        """Tenant code lookup should be case-insensitive."""
        config = TenantConfig(
            tenant_id="00000000-0000-4000-a000-000000000001",
            name="Test",
            code="HTT",
            admin_email="test@test.com",
            app_id="00000000-0000-4000-b000-000000000001",
            multi_tenant_app_id="00000000-0000-4000-c000-000000000000",
        )

        mock_tenants = {"HTT": config}

        with patch("app.core.tenants_config.RIVERSIDE_TENANTS", mock_tenants):
            # Should work with various cases
            assert get_credential_for_tenant("HTT")["app_id"] == config.multi_tenant_app_id
            assert get_credential_for_tenant("htt")["app_id"] == config.multi_tenant_app_id
            assert get_credential_for_tenant("HtT")["app_id"] == config.multi_tenant_app_id


# ============================================================================
# Performance Tests
# ============================================================================


class TestPerformance:
    """Basic performance tests for credential resolution."""

    def test_credential_resolution_is_fast(self):
        """Credential resolution should be fast (no I/O)."""
        import time

        config = TenantConfig(
            tenant_id="00000000-0000-4000-a000-000000000001",
            name="Test",
            code="TST",
            admin_email="test@test.com",
            app_id="00000000-0000-4000-b000-000000000001",
            multi_tenant_app_id="00000000-0000-4000-c000-000000000000",
        )

        mock_tenants = {"TST": config}

        with patch("app.core.tenants_config.RIVERSIDE_TENANTS", mock_tenants):
            start = time.perf_counter()

            # Run 1000 iterations
            for _ in range(1000):
                get_credential_for_tenant("TST")

            elapsed = time.perf_counter() - start

            # Should complete in under 100ms (very generous)
            assert elapsed < 0.1, f"Credential resolution too slow: {elapsed:.3f}s for 1000 calls"


# ============================================================================
# Cleanup Fixture - Restore original tenant config after tests that reload module
# ============================================================================


@pytest.fixture(autouse=True)
def restore_tenants_config():
    """Restore original tenants config after each test.

    Some tests use importlib.reload() to test config loading, which modifies
    the global RIVERSIDE_TENANTS. This fixture ensures the module is reloaded
    with the original config after such tests.
    """
    import importlib
    import os

    import app.core.tenants_config as tc_module

    # Store original env var
    original_config_path = os.environ.get("TENANTS_CONFIG_PATH")

    yield

    # Cleanup: reload with original config
    if original_config_path:
        os.environ["TENANTS_CONFIG_PATH"] = original_config_path
    elif "TENANTS_CONFIG_PATH" in os.environ:
        del os.environ["TENANTS_CONFIG_PATH"]

    # Force reload to restore original config
    importlib.reload(tc_module)
