"""Tests for app.core.permissions module.

Validates permission string registry, role definitions, containment hierarchy,
legacy role mapping, and permission resolution functions.

Run: ``pytest tests/unit/test_permissions.py -v``
"""

from __future__ import annotations

from app.core.permissions import (
    ALL_PERMISSIONS,
    AUDIT_LOGS_EXPORT,
    AUDIT_LOGS_READ,
    BUDGETS_MANAGE,
    BUDGETS_READ,
    COMPLIANCE_MANAGE,
    COMPLIANCE_READ,
    COMPLIANCE_WRITE,
    COSTS_EXPORT,
    COSTS_MANAGE,
    COSTS_READ,
    DASHBOARD_READ,
    DMARC_MANAGE,
    DMARC_READ,
    IDENTITY_EXPORT,
    IDENTITY_MANAGE,
    IDENTITY_READ,
    LEGACY_ROLE_MAP,
    MONITORING_MANAGE,
    MONITORING_READ,
    PREFLIGHT_READ,
    PREFLIGHT_RUN,
    RECOMMENDATIONS_READ,
    RESOURCES_EXPORT,
    RESOURCES_MANAGE,
    RESOURCES_READ,
    RIVERSIDE_MANAGE,
    RIVERSIDE_READ,
    ROLE_PERMISSIONS,
    SYNC_MANAGE,
    SYNC_READ,
    SYNC_TRIGGER,
    SYSTEM_ADMIN,
    SYSTEM_HEALTH,
    TENANTS_MANAGE,
    TENANTS_READ,
    USERS_MANAGE,
    USERS_READ,
    WILDCARD_PERMISSION,
    Role,
    get_all_permissions,
    get_permissions_for_role,
    has_permission,
)

# ============================================================================
# Permission String Format
# ============================================================================


class TestPermissionStringFormat:
    """All permission strings must follow ``resource:action`` format."""

    def test_all_permissions_are_colon_separated(self) -> None:
        for perm in ALL_PERMISSIONS:
            parts = perm.split(":")
            assert len(parts) == 2, f"'{perm}' not in resource:action format"

    def test_all_permissions_are_lowercase(self) -> None:
        for perm in ALL_PERMISSIONS:
            assert perm == perm.lower(), f"'{perm}' must be lowercase"

    def test_registry_is_not_empty(self) -> None:
        assert len(ALL_PERMISSIONS) > 0

    def test_registry_has_at_least_30_permissions(self) -> None:
        """ADR-0011 lists ~35 permissions across all modules."""
        assert len(ALL_PERMISSIONS) >= 30, (
            f"Expected ≥30 permissions per ADR-0011, got {len(ALL_PERMISSIONS)}"
        )

    def test_wildcard_is_not_in_registry(self) -> None:
        """The wildcard '*' is not a real permission — it's a meta-marker."""
        assert WILDCARD_PERMISSION not in ALL_PERMISSIONS


# ============================================================================
# Role Definitions
# ============================================================================


class TestRoleDefinitions:
    """Role enum and role→permission mappings."""

    def test_enum_has_five_roles(self) -> None:
        # ADR-0012 added MANAGER (franchise-coach tier).
        roles = list(Role)
        assert len(roles) == 5

    def test_enum_members(self) -> None:
        assert Role.ADMIN in Role
        assert Role.TENANT_ADMIN in Role
        assert Role.MANAGER in Role  # ADR-0012
        assert Role.ANALYST in Role
        assert Role.VIEWER in Role

    def test_role_string_values(self) -> None:
        assert Role.ADMIN == "admin"
        assert Role.TENANT_ADMIN == "tenant_admin"
        assert Role.ANALYST == "analyst"
        assert Role.VIEWER == "viewer"

    def test_all_roles_have_permission_mapping(self) -> None:
        for role in Role:
            assert role in ROLE_PERMISSIONS, f"{role} missing from ROLE_PERMISSIONS"

    def test_all_permission_sets_are_frozensets(self) -> None:
        for role, perms in ROLE_PERMISSIONS.items():
            assert isinstance(perms, frozenset), (
                f"Permissions for {role} must be frozenset, got {type(perms)}"
            )


