"""Tests for tenant configuration consistency and Key Vault integration.

Validates that all 5 Riverside tenants are properly configured with valid
UUIDs, email addresses, Key Vault secret names, and correct lookup behavior.
"""

import uuid

import pytest

from app.core.tenants_config import (
    RIVERSIDE_TENANTS,
    TenantConfig,
    get_active_tenants,
    get_all_active_tenant_ids,
    get_all_tenant_ids,
    get_key_vault_secret_name,
    get_tenant_by_code,
    get_tenant_by_id,
    validate_tenant_config,
)

EXPECTED_CODES: list[str] = ["HTT", "BCC", "FN", "TLL", "DCE"]


# ---------------------------------------------------------------------------
# 1. All 5 tenants present
# ---------------------------------------------------------------------------
class TestAllTenantsPresent:
    """Ensure the RIVERSIDE_TENANTS dict contains exactly the 5 expected entries."""

    def test_exactly_five_tenants(self) -> None:
        assert len(RIVERSIDE_TENANTS) == 5

    @pytest.mark.parametrize("code", EXPECTED_CODES)
    def test_tenant_code_exists(self, code: str) -> None:
        assert code in RIVERSIDE_TENANTS, f"Missing tenant code: {code}"

    @pytest.mark.parametrize("code", EXPECTED_CODES)
    def test_tenant_is_tenant_config_instance(self, code: str) -> None:
        assert isinstance(RIVERSIDE_TENANTS[code], TenantConfig)

    @pytest.mark.parametrize("code", EXPECTED_CODES)
    def test_tenant_code_matches_dict_key(self, code: str) -> None:
        """The .code attribute must agree with the dictionary key."""
        assert RIVERSIDE_TENANTS[code].code == code


# ---------------------------------------------------------------------------
# 2. All tenant_ids and app_ids are valid UUIDs
# ---------------------------------------------------------------------------
class TestUUIDValidity:
    """Every tenant_id and app_id must parse as a valid UUID-4 string."""

    @pytest.mark.parametrize("code", EXPECTED_CODES)
    def test_tenant_id_is_valid_uuid(self, code: str) -> None:
        try:
            parsed = uuid.UUID(RIVERSIDE_TENANTS[code].tenant_id)
        except ValueError:
            pytest.fail(f"{code}: tenant_id is not a valid UUID")
        # Round-trip: lowercased canonical form must match
        assert str(parsed) == RIVERSIDE_TENANTS[code].tenant_id

    @pytest.mark.parametrize("code", EXPECTED_CODES)
    def test_app_id_is_valid_uuid(self, code: str) -> None:
        try:
            parsed = uuid.UUID(RIVERSIDE_TENANTS[code].app_id)
        except ValueError:
            pytest.fail(f"{code}: app_id is not a valid UUID")
        assert str(parsed) == RIVERSIDE_TENANTS[code].app_id


# ---------------------------------------------------------------------------
# 3. All have valid admin emails
# ---------------------------------------------------------------------------
class TestAdminEmails:
    """Every tenant must have a plausible admin email address."""

    @pytest.mark.parametrize("code", EXPECTED_CODES)
    def test_admin_email_contains_at_sign(self, code: str) -> None:
        email = RIVERSIDE_TENANTS[code].admin_email
        assert "@" in email, f"{code}: admin_email missing '@'"

    @pytest.mark.parametrize("code", EXPECTED_CODES)
    def test_admin_email_has_local_and_domain(self, code: str) -> None:
        email = RIVERSIDE_TENANTS[code].admin_email
        local, _, domain = email.partition("@")
        assert local, f"{code}: admin_email has empty local part"
        assert domain, f"{code}: admin_email has empty domain part"

    @pytest.mark.parametrize("code", EXPECTED_CODES)
    def test_admin_email_is_non_empty_string(self, code: str) -> None:
        assert isinstance(RIVERSIDE_TENANTS[code].admin_email, str)
        assert len(RIVERSIDE_TENANTS[code].admin_email) > 0


# ---------------------------------------------------------------------------
# 4. All key_vault_secret_names contain their lowercase code
# ---------------------------------------------------------------------------
class TestKeyVaultSecretNames:
    """Secret names must follow the {code-lower}-client-secret convention."""

    @pytest.mark.parametrize("code", EXPECTED_CODES)
    def test_secret_name_contains_lowercase_code(self, code: str) -> None:
        secret_name = RIVERSIDE_TENANTS[code].key_vault_secret_name
        assert code.lower() in secret_name, (
            f"{code}: key_vault_secret_name '{secret_name}' does not contain '{code.lower()}'"
        )

    @pytest.mark.parametrize("code", EXPECTED_CODES)
    def test_secret_name_follows_convention(self, code: str) -> None:
        """Expected pattern: <lowercase-code>-client-secret."""
        expected = f"{code.lower()}-client-secret"
        assert RIVERSIDE_TENANTS[code].key_vault_secret_name == expected

    @pytest.mark.parametrize("code", EXPECTED_CODES)
    def test_secret_name_is_non_empty(self, code: str) -> None:
        assert RIVERSIDE_TENANTS[code].key_vault_secret_name


