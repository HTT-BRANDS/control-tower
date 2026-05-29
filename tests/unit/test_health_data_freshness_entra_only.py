"""Unit tests for /healthz/data freshness — Entra-only tenant carve-out.

Regression guard for bd ct-1m0: tenants with zero Azure subscriptions cannot
populate ARM-dependent domains (resources, compliance), so the freshness check
must NOT flag them as stale for those domains.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes.health import (
    ARM_DEPENDENT_DOMAINS,
    ENTRA_ONLY_TENANT_IDS,
    data_freshness_check,
)
from app.core.database import Base
from app.models.cost import CostSnapshot
from app.models.identity import IdentitySnapshot
from app.models.resource import Resource
from app.models.tenant import Tenant


@pytest.fixture()
def db_session():
    """In-memory SQLite session with full schema."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _make_tenant(session, *, tenant_id: str, name: str) -> Tenant:
    t = Tenant(
        id=tenant_id,
        tenant_id=tenant_id,
        name=name,
        is_active=True,
    )
    session.add(t)
    session.commit()
    return t


def _add_identity_row(session, tenant_pk: str, when: datetime) -> None:
    session.add(
        IdentitySnapshot(
            tenant_id=tenant_pk,
            snapshot_date=date.today(),
            total_users=1,
            mfa_enabled_users=1,
            synced_at=when,
        )
    )
    session.commit()


def _add_cost_row(session, tenant_pk: str, when: datetime) -> None:
    """Add a CostSnapshot row. Tries the obvious fields; gracefully falls back
    to whatever the model actually exposes (schema-agnostic test helper)."""
    cols = {c.name for c in CostSnapshot.__table__.columns}
    kwargs: dict = {"tenant_id": tenant_pk}
    if "date" in cols:
        kwargs["date"] = when.date()
    if "snapshot_date" in cols:
        kwargs["snapshot_date"] = when.date()
    if "synced_at" in cols:
        kwargs["synced_at"] = when
    if "total_cost" in cols:
        kwargs["total_cost"] = 0
    if "cost_amount" in cols:
        kwargs["cost_amount"] = 0
    if "currency" in cols:
        kwargs["currency"] = "USD"
    if "subscription_id" in cols:
        kwargs["subscription_id"] = "11111111-1111-1111-1111-111111111111"
    if "resource_group" in cols:
        kwargs["resource_group"] = "y"
    if "service_name" in cols:
        kwargs["service_name"] = "test"
    session.add(CostSnapshot(**kwargs))
    session.commit()


def _add_resource_row(session, tenant_pk: str, when: datetime) -> None:
    session.add(
        Resource(
            id=f"/subscriptions/x/resourceGroups/y/providers/z/{tenant_pk}",
            tenant_id=tenant_pk,
            subscription_id="11111111-1111-1111-1111-111111111111",
            resource_group="y",
            resource_type="Microsoft.Storage/storageAccounts",
            name=f"r-{tenant_pk}",
            location="eastus",
            synced_at=when,
        )
    )
    session.commit()


class TestEntraOnlyCarveOut:
    """The Entra-only constant + freshness check work together."""

    def test_dce_is_in_entra_only_set(self):
        # The whole point of ct-1m0
        assert "ce62e17d-2feb-4e67-a115-8ea4af68da30" in ENTRA_ONLY_TENANT_IDS

    def test_arm_dependent_domains_well_defined(self):
        # resources + compliance can't exist without an ARM subscription
        assert ARM_DEPENDENT_DOMAINS == frozenset({"resources", "compliance"})

    @pytest.mark.asyncio
    async def test_entra_only_tenant_not_stale_with_identity_and_costs(self, db_session):
        """Entra-only tenant with the achievable-domains (identity + costs) is GREEN.

        Mirrors real DCE prod state: costs populated via zero-cost marker, identity
        populated via Graph, resources/compliance impossible due to zero ARM subs.
        """
        entra_id = next(iter(ENTRA_ONLY_TENANT_IDS))
        _make_tenant(db_session, tenant_id=entra_id, name="DCE-test")
        now = datetime.now(UTC)
        _add_identity_row(db_session, entra_id, now)
        _add_cost_row(db_session, entra_id, now)

        result = await data_freshness_check(db=db_session)

        tenant_row = result["tenants"]["DCE-test"]
        assert tenant_row["stale"] is False, (
            "Entra-only tenant flagged stale despite having identity + costs and "
            "no ability to populate ARM-dependent domains"
        )
        assert tenant_row["arm_enabled"] is False
        assert tenant_row["resources"] is None
        assert tenant_row["compliance"] is None

    @pytest.mark.asyncio
    async def test_regular_tenant_stale_without_resources(self, db_session):
        """A non-Entra-only tenant missing resources IS stale (regression guard)."""
        regular_id = "11111111-2222-3333-4444-555555555555"
        assert regular_id not in ENTRA_ONLY_TENANT_IDS  # sanity

        _make_tenant(db_session, tenant_id=regular_id, name="Regular")
        _add_identity_row(db_session, regular_id, datetime.now(UTC))
        # NB: deliberately not adding Resource row

        result = await data_freshness_check(db=db_session)

        tenant_row = result["tenants"]["Regular"]
        assert tenant_row["stale"] is True, (
            "Regular tenant missing resources/compliance should be stale; carve-out leaked"
        )
        assert tenant_row["arm_enabled"] is True

    @pytest.mark.asyncio
    async def test_entra_only_still_stale_if_identity_missing(self, db_session):
        """The carve-out is narrow: identity remains required even for Entra-only."""
        entra_id = next(iter(ENTRA_ONLY_TENANT_IDS))
        _make_tenant(db_session, tenant_id=entra_id, name="DCE-test")
        # No identity data added — should still be stale

        result = await data_freshness_check(db=db_session)

        tenant_row = result["tenants"]["DCE-test"]
        assert tenant_row["stale"] is True
        assert tenant_row["arm_enabled"] is False

    @pytest.mark.asyncio
    async def test_entra_only_with_old_identity_is_stale(self, db_session):
        """Identity older than threshold still triggers stale for Entra-only tenants."""
        entra_id = next(iter(ENTRA_ONLY_TENANT_IDS))
        _make_tenant(db_session, tenant_id=entra_id, name="DCE-test")
        _add_identity_row(db_session, entra_id, datetime.now(UTC) - timedelta(days=30))

        result = await data_freshness_check(db=db_session)

        tenant_row = result["tenants"]["DCE-test"]
        assert tenant_row["stale"] is True

    @pytest.mark.asyncio
    async def test_top_level_response_shape(self, db_session):
        """The endpoint advertises arm_dependent_domains so clients can render it."""
        _make_tenant(db_session, tenant_id="aaa-bbb-ccc", name="X")
        _add_identity_row(db_session, "aaa-bbb-ccc", datetime.now(UTC))
        _add_resource_row(db_session, "aaa-bbb-ccc", datetime.now(UTC))

        result = await data_freshness_check(db=db_session)

        assert "arm_dependent_domains" in result
        assert set(result["arm_dependent_domains"]) == ARM_DEPENDENT_DOMAINS
        assert "required_domains" in result