# ============================================================================
# Role Hierarchy / Containment
# ============================================================================


class TestRoleHierarchy:
    """Viewer ⊂ Analyst ⊂ TenantAdmin ⊂ Admin (wildcard)."""

    def test_viewer_is_strict_subset_of_analyst(self) -> None:
        viewer = ROLE_PERMISSIONS[Role.VIEWER]
        analyst = ROLE_PERMISSIONS[Role.ANALYST]
        assert viewer < analyst, f"Viewer not ⊂ Analyst. Extra: {viewer - analyst}"

    def test_analyst_is_strict_subset_of_tenant_admin(self) -> None:
        analyst = ROLE_PERMISSIONS[Role.ANALYST]
        tenant_admin = ROLE_PERMISSIONS[Role.TENANT_ADMIN]
        assert analyst < tenant_admin, f"Analyst not ⊂ TenantAdmin. Extra: {analyst - tenant_admin}"

    def test_admin_has_wildcard(self) -> None:
        assert WILDCARD_PERMISSION in ROLE_PERMISSIONS[Role.ADMIN]


# ============================================================================
# Viewer Permissions — Read-Only
# ============================================================================


class TestViewerPermissions:
    """Viewer: read-only — no exports, no writes, no management."""

    def test_has_all_read_permissions(self) -> None:
        viewer = ROLE_PERMISSIONS[Role.VIEWER]
        expected_reads = {
            DASHBOARD_READ,
            COSTS_READ,
            COMPLIANCE_READ,
            RESOURCES_READ,
            IDENTITY_READ,
            AUDIT_LOGS_READ,
            SYNC_READ,
            TENANTS_READ,
            USERS_READ,
            RIVERSIDE_READ,
            DMARC_READ,
            PREFLIGHT_READ,
            BUDGETS_READ,
            RECOMMENDATIONS_READ,
            MONITORING_READ,
        }
        assert expected_reads.issubset(viewer)

    def test_has_no_write_actions(self) -> None:
        viewer = ROLE_PERMISSIONS[Role.VIEWER]
        write_actions = {"write", "manage", "trigger", "run", "export", "admin"}
        violations = {p for p in viewer if p.split(":")[-1] in write_actions}
        assert not violations, f"Viewer has non-read permissions: {violations}"

    def test_cannot_export(self) -> None:
        viewer = ROLE_PERMISSIONS[Role.VIEWER]
        assert COSTS_EXPORT not in viewer
        assert RESOURCES_EXPORT not in viewer
        assert IDENTITY_EXPORT not in viewer
        assert AUDIT_LOGS_EXPORT not in viewer

    def test_cannot_manage(self) -> None:
        viewer = ROLE_PERMISSIONS[Role.VIEWER]
        assert COSTS_MANAGE not in viewer
        assert COMPLIANCE_MANAGE not in viewer
        assert RESOURCES_MANAGE not in viewer


# ============================================================================
# Analyst Permissions — Read + Export
# ============================================================================


class TestAnalystPermissions:
    """Analyst: Viewer + export capabilities."""

    def test_inherits_all_viewer_permissions(self) -> None:
        viewer = ROLE_PERMISSIONS[Role.VIEWER]
        analyst = ROLE_PERMISSIONS[Role.ANALYST]
        assert viewer.issubset(analyst)

    def test_can_export(self) -> None:
        analyst = ROLE_PERMISSIONS[Role.ANALYST]
        assert COSTS_EXPORT in analyst
        assert RESOURCES_EXPORT in analyst
        assert IDENTITY_EXPORT in analyst
        assert AUDIT_LOGS_EXPORT in analyst

    def test_cannot_manage(self) -> None:
        analyst = ROLE_PERMISSIONS[Role.ANALYST]
        assert COSTS_MANAGE not in analyst
        assert COMPLIANCE_MANAGE not in analyst
        assert SYNC_TRIGGER not in analyst
        assert SYNC_MANAGE not in analyst


