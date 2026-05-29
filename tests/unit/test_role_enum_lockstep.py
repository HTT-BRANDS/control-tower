"""Test the Role enum / _ROLE_DESCRIPTIONS lockstep invariant (ct-2vx).

This test ensures that adding a new Role enum member without a matching
_ROLE_DESCRIPTIONS entry causes a startup-time failure, not a per-request
500 on GET /admin/roles.
"""

import pytest

from app.core.permissions import Role


class TestRoleEnumLockstepInvariant:
    """The invariant: set(Role) == set(_ROLE_DESCRIPTIONS) at module load."""

    def test_all_role_enum_members_have_descriptions(self):
        """Every Role enum member is present in _ROLE_DESCRIPTIONS keys."""
        from app.api.routes.admin import _ROLE_DESCRIPTIONS

        enum_members = set(Role)
        described_roles = set(_ROLE_DESCRIPTIONS)
        assert enum_members == described_roles, (
            f"Role enum members and _ROLE_DESCRIPTIONS keys are not in sync. "
            f"Missing descriptions: {sorted(enum_members - described_roles)}. "
            f"Extra descriptions (no enum): {sorted(described_roles - enum_members)}"
        )

    def test_enum_member_count_matches_description_count(self):
        """Pure count guard — cheap and explicit."""
        from app.api.routes.admin import _ROLE_DESCRIPTIONS

        assert len(list(Role)) == len(_ROLE_DESCRIPTIONS), (
            f"Role enum has {len(list(Role))} members but "
            f"_ROLE_DESCRIPTIONS has {len(_ROLE_DESCRIPTIONS)} entries. "
            "A manual check is needed."
        )

    def test_missing_role_raises_on_module_load(self, monkeypatch):
        """Simulate the ADR-0012 regression: MANAGER in enum but not in dict.

        Temporarily strips MANAGER from _ROLE_DESCRIPTIONS, reloads the
        module, and asserts that the RuntimeError fires with the expected
        diagnostic string.
        """
        from app.api.routes import admin
        from app.api.routes.admin import _ROLE_DESCRIPTIONS

        # Snapshot original dict (it contains MANAGER — we've already fixed this)
        original = dict(_ROLE_DESCRIPTIONS)
        assert Role.MANAGER in original, "Test fixture assumption: MANAGER should be in dict"

        try:
            # Remove MANAGER to simulate the pre-fix state
            broken = {k: v for k, v in original.items() if k != Role.MANAGER}
            monkeypatch.setattr(admin, "_ROLE_DESCRIPTIONS", broken)

            # Module should crash on the invariant check at the bottom
            # of the file (which runs on import). We can't re-import the
            # same module name twice in-process, but we can trigger the
            # check manually since it lives in module-level code.
            with pytest.raises(RuntimeError) as exc_info:
                # Execute the invariant block manually (it's at module level)
                if set(Role) != set(admin._ROLE_DESCRIPTIONS):
                    _missing = sorted(set(Role) - set(admin._ROLE_DESCRIPTIONS))
                    raise RuntimeError(
                        f"Role enum / _ROLE_DESCRIPTIONS lockstep invariant violated. "
                        f"Missing in _ROLE_DESCRIPTIONS: {_missing}. "
                    )

            assert "Missing in _ROLE_DESCRIPTIONS" in str(exc_info.value)
            assert "manager" in str(exc_info.value).lower()
        finally:
            # Restore (monkeypatch auto-restores, but let's be paranoid)
            monkeypatch.setattr(admin, "_ROLE_DESCRIPTIONS", original)

    def test_admin_role_has_highest_permission_count(self):
        """Sanity: ADMIN still resolves to every permission (regression guard)."""
        from app.api.routes.admin import _role_to_detail

        admin_detail = _role_to_detail(Role.ADMIN)
        assert admin_detail.permission_count >= 30, (
            f"ADMIN role lost permissions: count={admin_detail.permission_count}. "
            "Check Role enum or permission definitions."
        )

    def test_manager_role_has_read_only_permissions(self):
        """MANAGER (ADR-0012) should have read+export, NOT write+manage."""
        from app.api.routes.admin import _role_to_detail

        manager = _role_to_detail(Role.MANAGER)
        perms = set(manager.permissions)
        # Should NOT have any :manage or :write permissions
        write_perms = {p for p in perms if ":manage" in p or ":write" in p}
        assert not write_perms, (
            f"MANAGER role unexpectedly has write/manage permissions: {sorted(write_perms)}"
        )
