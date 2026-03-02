"""Azure AD Admin Role Service for collecting privileged access data.

This module provides a comprehensive service for:
- Querying Azure AD directory roles and role definitions
- Fetching privileged role assignments for users and service principals
- Identifying global admins, security admins, and other privileged roles
- Tracking role assignments per user with support for both direct and PIM assignments
- Caching results for improved performance
- Supporting all Riverside tenants with proper error handling and retry logic

Features:
- Async functions for all operations
- Error handling and retry logic with exponential backoff
- Rate limiting compliance to respect Graph API throttling
- Cache integration for performance optimization
- Multi-tenant support
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.api.services.graph_client import (
    AdminRoleSummary,
    DirectoryRole,
    GraphClient,
    PrivilegedAccessAssignment,
    RoleAssignment,
)
from app.core.cache import cache_manager, cached
from app.core.retry import GRAPH_API_POLICY, retry_with_backoff

logger = logging.getLogger(__name__)


class AdminRoleError(Exception):
    """Exception raised when admin role operations fail."""

    def __init__(self, message: str, tenant_id: str | None = None) -> None:
        super().__init__(message)
        self.tenant_id = tenant_id


@dataclass
class AdminRoleMetrics:
    """Metrics for admin role collection operations."""

    tenant_id: str
    total_roles_collected: int = 0
    total_assignments_collected: int = 0
    pim_assignments_collected: int = 0
    privileged_users_count: int = 0
    privileged_service_principals_count: int = 0
    collection_duration_seconds: float = 0.0
    errors_encountered: int = 0
    cached: bool = False


class AzureADAdminService:
    """Service for collecting and managing Azure AD admin role data.

    This service provides a high-level interface for querying Azure AD
    directory roles, role assignments, and privileged access data.
    It includes caching, retry logic, and multi-tenant support.

    Example:
        service = AzureADAdminService()
        
        # Get admin role summary for a tenant
        summary = await service.get_admin_role_summary("tenant-id")
        
        # Get privileged users with their roles
        users = await service.get_privileged_users("tenant-id")
        
        # Sync data to database
        await service.sync_privileged_users("tenant-id", db_session)
    """

    # Cache TTL for different data types (seconds)
    CACHE_TTL_ROLES = 3600  # 1 hour
    CACHE_TTL_ASSIGNMENTS = 1800  # 30 minutes
    CACHE_TTL_SUMMARY = 900  # 15 minutes

    # Batch sizes for API calls
    DEFAULT_BATCH_SIZE = 100
    MAX_BATCH_SIZE = 999

    def __init__(self) -> None:
        self._clients: dict[str, GraphClient] = {}

    def _get_client(self, tenant_id: str) -> GraphClient:
        """Get or create GraphClient for a tenant."""
        if tenant_id not in self._clients:
            self._clients[tenant_id] = GraphClient(tenant_id)
        return self._clients[tenant_id]

    def _generate_cache_key(self, prefix: str, tenant_id: str, *args) -> str:
        """Generate a cache key for tenant-isolated data."""
        return cache_manager.generate_key(prefix, tenant_id, *args)

    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_directory_roles(
        self,
        tenant_id: str,
        include_built_in: bool = True,
        use_cache: bool = True,
    ) -> list[DirectoryRole]:
        """Get all directory roles for a tenant.

        Args:
            tenant_id: The Azure tenant ID
            include_built_in: Include built-in directory roles
            use_cache: Use cached data if available

        Returns:
            List of DirectoryRole objects

        Raises:
            AdminRoleError: If the operation fails
        """
        cache_key = self._generate_cache_key("admin_roles", tenant_id, include_built_in)

        # Try cache first
        if use_cache:
            cached_data = await cache_manager.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for directory roles: {tenant_id}")
                return [DirectoryRole(**r) for r in cached_data]

        try:
            client = self._get_client(tenant_id)
            roles = await client.get_directory_role_definitions(include_built_in)

            # Cache the results
            if use_cache:
                await cache_manager.set(
                    cache_key,
                    [r.__dict__ for r in roles],
                    ttl_seconds=self.CACHE_TTL_ROLES,
                )

            return roles

        except Exception as e:
            logger.error(f"Failed to get directory roles for tenant {tenant_id}: {e}")
            raise AdminRoleError(
                f"Failed to get directory roles: {e}",
                tenant_id=tenant_id,
            ) from e

    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_role_assignments(
        self,
        tenant_id: str,
        batch_size: int = 100,
        include_inactive: bool = False,
        use_cache: bool = True,
    ) -> list[RoleAssignment]:
        """Get all directory role assignments for a tenant.

        Args:
            tenant_id: The Azure tenant ID
            batch_size: Number of assignments per page (max 999)
            include_inactive: Include inactive assignments
            use_cache: Use cached data if available

        Returns:
            List of RoleAssignment objects

        Raises:
            AdminRoleError: If the operation fails
        """
        batch_size = min(batch_size, self.MAX_BATCH_SIZE)
        cache_key = self._generate_cache_key(
            "role_assignments", tenant_id, batch_size, include_inactive
        )

        # Try cache first
        if use_cache:
            cached_data = await cache_manager.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for role assignments: {tenant_id}")
                return [RoleAssignment(**a) for a in cached_data]

        try:
            client = self._get_client(tenant_id)
            assignments = await client.get_role_assignments_paginated(
                batch_size=batch_size,
                include_inactive=include_inactive,
            )

            # Cache the results
            if use_cache:
                await cache_manager.set(
                    cache_key,
                    [a.__dict__ for a in assignments],
                    ttl_seconds=self.CACHE_TTL_ASSIGNMENTS,
                )

            return assignments

        except Exception as e:
            logger.error(f"Failed to get role assignments for tenant {tenant_id}: {e}")
            raise AdminRoleError(
                f"Failed to get role assignments: {e}",
                tenant_id=tenant_id,
            ) from e

    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_pim_assignments(
        self,
        tenant_id: str,
        batch_size: int = 100,
        include_eligible: bool = True,
        include_active: bool = True,
        use_cache: bool = True,
    ) -> list[PrivilegedAccessAssignment]:
        """Get PIM (Privileged Identity Management) role assignments.

        Args:
            tenant_id: The Azure tenant ID
            batch_size: Number of assignments per page
            include_eligible: Include eligible assignments
            include_active: Include active assignments
            use_cache: Use cached data if available

        Returns:
            List of PrivilegedAccessAssignment objects

        Raises:
            AdminRoleError: If the operation fails
        """
        batch_size = min(batch_size, self.MAX_BATCH_SIZE)
        cache_key = self._generate_cache_key(
            "pim_assignments", tenant_id, batch_size, include_eligible, include_active
        )

        # Try cache first
        if use_cache:
            cached_data = await cache_manager.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for PIM assignments: {tenant_id}")
                return [PrivilegedAccessAssignment(**a) for a in cached_data]

        try:
            client = self._get_client(tenant_id)
            assignments = await client.get_pim_role_assignments(
                batch_size=batch_size,
                include_eligible=include_eligible,
                include_active=include_active,
            )

            # Cache the results
            if use_cache:
                await cache_manager.set(
                    cache_key,
                    [a.__dict__ for a in assignments],
                    ttl_seconds=self.CACHE_TTL_ASSIGNMENTS,
                )

            return assignments

        except Exception as e:
            logger.warning(f"Failed to get PIM assignments for tenant {tenant_id}: {e}")
            # PIM might not be enabled in all tenants, so we return empty list
            # rather than raising an error
            return []

    async def get_privileged_users(
        self,
        tenant_id: str,
        include_pim: bool = True,
        batch_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Get all privileged users with their role assignments.

        Retrieves users with directory role assignments, including
        global admins, security admins, and other privileged roles.

        Args:
            tenant_id: The Azure tenant ID
            include_pim: Include PIM eligible/active assignments
            batch_size: Number of items per page

        Returns:
            List of privileged user dictionaries with role information

        Raises:
            AdminRoleError: If the operation fails
        """
        try:
            # Get role assignments
            assignments = await self.get_role_assignments(
                tenant_id,
                batch_size=batch_size,
                use_cache=True,
            )

            # Filter for user assignments
            user_assignments = [a for a in assignments if a.principal_type == "User"]

            # Get PIM assignments if requested
            pim_assignments: list[PrivilegedAccessAssignment] = []
            if include_pim:
                pim_assignments = await self.get_pim_assignments(
                    tenant_id,
                    batch_size=batch_size,
                    use_cache=True,
                )

            # Build privileged users list
            privileged_users: dict[str, dict[str, Any]] = {}

            # Process direct role assignments
            for assignment in user_assignments:
                principal_id = assignment.principal_id

                if principal_id not in privileged_users:
                    privileged_users[principal_id] = {
                        "principal_id": principal_id,
                        "user_principal_name": assignment.principal_display_name,
                        "display_name": assignment.principal_display_name,
                        "roles": [],
                        "is_permanent": True,
                        "pim_assignments": [],
                    }

                privileged_users[principal_id]["roles"].append({
                    "role_name": assignment.role_name,
                    "role_template_id": assignment.role_template_id,
                    "scope_type": assignment.scope_type,
                    "scope_id": assignment.scope_id,
                    "assignment_type": assignment.assignment_type,
                })

            # Process PIM assignments
            for pim in pim_assignments:
                if pim.principal_type != "User":
                    continue

                principal_id = pim.principal_id
                if principal_id not in privileged_users:
                    privileged_users[principal_id] = {
                        "principal_id": principal_id,
                        "user_principal_name": pim.principal_display_name,
                        "display_name": pim.principal_display_name,
                        "roles": [],
                        "is_permanent": False,
                        "pim_assignments": [],
                    }

                privileged_users[principal_id]["pim_assignments"].append({
                    "role_name": pim.role_name,
                    "role_definition_id": pim.role_definition_id,
                    "assignment_state": pim.assignment_state,
                    "start_date_time": pim.start_date_time,
                    "end_date_time": pim.end_date_time,
                    "duration": pim.duration,
                })
                privileged_users[principal_id]["is_permanent"] = False

            return list(privileged_users.values())

        except Exception as e:
            logger.error(f"Failed to get privileged users for tenant {tenant_id}: {e}")
            raise AdminRoleError(
                f"Failed to get privileged users: {e}",
                tenant_id=tenant_id,
            ) from e

    async def get_privileged_service_principals(
        self,
        tenant_id: str,
        batch_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Get all privileged service principals with their role assignments.

        Args:
            tenant_id: The Azure tenant ID
            batch_size: Number of items per page

        Returns:
            List of privileged service principal dictionaries

        Raises:
            AdminRoleError: If the operation fails
        """
        try:
            assignments = await self.get_role_assignments(
                tenant_id,
                batch_size=batch_size,
                use_cache=True,
            )

            # Filter for service principal assignments
            sp_assignments = [a for a in assignments if a.principal_type == "ServicePrincipal"]

            # Group by service principal
            privileged_sps: dict[str, dict[str, Any]] = {}

            for assignment in sp_assignments:
                principal_id = assignment.principal_id

                if principal_id not in privileged_sps:
                    privileged_sps[principal_id] = {
                        "principal_id": principal_id,
                        "app_id": assignment.principal_display_name,
                        "display_name": assignment.principal_display_name,
                        "roles": [],
                    }

                privileged_sps[principal_id]["roles"].append({
                    "role_name": assignment.role_name,
                    "role_template_id": assignment.role_template_id,
                    "scope_type": assignment.scope_type,
                    "scope_id": assignment.scope_id,
                })

            return list(privileged_sps.values())

        except Exception as e:
            logger.error(
                f"Failed to get privileged service principals for tenant {tenant_id}: {e}"
            )
            raise AdminRoleError(
                f"Failed to get privileged service principals: {e}",
                tenant_id=tenant_id,
            ) from e

    async def get_admin_role_summary(
        self,
        tenant_id: str,
        batch_size: int = 100,
        use_cache: bool = True,
    ) -> AdminRoleSummary:
        """Get comprehensive admin role summary for a tenant.

        This method provides a complete picture of privileged access in the tenant,
        including role assignments, PIM data, and statistics.

        Args:
            tenant_id: The Azure tenant ID
            batch_size: Number of items per page for API calls
            use_cache: Use cached data if available

        Returns:
            AdminRoleSummary with complete statistics

        Raises:
            AdminRoleError: If the operation fails
        """
        cache_key = self._generate_cache_key("admin_role_summary", tenant_id, batch_size)

        # Try cache first
        if use_cache:
            cached_data = await cache_manager.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for admin role summary: {tenant_id}")
                return AdminRoleSummary(**cached_data)

        try:
            client = self._get_client(tenant_id)
            summary = await client.get_admin_role_summary(batch_size=batch_size)

            # Cache the results
            if use_cache:
                await cache_manager.set(
                    cache_key,
                    summary.__dict__,
                    ttl_seconds=self.CACHE_TTL_SUMMARY,
                )

            return summary

        except Exception as e:
            logger.error(f"Failed to get admin role summary for tenant {tenant_id}: {e}")
            raise AdminRoleError(
                f"Failed to get admin role summary: {e}",
                tenant_id=tenant_id,
            ) from e

    async def get_role_assignment_counts_by_user(
        self,
        tenant_id: str,
    ) -> dict[str, dict[str, Any]]:
        """Get role assignment counts grouped by user.

        Useful for identifying users with multiple admin roles.

        Args:
            tenant_id: The Azure tenant ID

        Returns:
            Dictionary mapping user principal name to role counts
        """
        privileged_users = await self.get_privileged_users(tenant_id)

        user_counts: dict[str, dict[str, Any]] = {}
        for user in privileged_users:
            upn = user.get("user_principal_name", "")
            roles = user.get("roles", [])
            pim = user.get("pim_assignments", [])

            user_counts[upn] = {
                "principal_id": user.get("principal_id"),
                "display_name": user.get("display_name"),
                "total_role_count": len(roles),
                "pim_assignments_count": len(pim),
                "role_names": [r["role_name"] for r in roles],
            }

        return user_counts

    async def get_global_admins(
        self,
        tenant_id: str,
    ) -> list[dict[str, Any]]:
        """Get all global administrators.

        Args:
            tenant_id: The Azure tenant ID

        Returns:
            List of global admin user dictionaries
        """
        privileged_users = await self.get_privileged_users(tenant_id)

        global_admins = []
        global_admin_template_id = "62e90394-69f5-4237-9190-012177145e10"

        for user in privileged_users:
            roles = user.get("roles", [])
            for role in roles:
                if role.get("role_template_id") == global_admin_template_id:
                    global_admins.append(user)
                    break

        return global_admins

    async def get_security_admins(
        self,
        tenant_id: str,
    ) -> list[dict[str, Any]]:
        """Get all security administrators.

        Args:
            tenant_id: The Azure tenant ID

        Returns:
            List of security admin user dictionaries
        """
        privileged_users = await self.get_privileged_users(tenant_id)

        security_admins = []
        security_admin_template_id = "194ae4cb-b126-40b2-bd5b-6091b380977d"

        for user in privileged_users:
            roles = user.get("roles", [])
            for role in roles:
                if role.get("role_template_id") == security_admin_template_id:
                    security_admins.append(user)
                    break

        return security_admins

    async def invalidate_cache(
        self,
        tenant_id: str,
        data_type: str | None = None,
    ) -> int:
        """Invalidate cached admin role data for a tenant.

        Args:
            tenant_id: The Azure tenant ID
            data_type: Optional specific data type to invalidate
                       ("roles", "assignments", "pim", "summary")

        Returns:
            Number of cache entries invalidated
        """
        if data_type:
            pattern = f"{data_type}:{tenant_id}"
            return await cache_manager.delete_pattern(pattern)
        else:
            # Invalidate all admin role data for tenant
            patterns = [
                f"admin_roles:{tenant_id}",
                f"role_assignments:{tenant_id}",
                f"pim_assignments:{tenant_id}",
                f"admin_role_summary:{tenant_id}",
            ]
            total = 0
            for pattern in patterns:
                total += await cache_manager.delete_pattern(pattern)
            return total


# Global service instance
azure_ad_admin_service = AzureADAdminService()
