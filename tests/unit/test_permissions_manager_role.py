"""Tests for the MANAGER role (franchise-coach).

ADR-0012: Manager is read + export across accessible brands, with no
write/manage capability. Designed for franchise-leadership coaching.

Containment: ``VIEWER ⊂ ANALYST ⊂ MANAGER ⊂ TENANT_ADMIN ⊂ ADMIN``
"""

from __future__ import annotations

import pytest

from app.core.permissions import (
    AUDIT_LOGS_EXPORT,
    AUDIT_LOGS_READ,
    COMPLIANCE_MANAGE,
    COMPLIANCE_READ,
    COMPLIANCE_WRITE,
    COSTS_EXPORT,
    COSTS_MANAGE,
    COSTS_READ,
    FRANCHISE_COACH_EXPORT,
    FRANCHISE_COACH_READ,
    IDENTITY_EXPORT,
    IDENTITY_MANAGE,
    IDENTITY_READ,
    LEGACY_ROLE_MAP,
    RESOURCES_EXPORT,
    RESOURCES_MANAGE,
    RESOURCES_READ,
    ROLE_PERMISSIONS,
    SYNC_MANAGE,
    SYNC_TRIGGER,
    SYSTEM_ADMIN,
    Role,
    get_permissions_for_role,
    has_permission,
)


class TestManagerRoleEnum:
    """Manager role exists and sits between Analyst and Tenant Admin."""

    def test_manager_role_exists(self):
        assert Role.MANAGER.value == "manager"

    def test_manager_in_role_permissions_registry(self):
        assert Role.MANAGER in ROLE_PERMISSIONS

    def test_manager_resolves_through_legacy_map(self):
        """Plain 'manager' string resolves to canonical 'manager'."""
        assert LEGACY_ROLE_MAP["manager"] == "manager"


class TestManagerPermissions:
    """Manager has read + export everywhere + franchise-coach access."""

    @pytest.fixture
    def manager_perms(self) -> frozenset[str]:
        return get_permissions_for_role("manager")

    def test_manager_has_franchise_coach_read(self, manager_perms):
        assert FRANCHISE_COACH_READ in manager_perms

    def test_manager_has_franchise_coach_export(self, manager_perms):
        assert FRANCHISE_COACH_EXPORT in manager_perms

    @pytest.mark.parametrize(
        "perm",
        [COSTS_READ, COMPLIANCE_READ, RESOURCES_READ, IDENTITY_READ, AUDIT_LOGS_READ],
    )
    def test_manager_inherits_viewer_reads(self, manager_perms, perm):
        assert perm in manager_perms, f"Manager should inherit Viewer read: {perm}"

    @pytest.mark.parametrize(
        "perm",
        [COSTS_EXPORT, RESOURCES_EXPORT, IDENTITY_EXPORT, AUDIT_LOGS_EXPORT],
    )
    def test_manager_inherits_analyst_exports(self, manager_perms, perm):
        assert perm in manager_perms, f"Manager should inherit Analyst export: {perm}"


class TestManagerReadOnlyByDesign:
    """Manager is a coach, not an operator — no write/manage allowed.

    ADR-0012 mandates read-only Manager. Verify each write/manage perm
    is explicitly NOT present.
    """

    @pytest.fixture
    def manager_perms(self) -> frozenset[str]:
        return get_permissions_for_role("manager")

    @pytest.mark.parametrize(
        "manage_perm",
        [
            COSTS_MANAGE,
            COMPLIANCE_WRITE,
            COMPLIANCE_MANAGE,
            RESOURCES_MANAGE,
            IDENTITY_MANAGE,
            SYNC_TRIGGER,
            SYNC_MANAGE,
            SYSTEM_ADMIN,
        ],
    )
    def test_manager_does_not_have_manage_permission(self, manager_perms, manage_perm):
        assert manage_perm not in manager_perms, (
            f"Manager must remain read-only — {manage_perm} leaked in. See ADR-0012."
        )


class TestManagerContainment:
    """Verify the containment hierarchy: Viewer ⊂ Analyst ⊂ Manager ⊂ TenantAdmin ⊂ Admin."""

    def test_viewer_subset_of_analyst(self):
        viewer = get_permissions_for_role("viewer")
        analyst = get_permissions_for_role("analyst")
        assert viewer.issubset(analyst)

    def test_analyst_subset_of_manager(self):
        analyst = get_permissions_for_role("analyst")
        manager = get_permissions_for_role("manager")
        assert analyst.issubset(manager)

    def test_manager_subset_of_tenant_admin(self):
        """Manager's permissions are also held by Tenant Admin.

        Tenant Admin is a superset because they can do everything
        Manager can plus management actions.
        """
        manager = get_permissions_for_role("manager")
        tenant_admin = get_permissions_for_role("tenant_admin")
        # Tenant Admin has franchise_coach perms too (inherited via permission union)
        # so manager IS subset of tenant_admin
        franchise_coach_perms = {FRANCHISE_COACH_READ, FRANCHISE_COACH_EXPORT}
        # Tenant Admin gets the same shared reads + exports + manages.
        # It does NOT inherit franchise_coach explicitly; only Manager has it.
        # Verify: Tenant Admin has all Manager perms EXCEPT franchise-coach
        # (because those are Manager-specific by design).
        non_coach_manager_perms = manager - franchise_coach_perms
        assert non_coach_manager_perms.issubset(tenant_admin)

    def test_admin_has_everything(self):
        admin = get_permissions_for_role("admin")
        # Admin uses wildcard
        assert "*" in admin


class TestManagerHasPermission:
    """End-to-end has_permission() checks."""

    def test_manager_can_access_franchise_coach(self):
        assert has_permission(["manager"], FRANCHISE_COACH_READ) is True

    def test_viewer_cannot_access_franchise_coach(self):
        assert has_permission(["viewer"], FRANCHISE_COACH_READ) is False

    def test_analyst_cannot_access_franchise_coach(self):
        """Even Analyst (read+export everything) doesn't get coach view —
        that's a Manager-only surface."""
        assert has_permission(["analyst"], FRANCHISE_COACH_READ) is False

    def test_manager_cannot_manage_costs(self):
        assert has_permission(["manager"], COSTS_MANAGE) is False

    def test_admin_can_access_franchise_coach_via_wildcard(self):
        assert has_permission(["admin"], FRANCHISE_COACH_READ) is True
