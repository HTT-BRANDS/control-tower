"""Regression test for ct-45q: /api/v1/identity/users returned 500.

The endpoint built a ``UserAccount`` (schema field ``id: str``) using
``PrivilegedUser.id`` (autoincrement integer PK). Pydantic refused the
int and every call 500'd with::

    ValidationError: id: Input should be a valid string
    [type=string_type, input_value=1, input_type=int]

Fix: use ``user_principal_name`` as the id. UPN is the natural
identifier for ``PrivilegedUser`` rows AND it matches the schema's
documented intent (the field describes itself as 'Azure AD user
object ID', which a database autoincrement integer absolutely is not).
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch


def _noop_cache(cache_key):  # pragma: no cover - test fixture
    def decorator(func):
        return func

    return decorator


with patch("app.core.cache.cached", _noop_cache):
    sys.modules.pop("app.api.services.identity_service", None)
    from app.api.services.identity_service import IdentityService

from app.models.identity import PrivilegedUser
from app.models.tenant import Tenant


def _make_user(int_id: int, upn: str, tenant_id: str = "t1") -> MagicMock:
    """A PrivilegedUser mock whose ``id`` is an int — like the real model."""
    u = MagicMock(spec=PrivilegedUser)
    u.id = int_id  # ← critical: int, not str
    u.tenant_id = tenant_id
    u.user_principal_name = upn
    u.display_name = "Test User"
    u.user_type = "Member"
    u.account_enabled = True
    u.mfa_enabled = 1
    u.last_sign_in = None
    u.created_at = None
    u.job_title = None
    u.department = None
    u.office_location = None
    return u


def _make_tenant(tid: str, name: str) -> MagicMock:
    t = MagicMock(spec=Tenant)
    t.id = tid
    t.name = name
    return t


import pytest


@pytest.mark.asyncio
async def test_get_users_returns_string_ids_not_ints():
    """ct-45q: the schema declares ``id: str``; service must comply."""
    mock_db = MagicMock()

    users_query = MagicMock()
    users_query.filter.return_value = users_query
    users_query.all.return_value = [
        _make_user(1, "alice@example.com"),
        _make_user(2, "bob@example.com"),
    ]

    tenants_query = MagicMock()
    tenants_query.all.return_value = [_make_tenant("t1", "Tenant One")]

    # First .query() call → PrivilegedUser; second → Tenant
    # The service first calls db.query(PrivilegedUser) (and chains filters),
    # then db.query(Tenant).all() for the name map.
    mock_db.query.side_effect = [users_query, tenants_query]

    service = IdentityService(db=mock_db)
    result = await service.get_users()

    assert len(result) == 2
    for user in result:
        assert isinstance(user.id, str), (
            f"ct-45q: UserAccount.id must be str, got {type(user.id).__name__}"
        )
    # Confirm the chosen id is the UPN (the documented 'Azure AD user object ID'
    # intent of the schema), NOT a stringified autoincrement integer.
    assert {u.id for u in result} == {
        "alice@example.com",
        "bob@example.com",
    }