# ============================================================================
# Tenant Admin Permissions — Full Module Access (minus system/tenant mgmt)
# ============================================================================


class TestTenantAdminPermissions:
    """TenantAdmin: Analyst + manage/write/trigger/run (except system:admin, tenants:manage)."""

    def test_inherits_all_analyst_permissions(self) -> None:
        analyst = ROLE_PERMISSIONS[Role.ANALYST]
        tenant_admin = ROLE_PERMISSIONS[Role.TENANT_ADMIN]
        assert analyst.issubset(tenant_admin)

    def test_can_manage_modules(self) -> None:
        ta = ROLE_PERMISSIONS[Role.TENANT_ADMIN]
        assert COSTS_MANAGE in ta
        assert COMPLIANCE_MANAGE in ta
        assert RESOURCES_MANAGE in ta
        assert IDENTITY_MANAGE in ta
        assert USERS_MANAGE in ta
        assert RIVERSIDE_MANAGE in ta
        assert DMARC_MANAGE in ta
        assert BUDGETS_MANAGE in ta
        assert MONITORING_MANAGE in ta

    def test_can_write_compliance(self) -> None:
        ta = ROLE_PERMISSIONS[Role.TENANT_ADMIN]
        assert COMPLIANCE_WRITE in ta

    def test_can_trigger_sync(self) -> None:
        ta = ROLE_PERMISSIONS[Role.TENANT_ADMIN]
        assert SYNC_TRIGGER in ta
        assert SYNC_MANAGE in ta

    def test_can_run_preflight(self) -> None:
        ta = ROLE_PERMISSIONS[Role.TENANT_ADMIN]
        assert PREFLIGHT_RUN in ta

    def test_has_system_health(self) -> None:
        ta = ROLE_PERMISSIONS[Role.TENANT_ADMIN]
        assert SYSTEM_HEALTH in ta

    def test_cannot_access_system_admin(self) -> None:
        ta = ROLE_PERMISSIONS[Role.TENANT_ADMIN]
        assert SYSTEM_ADMIN not in ta

    def test_cannot_manage_tenants(self) -> None:
        ta = ROLE_PERMISSIONS[Role.TENANT_ADMIN]
        assert TENANTS_MANAGE not in ta


# ============================================================================
# Admin — Wildcard
# ============================================================================


class TestAdminPermissions:
    """Admin: wildcard '*' grants all permissions."""

    def test_has_wildcard(self) -> None:
        admin = ROLE_PERMISSIONS[Role.ADMIN]
        assert WILDCARD_PERMISSION in admin

    def test_wildcard_set_is_minimal(self) -> None:
        """Admin set should only contain the wildcard marker — not all perms."""
        admin = ROLE_PERMISSIONS[Role.ADMIN]
        assert admin == frozenset({WILDCARD_PERMISSION})


# ============================================================================
# Legacy Role Mapping
# ============================================================================


class TestLegacyRoleMapping:
    """Legacy roles map to new roles for backward compatibility."""

    def test_admin_maps_to_admin(self) -> None:
        assert LEGACY_ROLE_MAP["admin"] == "admin"

    def test_operator_maps_to_tenant_admin(self) -> None:
        assert LEGACY_ROLE_MAP["operator"] == "tenant_admin"

    def test_reader_maps_to_viewer(self) -> None:
        assert LEGACY_ROLE_MAP["reader"] == "viewer"

    def test_user_maps_to_viewer(self) -> None:
        assert LEGACY_ROLE_MAP["user"] == "viewer"

    def test_all_legacy_roles_resolve_to_valid_roles(self) -> None:
        for legacy, new in LEGACY_ROLE_MAP.items():
            assert new in [r.value for r in Role], (
                f"Legacy '{legacy}' maps to '{new}' which is not a valid Role"
            )


# ============================================================================
# get_permissions_for_role()
# ============================================================================


