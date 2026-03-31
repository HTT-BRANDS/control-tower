"""Identity governance service with caching support."""

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.cache import cached, invalidate_on_sync_completion
from app.models.identity import IdentitySnapshot, PrivilegedUser
from app.models.tenant import Tenant
from app.schemas.identity import (
    GuestAccount,
    GroupSummary,
    IdentityStats,
    IdentitySummary,
    PrivilegedAccount,
    StaleAccount,
    TenantIdentitySummary,
    UserAccount,
    UserSummary,
)

logger = logging.getLogger(__name__)


class IdentityService:
    """Service for identity governance operations."""

    def __init__(self, db: Session):
        self.db = db

    @cached("identity_summary")
    async def get_identity_summary(self, tenant_ids: list[str] | None = None) -> IdentitySummary:
        """Get aggregated identity summary across all tenants.

        Args:
            tenant_ids: Optional list of tenant IDs to filter by
        """
        query = self.db.query(Tenant).filter(Tenant.is_active)
        if tenant_ids:
            query = query.filter(Tenant.id.in_(tenant_ids))
        tenants = query.all()

        total_users = 0
        active_users = 0
        guest_users = 0
        mfa_enabled = 0
        mfa_disabled = 0
        privileged_users = 0
        stale_accounts = 0
        service_principals = 0

        tenant_summaries = []

        for tenant in tenants:
            # Get latest identity snapshot
            latest = (
                self.db.query(IdentitySnapshot)
                .filter(IdentitySnapshot.tenant_id == tenant.id)
                .order_by(IdentitySnapshot.snapshot_date.desc())
                .first()
            )

            if latest:
                total_users += latest.total_users
                active_users += latest.active_users
                guest_users += latest.guest_users
                mfa_enabled += latest.mfa_enabled_users
                mfa_disabled += latest.mfa_disabled_users
                privileged_users += latest.privileged_users
                stale_accounts += latest.stale_accounts_30d
                service_principals += latest.service_principals

                # Calculate MFA percent for tenant
                tenant_mfa_percent = 0.0
                if latest.total_users > 0:
                    tenant_mfa_percent = latest.mfa_enabled_users / latest.total_users * 100

                tenant_summaries.append(
                    TenantIdentitySummary(
                        tenant_id=tenant.id,
                        tenant_name=tenant.name,
                        total_users=latest.total_users,
                        guest_users=latest.guest_users,
                        mfa_enabled_percent=tenant_mfa_percent,
                        privileged_users=latest.privileged_users,
                        stale_accounts_30d=latest.stale_accounts_30d,
                        stale_accounts_90d=latest.stale_accounts_90d,
                    )
                )

        # Calculate overall MFA percent
        overall_mfa_percent = 0.0
        if total_users > 0:
            overall_mfa_percent = mfa_enabled / total_users * 100

        return IdentitySummary(
            total_users=total_users,
            active_users=active_users,
            guest_users=guest_users,
            mfa_enabled_percent=overall_mfa_percent,
            privileged_users=privileged_users,
            stale_accounts=stale_accounts,
            service_principals=service_principals,
            by_tenant=tenant_summaries,
        )

    @cached("identity_privileged")
    async def get_privileged_accounts(
        self, tenant_id: str | None = None
    ) -> list[PrivilegedAccount]:
        """Get privileged account details."""
        query = self.db.query(PrivilegedUser)

        if tenant_id:
            query = query.filter(PrivilegedUser.tenant_id == tenant_id)

        users = query.order_by(PrivilegedUser.role_name).all()

        tenants = {t.id: t.name for t in self.db.query(Tenant).all()}

        return [
            PrivilegedAccount(
                tenant_id=u.tenant_id,
                tenant_name=tenants.get(u.tenant_id, "Unknown"),
                user_principal_name=u.user_principal_name,
                display_name=u.display_name or "",
                user_type=u.user_type or "Member",
                role_name=u.role_name,
                role_scope=u.role_scope or "",
                is_permanent=bool(u.is_permanent),
                mfa_enabled=bool(u.mfa_enabled),
                last_sign_in=u.last_sign_in,
                risk_level=self._calculate_risk_level(u),
            )
            for u in users
        ]

    def _calculate_risk_level(self, user: PrivilegedUser) -> str:
        """Calculate risk level for a privileged user."""
        risk_score = 0

        # Guest with privileged access = high risk
        if user.user_type == "Guest":
            risk_score += 3

        # No MFA = higher risk
        if not user.mfa_enabled:
            risk_score += 2

        # Permanent assignment = higher risk than PIM
        if user.is_permanent:
            risk_score += 1

        # No recent sign-in = potential stale account
        if user.last_sign_in:
            _last_sign_in = user.last_sign_in
            if _last_sign_in.tzinfo is None:
                _last_sign_in = _last_sign_in.replace(tzinfo=UTC)
            days_since_signin = (datetime.now(UTC) - _last_sign_in).days
            if days_since_signin > 30:
                risk_score += 1
            if days_since_signin > 90:
                risk_score += 1

        # Map score to level
        if risk_score >= 5:
            return "High"
        elif risk_score >= 3:
            return "Medium"
        return "Low"

    async def get_users(
        self,
        tenant_id: str | None = None,
        tenant_ids: list[str] | None = None,
        user_type: str | None = None,
        account_enabled: bool | None = None,
        mfa_enabled: bool | None = None,
        search: str | None = None,
        sort_by: str = "display_name",
        sort_order: str = "asc",
    ) -> list[UserAccount]:
        """Get user accounts with filtering and sorting.

        Args:
            tenant_id: Filter by specific tenant
            tenant_ids: Filter by multiple tenants
            user_type: Filter by user type (Member or Guest)
            account_enabled: Filter by account enabled status
            mfa_enabled: Filter by MFA status
            search: Search in display name or UPN
            sort_by: Field to sort by
            sort_order: Sort direction (asc or desc)

        Returns:
            List of UserAccount objects matching the filters
        """
        # Build base query from PrivilegedUser as a proxy for user data
        # In production, this would query a dedicated User table populated by sync
        query = self.db.query(PrivilegedUser)

        # Apply tenant filters
        if tenant_id:
            query = query.filter(PrivilegedUser.tenant_id == tenant_id)
        elif tenant_ids:
            query = query.filter(PrivilegedUser.tenant_id.in_(tenant_ids))

        # Apply user type filter
        if user_type:
            query = query.filter(PrivilegedUser.user_type == user_type)

        # Apply MFA filter
        if mfa_enabled is not None:
            query = query.filter(PrivilegedUser.mfa_enabled == mfa_enabled)

        # Apply search filter
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (PrivilegedUser.display_name.ilike(search_term))
                | (PrivilegedUser.user_principal_name.ilike(search_term))
            )

        # Get tenant names for mapping
        tenants = {t.id: t.name for t in self.db.query(Tenant).all()}

        # Execute query
        users = query.all()

        # Convert to UserAccount schema
        user_accounts = []
        for u in users:
            user_accounts.append(
                UserAccount(
                    id=u.id if hasattr(u, "id") else u.user_principal_name,
                    tenant_id=u.tenant_id,
                    tenant_name=tenants.get(u.tenant_id, "Unknown"),
                    user_principal_name=u.user_principal_name,
                    display_name=u.display_name or "",
                    user_type=u.user_type or "Member",
                    account_enabled=getattr(u, "account_enabled", True),
                    mfa_enabled=bool(u.mfa_enabled),
                    last_sign_in=u.last_sign_in,
                    created_at=getattr(u, "created_at", None),
                    job_title=getattr(u, "job_title", None),
                    department=getattr(u, "department", None),
                    office_location=getattr(u, "office_location", None),
                )
            )

        # Apply sorting
        reverse = sort_order == "desc"
        if sort_by == "display_name":
            user_accounts.sort(key=lambda x: x.display_name or "", reverse=reverse)
        elif sort_by == "user_principal_name":
            user_accounts.sort(key=lambda x: x.user_principal_name or "", reverse=reverse)
        elif sort_by == "last_sign_in":
            user_accounts.sort(
                key=lambda x: x.last_sign_in or datetime.min.replace(tzinfo=UTC),
                reverse=reverse,
            )

        return user_accounts

    def get_guest_accounts(
        self, tenant_id: str | None = None, stale_only: bool = False
    ) -> list[GuestAccount]:
        """Get guest account details (not cached - real-time)."""
        # For MVP, we'd query from a cached table of guest users
        # Stub: populated by the identity sync job at runtime
        return []

    def get_stale_accounts(
        self, days_inactive: int = 30, tenant_id: str | None = None
    ) -> list[StaleAccount]:
        """Get stale account details (not cached - real-time)."""
        # For MVP, this would be populated by the sync job
        # comparing last sign-in dates
        return []

    @cached("identity_trends")
    async def get_identity_trends(
        self, tenant_ids: list[str] | None = None, days: int = 30
    ) -> list[dict[str, Any]]:
        """Get identity metrics trends over time.

        Args:
            tenant_ids: Filter by specific tenants
            days: Number of days of history to analyze

        Returns trends for:
        - MFA adoption rate
        - Guest account count
        - Privileged account count
        - Stale account count
        """
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=days)

        # Query identity snapshots within the date range
        query = self.db.query(IdentitySnapshot).filter(
            IdentitySnapshot.snapshot_date >= start_date.date(),
            IdentitySnapshot.snapshot_date <= end_date.date(),
        )

        if tenant_ids:
            query = query.filter(IdentitySnapshot.tenant_id.in_(tenant_ids))

        snapshots = query.order_by(IdentitySnapshot.snapshot_date).all()

        # Group by date and calculate metrics
        by_date: dict[date, dict[str, Any]] = {}
        for snapshot in snapshots:
            date_key = snapshot.snapshot_date
            if date_key not in by_date:
                by_date[date_key] = {
                    "total_users": 0,
                    "mfa_enabled": 0,
                    "mfa_disabled": 0,
                    "guest_users": 0,
                    "privileged_users": 0,
                    "stale_accounts_30d": 0,
                    "stale_accounts_90d": 0,
                    "service_principals": 0,
                    "tenant_count": 0,
                }

            by_date[date_key]["total_users"] += snapshot.total_users
            by_date[date_key]["mfa_enabled"] += snapshot.mfa_enabled_users
            by_date[date_key]["mfa_disabled"] += snapshot.mfa_disabled_users
            by_date[date_key]["guest_users"] += snapshot.guest_users
            by_date[date_key]["privileged_users"] += snapshot.privileged_users
            by_date[date_key]["stale_accounts_30d"] += snapshot.stale_accounts_30d
            by_date[date_key]["stale_accounts_90d"] += snapshot.stale_accounts_90d
            by_date[date_key]["service_principals"] += snapshot.service_principals
            by_date[date_key]["tenant_count"] += 1

        # Build trend data with calculated metrics
        trends = []
        for date_key, data in sorted(by_date.items()):
            mfa_adoption_rate = (
                (data["mfa_enabled"] / data["total_users"] * 100)
                if data["total_users"] > 0
                else 0.0
            )

            trends.append(
                {
                    "date": date_key.isoformat(),
                    "total_users": data["total_users"],
                    "mfa_adoption_rate": round(mfa_adoption_rate, 2),
                    "mfa_enabled": data["mfa_enabled"],
                    "mfa_disabled": data["mfa_disabled"],
                    "guest_users": data["guest_users"],
                    "privileged_users": data["privileged_users"],
                    "stale_accounts_30d": data["stale_accounts_30d"],
                    "stale_accounts_90d": data["stale_accounts_90d"],
                    "service_principals": data["service_principals"],
                    "tenant_count": data["tenant_count"],
                }
            )

        return trends

    async def invalidate_cache(self, tenant_id: str | None = None) -> None:
        """Invalidate identity cache after updates."""
        await invalidate_on_sync_completion(tenant_id)

    async def get_user_summary(
        self,
        tenant_id: str,
        include_guests: bool = False,
    ) -> UserSummary:
        """Get user summary for a tenant.

        Args:
            tenant_id: The tenant ID to query
            include_guests: Whether to include guest users

        Returns:
            UserSummary with user counts and details
        """
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return UserSummary(
                tenant_id=tenant_id,
                tenant_name="Unknown",
                total_users=0,
                active_users=0,
                guest_users=0,
                member_users=0,
                mfa_enabled_count=0,
                mfa_disabled_count=0,
                mfa_enabled_percent=0.0,
            )

        # Get latest identity snapshot for tenant
        latest = (
            self.db.query(IdentitySnapshot)
            .filter(IdentitySnapshot.tenant_id == tenant_id)
            .order_by(IdentitySnapshot.snapshot_date.desc())
            .first()
        )

        if not latest:
            return UserSummary(
                tenant_id=tenant_id,
                tenant_name=tenant.name,
                total_users=0,
                active_users=0,
                guest_users=0,
                member_users=0,
                mfa_enabled_count=0,
                mfa_disabled_count=0,
                mfa_enabled_percent=0.0,
            )

        total_users = latest.total_users if include_guests else latest.total_users - latest.guest_users
        member_users = latest.total_users - latest.guest_users

        mfa_enabled_percent = 0.0
        if latest.total_users > 0:
            mfa_enabled_percent = latest.mfa_enabled_users / latest.total_users * 100

        return UserSummary(
            tenant_id=tenant_id,
            tenant_name=tenant.name,
            total_users=total_users,
            active_users=latest.active_users,
            guest_users=latest.guest_users if include_guests else 0,
            member_users=member_users,
            mfa_enabled_count=latest.mfa_enabled_users,
            mfa_disabled_count=latest.mfa_disabled_users,
            mfa_enabled_percent=mfa_enabled_percent,
        )

    async def get_group_summary(
        self,
        tenant_id: str,
    ) -> GroupSummary:
        """Get group summary for a tenant.

        Args:
            tenant_id: The tenant ID to query

        Returns:
            GroupSummary with group counts and details
        """
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return GroupSummary(
                tenant_id=tenant_id,
                tenant_name="Unknown",
                total_groups=0,
                security_groups=0,
                microsoft_365_groups=0,
                mail_enabled_groups=0,
                dynamic_groups=0,
                synced_groups=0,
            )

        # For MVP, return placeholder data
        # In production, this would query a dedicated Group table
        return GroupSummary(
            tenant_id=tenant_id,
            tenant_name=tenant.name,
            total_groups=0,
            security_groups=0,
            microsoft_365_groups=0,
            mail_enabled_groups=0,
            dynamic_groups=0,
            synced_groups=0,
        )

    async def get_identity_stats(
        self,
        tenant_ids: list[str],
    ) -> dict[str, IdentityStats]:
        """Get identity statistics across multiple tenants.

        Args:
            tenant_ids: List of tenant IDs to query

        Returns:
            Dictionary mapping tenant_id to IdentityStats
        """
        results: dict[str, IdentityStats] = {}

        for tenant_id in tenant_ids:
            user_summary = await self.get_user_summary(tenant_id, include_guests=True)
            group_summary = await self.get_group_summary(tenant_id)

            # Get latest snapshot for additional stats
            latest = (
                self.db.query(IdentitySnapshot)
                .filter(IdentitySnapshot.tenant_id == tenant_id)
                .order_by(IdentitySnapshot.snapshot_date.desc())
                .first()
            )

            tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
            tenant_name = tenant.name if tenant else "Unknown"

            results[tenant_id] = IdentityStats(
                tenant_id=tenant_id,
                tenant_name=tenant_name,
                users=user_summary,
                groups=group_summary,
                privileged_users=latest.privileged_users if latest else 0,
                service_principals=latest.service_principals if latest else 0,
                managed_identities=0,  # Placeholder for MVP
                stale_accounts_30d=latest.stale_accounts_30d if latest else 0,
                stale_accounts_90d=latest.stale_accounts_90d if latest else 0,
                snapshot_date=latest.snapshot_date if latest else datetime.now(UTC),
            )

        return results