# ---------------------------------------------------------------------------
# 5. No duplicate IDs
# ---------------------------------------------------------------------------
class TestNoDuplicateIDs:
    """tenant_id and app_id values must be globally unique."""

    def test_no_duplicate_tenant_ids(self) -> None:
        ids = [cfg.tenant_id for cfg in RIVERSIDE_TENANTS.values()]
        assert len(ids) == len(set(ids)), "Duplicate tenant IDs detected"

    def test_no_duplicate_app_ids(self) -> None:
        ids = [cfg.app_id for cfg in RIVERSIDE_TENANTS.values()]
        assert len(ids) == len(set(ids)), "Duplicate app IDs detected"

    def test_tenant_ids_and_app_ids_do_not_overlap(self) -> None:
        """A tenant_id should never equal any app_id."""
        tenant_ids = {cfg.tenant_id for cfg in RIVERSIDE_TENANTS.values()}
        app_ids = {cfg.app_id for cfg in RIVERSIDE_TENANTS.values()}
        overlap = tenant_ids & app_ids
        assert not overlap, f"Overlapping tenant/app IDs: {overlap}"


# ---------------------------------------------------------------------------
# 6. Lookup functions (by code, by id, case-insensitive)
# ---------------------------------------------------------------------------
class TestLookupFunctions:
    """Verify the helper lookup functions return correct results."""

    # -- by code ---------------------------------------------------------
    @pytest.mark.parametrize("code", EXPECTED_CODES)
    def test_get_tenant_by_code_uppercase(self, code: str) -> None:
        result = get_tenant_by_code(code)
        assert result is not None
        assert result.code == code

    @pytest.mark.parametrize("code", EXPECTED_CODES)
    def test_get_tenant_by_code_lowercase(self, code: str) -> None:
        """Lookup must be case-insensitive."""
        result = get_tenant_by_code(code.lower())
        assert result is not None
        assert result.code == code

    @pytest.mark.parametrize("code", EXPECTED_CODES)
    def test_get_tenant_by_code_mixedcase(self, code: str) -> None:
        mixed = code[0].lower() + code[1:].upper() if len(code) > 1 else code
        result = get_tenant_by_code(mixed)
        assert result is not None
        assert result.code == code

    def test_get_tenant_by_code_invalid_returns_none(self) -> None:
        assert get_tenant_by_code("NOPE") is None

    def test_get_tenant_by_code_empty_returns_none(self) -> None:
        assert get_tenant_by_code("") is None

    # -- by id -----------------------------------------------------------
    @pytest.mark.parametrize("code", EXPECTED_CODES)
    def test_get_tenant_by_id(self, code: str) -> None:
        tenant_id = RIVERSIDE_TENANTS[code].tenant_id
        result = get_tenant_by_id(tenant_id)
        assert result is not None
        assert result.code == code

    def test_get_tenant_by_id_invalid_returns_none(self) -> None:
        assert get_tenant_by_id("00000000-0000-0000-0000-000000000000") is None

    # -- bulk accessors --------------------------------------------------
    def test_get_active_tenants_returns_all_five(self) -> None:
        active = get_active_tenants()
        assert len(active) == 5
        assert set(active.keys()) == set(EXPECTED_CODES)

    def test_get_all_tenant_ids_count(self) -> None:
        ids = get_all_tenant_ids()
        assert len(ids) == 5

    def test_get_all_tenant_ids_are_valid_uuids(self) -> None:
        for tid in get_all_tenant_ids():
            uuid.UUID(tid)  # raises on bad format

    def test_get_all_active_tenant_ids_count(self) -> None:
        ids = get_all_active_tenant_ids()
        assert len(ids) == 5

    def test_active_tenant_ids_match_all_tenant_ids(self) -> None:
        """When every tenant is active, the two lists should match."""
        assert set(get_all_active_tenant_ids()) == set(get_all_tenant_ids())


# ---------------------------------------------------------------------------
# 7. get_key_vault_secret_name returns expected names
# ---------------------------------------------------------------------------
class TestGetKeyVaultSecretName:
    """The helper must return the correct secret name for each code."""

    @pytest.mark.parametrize(
        "code, expected",
        [
            ("HTT", "htt-client-secret"),
            ("BCC", "bcc-client-secret"),
            ("FN", "fn-client-secret"),
            ("TLL", "tll-client-secret"),
            ("DCE", "dce-client-secret"),
        ],
    )
    def test_returns_expected_secret_name(self, code: str, expected: str) -> None:
        assert get_key_vault_secret_name(code) == expected

    def test_case_insensitive_lookup(self) -> None:
        assert get_key_vault_secret_name("htt") == "htt-client-secret"

    def test_raises_on_unknown_code(self) -> None:
        with pytest.raises(ValueError, match="Unknown tenant code"):
            get_key_vault_secret_name("INVALID")


# ---------------------------------------------------------------------------
# 8. validate_tenant_config returns no issues
# ---------------------------------------------------------------------------
class TestValidateTenantConfig:
    """The built-in validator should report zero issues for current config."""

    def test_validate_returns_empty_list(self) -> None:
        issues = validate_tenant_config()
        assert issues == [], f"Validation issues found: {issues}"

    def test_validate_return_type(self) -> None:
        result = validate_tenant_config()
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# 9. All tenants are active
# ---------------------------------------------------------------------------
class TestAllTenantsActive:
    """Every Riverside tenant must currently be flagged as active."""

    @pytest.mark.parametrize("code", EXPECTED_CODES)
    def test_tenant_is_active(self, code: str) -> None:
        assert RIVERSIDE_TENANTS[code].is_active is True, f"{code} should be active"

    @pytest.mark.parametrize("code", EXPECTED_CODES)
    def test_tenant_is_riverside(self, code: str) -> None:
        assert RIVERSIDE_TENANTS[code].is_riverside is True, (
            f"{code} should be marked as Riverside-managed"
        )

    def test_active_count_equals_total(self) -> None:
        active = get_active_tenants()
        assert len(active) == len(RIVERSIDE_TENANTS)