class TestGetPermissionsForRole:
    """Single-role permission resolution."""

    def test_known_role_returns_permissions(self) -> None:
        perms = get_permissions_for_role("viewer")
        assert COSTS_READ in perms
        assert DASHBOARD_READ in perms

    def test_legacy_role_resolves(self) -> None:
        perms = get_permissions_for_role("operator")
        expected = ROLE_PERMISSIONS[Role.TENANT_ADMIN]
        assert perms == expected

    def test_unknown_role_returns_empty_frozenset(self) -> None:
        perms = get_permissions_for_role("nonexistent_role")
        assert perms == frozenset()
        assert isinstance(perms, frozenset)

    def test_admin_returns_wildcard(self) -> None:
        perms = get_permissions_for_role("admin")
        assert WILDCARD_PERMISSION in perms

    def test_reader_resolves_to_viewer_perms(self) -> None:
        reader = get_permissions_for_role("reader")
        viewer = get_permissions_for_role("viewer")
        assert reader == viewer

    def test_user_resolves_to_viewer_perms(self) -> None:
        user_perms = get_permissions_for_role("user")
        viewer = get_permissions_for_role("viewer")
        assert user_perms == viewer


# ============================================================================
# get_all_permissions()
# ============================================================================


class TestGetAllPermissions:
    """Multi-role permission accumulation."""

    def test_single_role(self) -> None:
        perms = get_all_permissions(["viewer"])
        assert perms == ROLE_PERMISSIONS[Role.VIEWER]

    def test_multiple_roles_accumulate(self) -> None:
        perms = get_all_permissions(["viewer", "analyst"])
        assert COSTS_READ in perms  # from viewer
        assert COSTS_EXPORT in perms  # from analyst

    def test_empty_roles_returns_empty(self) -> None:
        perms = get_all_permissions([])
        assert perms == frozenset()

    def test_unknown_role_ignored(self) -> None:
        perms = get_all_permissions(["viewer", "unknown_role"])
        assert perms == ROLE_PERMISSIONS[Role.VIEWER]

    def test_legacy_roles_resolve(self) -> None:
        perms = get_all_permissions(["reader"])
        assert perms == ROLE_PERMISSIONS[Role.VIEWER]

    def test_duplicate_roles_idempotent(self) -> None:
        single = get_all_permissions(["viewer"])
        double = get_all_permissions(["viewer", "viewer"])
        assert single == double

    def test_returns_frozenset(self) -> None:
        perms = get_all_permissions(["viewer"])
        assert isinstance(perms, frozenset)


# ============================================================================
# has_permission()
# ============================================================================


class TestHasPermission:
    """Permission checking against role sets."""

    def test_viewer_has_read(self) -> None:
        assert has_permission(["viewer"], "costs:read") is True

    def test_viewer_lacks_export(self) -> None:
        assert has_permission(["viewer"], "costs:export") is False

    def test_analyst_has_export(self) -> None:
        assert has_permission(["analyst"], "costs:export") is True

    def test_admin_has_everything(self) -> None:
        assert has_permission(["admin"], "costs:read") is True
        assert has_permission(["admin"], "system:admin") is True
        assert has_permission(["admin"], "tenants:manage") is True
        # Even an arbitrary string passes because admin has wildcard
        assert has_permission(["admin"], "anything:anything") is True

    def test_unknown_role_has_nothing(self) -> None:
        assert has_permission(["fake_role"], "costs:read") is False

    def test_empty_roles_has_nothing(self) -> None:
        assert has_permission([], "costs:read") is False

    def test_legacy_operator_has_manage(self) -> None:
        assert has_permission(["operator"], "costs:manage") is True

    def test_legacy_reader_has_read(self) -> None:
        assert has_permission(["reader"], "costs:read") is True
        assert has_permission(["reader"], "costs:export") is False

    def test_multiple_roles_combine(self) -> None:
        # viewer alone can't export, but analyst can
        assert has_permission(["viewer"], "costs:export") is False
        assert has_permission(["viewer", "analyst"], "costs:export") is True

    def test_tenant_admin_lacks_system_admin(self) -> None:
        assert has_permission(["tenant_admin"], "system:admin") is False
        assert has_permission(["tenant_admin"], "tenants:manage") is False
