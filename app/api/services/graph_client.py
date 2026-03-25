"""Microsoft Graph API client for identity operations.

This module provides a comprehensive Graph API client with:
- MFA data collection methods
- Admin role and privileged access data collection
- Pagination support for large user bases
- Rate limiting compliance
- Error handling and retry logic
- Circuit breaker pattern for resilience
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx
from azure.core.credentials import TokenCredential
from azure.identity import ClientSecretCredential

from app.core.circuit_breaker import GRAPH_API_BREAKER, circuit_breaker
from app.core.config import get_settings
from app.core.retry import GRAPH_API_POLICY, retry_with_backoff

logger = logging.getLogger(__name__)
settings = get_settings()

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_BETA_API_BASE = "https://graph.microsoft.com/beta"
GRAPH_SCOPES = ["https://graph.microsoft.com/.default"]


@dataclass
class MFAMethodDetails:
    """MFA method details for a user."""

    method_type: str
    is_default: bool
    is_enabled: bool
    phone_number: str | None = None
    email_address: str | None = None
    display_name: str | None = None
    app_id: str | None = None


@dataclass
class UserMFAStatus:
    """Complete MFA status for a user."""

    user_id: str
    user_principal_name: str
    display_name: str
    is_mfa_registered: bool
    methods_registered: list[str]
    auth_methods: list[MFAMethodDetails]
    default_method: str | None
    last_updated: str | None


@dataclass
class TenantMFASummary:
    """MFA summary statistics for a tenant."""

    tenant_id: str
    total_users: int
    mfa_registered_users: int
    mfa_coverage_percentage: float
    admin_accounts_total: int
    admin_accounts_mfa: int
    admin_mfa_percentage: float
    method_breakdown: dict[str, int]
    users_without_mfa: list[dict[str, Any]]


@dataclass
class DirectoryRole:
    """Azure AD directory role definition."""

    role_id: str
    display_name: str
    description: str
    role_template_id: str
    is_built_in: bool


@dataclass
class RoleAssignment:
    """Azure AD role assignment with principal and role details."""

    assignment_id: str
    principal_id: str
    principal_type: str  # User, Group, ServicePrincipal
    principal_display_name: str
    role_definition_id: str
    role_name: str
    role_template_id: str
    scope_type: str  # Directory, Subscription, ResourceGroup
    scope_id: str | None
    created_date_time: str | None
    assignment_type: str  # Direct, Group, PIM


@dataclass
class PrivilegedAccessAssignment:
    """PIM (Privileged Identity Management) role assignment."""

    assignment_id: str
    principal_id: str
    principal_type: str
    principal_display_name: str
    role_definition_id: str
    role_name: str
    assignment_state: str  # active, eligible
    start_date_time: str | None
    end_date_time: str | None
    duration: str | None  # For time-bound assignments


@dataclass
class AdminRoleSummary:
    """Summary of admin roles and privileged access in a tenant."""

    tenant_id: str
    total_roles: int
    total_assignments: int
    privileged_users: list[dict[str, Any]]
    privileged_service_principals: list[dict[str, Any]]
    pim_assignments: list[dict[str, Any]]
    roles_without_members: list[str]
    global_admin_count: int
    security_admin_count: int
    privileged_role_admin_count: int
    other_admin_count: int


class MFAError(Exception):
    """Exception raised when MFA data collection fails."""

    def __init__(self, message: str, user_id: str | None = None) -> None:
        super().__init__(message)
        self.user_id = user_id


class GraphClient:
    """Microsoft Graph API client wrapper."""

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self._token: str | None = None
        self._credential: TokenCredential | None = None

    def _get_credential(self) -> TokenCredential:
        """Get or create credential for this tenant.

        Supports two modes controlled by ``settings.use_oidc_federation``:

        * **OIDC mode**: uses ``OIDCCredentialProvider`` backed by the App Service
          Managed Identity — no client secret required.
        * **Secret mode**: resolves ``client_id`` / ``client_secret`` via env vars,
          Key Vault, or settings fallback through ``AzureClientManager``.
        """
        if not self._credential:
            if settings.use_oidc_federation:
                from app.core.oidc_credential import get_oidc_provider
                from app.core.tenants_config import get_app_id_for_tenant

                client_id = get_app_id_for_tenant(self.tenant_id)
                if not client_id:
                    # Fall back to DB record
                    from app.api.services.azure_client import AzureClientManager

                    tenant_record = AzureClientManager()._get_tenant_from_db(self.tenant_id)
                    client_id = tenant_record.client_id if tenant_record else None
                if not client_id:
                    raise ValueError(
                        f"OIDC mode: could not resolve client_id for tenant {self.tenant_id}. "
                        "Add it to tenants_config.py or the tenants DB table."
                    )
                self._credential = get_oidc_provider().get_credential_for_tenant(
                    self.tenant_id, client_id
                )
            else:
                from app.api.services.azure_client import AzureClientManager

                manager = AzureClientManager()
                client_id, client_secret, _ = manager._resolve_credentials(self.tenant_id)
                self._credential = ClientSecretCredential(
                    tenant_id=self.tenant_id,
                    client_id=client_id,
                    client_secret=client_secret,
                    connection_timeout=10,
                )
        return self._credential

    async def _get_token(self) -> str:
        """Get access token for Graph API.

        Uses asyncio.to_thread() to avoid blocking the event loop
        since ClientSecretCredential.get_token() is synchronous.
        """
        credential = self._get_credential()
        token = await asyncio.to_thread(credential.get_token, *GRAPH_SCOPES)
        return token.token

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
    ) -> dict:
        """Make authenticated request to Graph API."""
        token = await self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            url = f"{GRAPH_API_BASE}{endpoint}"
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    @circuit_breaker(GRAPH_API_BREAKER)
    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_users(self, top: int = 999) -> list[dict]:
        """Get all users in the tenant.

        Note: signInActivity requires AuditLog.Read.All — if the app
        registration lacks that permission, we gracefully retry without it.
        """
        users: list[dict] = []
        endpoint = "/users"
        base_fields = "id,displayName,userPrincipalName,userType,accountEnabled,createdDateTime"
        params = {
            "$top": top,
            "$select": f"{base_fields},signInActivity",
        }

        try:
            data = await self._request("GET", endpoint, params)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                # signInActivity requires AuditLog.Read.All — degrade gracefully
                logger.warning(
                    f"signInActivity requires AuditLog.Read.All for tenant "
                    f"{self.tenant_id[:8]}..., retrying without it"
                )
                params["$select"] = base_fields
                data = await self._request("GET", endpoint, params)
            else:
                raise

        users.extend(data.get("value", []))

        # Handle pagination
        next_link = data.get("@odata.nextLink")
        while next_link:
            endpoint = next_link.replace(GRAPH_API_BASE, "")
            data = await self._request("GET", endpoint)
            users.extend(data.get("value", []))
            next_link = data.get("@odata.nextLink")

        return users

    @circuit_breaker(GRAPH_API_BREAKER)
    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_guest_users(self) -> list[dict]:
        """Get all guest users.

        Note: signInActivity requires AuditLog.Read.All — degrades gracefully.
        """
        endpoint = "/users"
        base_fields = "id,displayName,userPrincipalName,createdDateTime,externalUserState"
        params = {
            "$filter": "userType eq 'Guest'",
            "$select": f"{base_fields},signInActivity",
        }
        try:
            data = await self._request("GET", endpoint, params)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                logger.warning(
                    f"signInActivity requires AuditLog.Read.All for tenant "
                    f"{self.tenant_id[:8]}... (guest query), retrying without it"
                )
                params["$select"] = base_fields
                data = await self._request("GET", endpoint, params)
            else:
                raise
        return data.get("value", [])

    @circuit_breaker(GRAPH_API_BREAKER)
    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_directory_roles(self) -> list[dict]:
        """Get all directory roles with members."""
        endpoint = "/directoryRoles"
        params = {"$expand": "members"}
        data = await self._request("GET", endpoint, params)
        return data.get("value", [])

    @circuit_breaker(GRAPH_API_BREAKER)
    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_privileged_role_assignments(self) -> list[dict]:
        """Get privileged role assignments."""
        endpoint = "/roleManagement/directory/roleAssignments"
        params = {"$expand": "principal,roleDefinition"}
        data = await self._request("GET", endpoint, params)
        return data.get("value", [])

    @circuit_breaker(GRAPH_API_BREAKER)
    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_directory_role_definitions(
        self,
        include_built_in: bool = True,
    ) -> list[DirectoryRole]:
        """Get all directory role definitions.

        Retrieves Azure AD built-in and custom directory roles.

        Args:
            include_built_in: Include built-in roles (default: True)

        Returns:
            List of DirectoryRole objects
        """
        endpoint = "/directoryRoles"
        params: dict[str, Any] = {
            "$select": "id,displayName,description,roleTemplateId,isBuiltIn",
        }

        roles: list[DirectoryRole] = []
        current_endpoint = endpoint

        while current_endpoint:
            data = await self._request("GET", current_endpoint, params)
            items = data.get("value", [])

            for role in items:
                is_built_in = role.get("isBuiltIn", True)
                if not include_built_in and is_built_in:
                    continue

                roles.append(
                    DirectoryRole(
                        role_id=role.get("id", ""),
                        display_name=role.get("displayName", ""),
                        description=role.get("description", ""),
                        role_template_id=role.get("roleTemplateId", ""),
                        is_built_in=is_built_in,
                    )
                )

            # Handle pagination
            next_link = data.get("@odata.nextLink")
            if next_link:
                current_endpoint = next_link.replace(GRAPH_API_BASE, "")
                params = None
                await asyncio.sleep(0.05)  # Rate limiting
            else:
                current_endpoint = None

        return roles

    @circuit_breaker(GRAPH_API_BREAKER)
    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_role_assignments_paginated(
        self,
        batch_size: int = 100,
        include_inactive: bool = False,
    ) -> list[RoleAssignment]:
        """Get all directory role assignments with full details.

        Retrieves role assignments including principal and role definition details.
        Handles pagination for large result sets.

        Args:
            batch_size: Number of assignments per page (max 999)
            include_inactive: Include inactive assignments

        Returns:
            List of RoleAssignment objects
        """
        endpoint = "/roleManagement/directory/roleAssignments"
        params: dict[str, Any] = {
            "$top": min(batch_size, 999),
            "$expand": "principal($select=id,displayName,userPrincipalName,appId,userType),roleDefinition($select=id,displayName,description,templateId,isBuiltIn)",
        }

        assignments: list[RoleAssignment] = []
        current_endpoint = endpoint

        while current_endpoint:
            data = await self._request("GET", current_endpoint, params)
            items = data.get("value", [])

            for assignment in items:
                principal = assignment.get("principal", {})
                role_def = assignment.get("roleDefinition", {})

                # Determine principal type and name
                principal_type = principal.get("@odata.type", "").replace("#microsoft.graph.", "")
                if "user" in principal_type.lower():
                    principal_type = "User"
                    display_name = principal.get("userPrincipalName") or principal.get(
                        "displayName", ""
                    )
                elif "servicePrincipal" in principal_type.lower():
                    principal_type = "ServicePrincipal"
                    display_name = principal.get("appId") or principal.get("displayName", "")
                elif "group" in principal_type.lower():
                    principal_type = "Group"
                    display_name = principal.get("displayName", "")
                else:
                    principal_type = "Unknown"
                    display_name = principal.get("displayName", "Unknown")

                # Determine scope (simplified for directory-scoped roles)
                scope_type = "Directory"
                scope_id = None

                # Check for scope information if available
                directory_scope = assignment.get("directoryScope", {})
                app_scope = assignment.get("appScope", {})

                if directory_scope:
                    scope_id = directory_scope.get("id")
                elif app_scope:
                    scope_type = "Application"
                    scope_id = app_scope.get("id")

                # Determine assignment type
                assignment_type = "Direct"
                if principal_type == "Group":
                    assignment_type = "Group"

                role_template_id = role_def.get("templateId", "")
                if isinstance(role_template_id, dict):
                    # Handle OData metadata issue
                    role_template_id = ""

                assignments.append(
                    RoleAssignment(
                        assignment_id=assignment.get("id", ""),
                        principal_id=principal.get("id", ""),
                        principal_type=principal_type,
                        principal_display_name=display_name,
                        role_definition_id=role_def.get("id", ""),
                        role_name=role_def.get("displayName", ""),
                        role_template_id=role_template_id,
                        scope_type=scope_type,
                        scope_id=scope_id,
                        created_date_time=assignment.get("createdDateTime"),
                        assignment_type=assignment_type,
                    )
                )

            # Handle pagination
            next_link = data.get("@odata.nextLink")
            if next_link:
                current_endpoint = next_link.replace(GRAPH_API_BASE, "")
                params = None
                await asyncio.sleep(0.1)  # Rate limiting between pages
            else:
                current_endpoint = None

        return assignments

    @circuit_breaker(GRAPH_API_BREAKER)
    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_pim_role_assignments(
        self,
        batch_size: int = 100,
        include_eligible: bool = True,
        include_active: bool = True,
    ) -> list[PrivilegedAccessAssignment]:
        """Get PIM (Privileged Identity Management) role assignments.

        Uses the beta API for PIM role assignment schedules.

        Args:
            batch_size: Number of assignments per page
            include_eligible: Include eligible (not yet activated) assignments
            include_active: Include currently active assignments

        Returns:
            List of PrivilegedAccessAssignment objects
        """
        assignments: list[PrivilegedAccessAssignment] = []

        # Get active assignments (beta endpoint)
        if include_active:
            active_assignments = await self._get_pim_assignments_by_type("active", batch_size)
            assignments.extend(active_assignments)

        # Get eligible assignments (beta endpoint)
        if include_eligible:
            eligible_assignments = await self._get_pim_assignments_by_type("eligible", batch_size)
            assignments.extend(eligible_assignments)

        return assignments

    async def _get_pim_assignments_by_type(
        self,
        assignment_type: str,
        batch_size: int,
    ) -> list[PrivilegedAccessAssignment]:
        """Helper to get PIM assignments of a specific type."""
        endpoint = f"/roleManagement/directory/roleAssignmentSchedules/{assignment_type}"
        params: dict[str, Any] = {
            "$top": min(batch_size, 999),
            "$expand": "principal($select=id,displayName,userPrincipalName,appId),roleDefinition($select=id,displayName,templateId)",
        }

        assignments: list[PrivilegedAccessAssignment] = []
        current_endpoint = endpoint

        while current_endpoint:
            try:
                # Use beta API for PIM
                token = await self._get_token()
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                }

                async with httpx.AsyncClient() as client:
                    url = f"{GRAPH_BETA_API_BASE}{current_endpoint}"
                    response = await client.request(
                        method="GET",
                        url=url,
                        headers=headers,
                        params=params,
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    data = response.json()

            except Exception as e:
                logger.warning(f"PIM {assignment_type} assignments query failed: {e}")
                break

            items = data.get("value", [])

            for assignment in items:
                principal = assignment.get("principal", {})
                role_def = assignment.get("roleDefinition", {})

                # Determine principal type
                principal_type = principal.get("@odata.type", "").replace("#microsoft.graph.", "")
                if "user" in principal_type.lower():
                    principal_type = "User"
                    display_name = principal.get("userPrincipalName") or principal.get(
                        "displayName", ""
                    )
                elif "servicePrincipal" in principal_type.lower():
                    principal_type = "ServicePrincipal"
                    display_name = principal.get("appId") or principal.get("displayName", "")
                elif "group" in principal_type.lower():
                    principal_type = "Group"
                    display_name = principal.get("displayName", "")
                else:
                    principal_type = "Unknown"
                    display_name = principal.get("displayName", "Unknown")

                # Calculate duration from start/end times
                start_time = assignment.get("startDateTime")
                end_time = assignment.get("endDateTime")
                duration = None
                if start_time and end_time:
                    try:
                        from datetime import datetime

                        start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                        end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                        duration = str(end - start)
                    except Exception:
                        duration = None

                assignments.append(
                    PrivilegedAccessAssignment(
                        assignment_id=assignment.get("id", ""),
                        principal_id=principal.get("id", ""),
                        principal_type=principal_type,
                        principal_display_name=display_name,
                        role_definition_id=role_def.get("id", ""),
                        role_name=role_def.get("displayName", ""),
                        assignment_state=assignment_type,
                        start_date_time=start_time,
                        end_date_time=end_time,
                        duration=duration,
                    )
                )

            # Handle pagination
            next_link = data.get("@odata.nextLink")
            if next_link:
                current_endpoint = next_link.replace(GRAPH_BETA_API_BASE, "")
                params = None
                await asyncio.sleep(0.1)
            else:
                current_endpoint = None

        return assignments

    @circuit_breaker(GRAPH_API_BREAKER)
    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_service_principal_role_assignments(
        self,
        batch_size: int = 100,
    ) -> list[RoleAssignment]:
        """Get role assignments specifically for service principals.

        Retrieves service principals with admin role assignments.

        Args:
            batch_size: Number of assignments per page

        Returns:
            List of RoleAssignment objects for service principals
        """
        # Get all role assignments and filter for service principals
        all_assignments = await self.get_role_assignments_paginated(batch_size)
        return [a for a in all_assignments if a.principal_type == "ServicePrincipal"]

    async def get_admin_role_summary(
        self,
        batch_size: int = 100,
    ) -> AdminRoleSummary:
        """Get comprehensive summary of admin roles in the tenant.

        Aggregates directory roles, role assignments, and PIM data to provide
        a complete picture of privileged access.

        Args:
            batch_size: Number of items per page for paginated queries

        Returns:
            AdminRoleSummary with complete admin role statistics
        """
        # Get role definitions
        role_defs = await self.get_directory_role_definitions()
        {r.role_id: r for r in role_defs}

        # Get all role assignments
        assignments = await self.get_role_assignments_paginated(batch_size)

        # Get PIM assignments
        try:
            pim_assignments = await self.get_pim_role_assignments(batch_size)
        except Exception as e:
            logger.warning(f"Failed to get PIM assignments: {e}")
            pim_assignments = []

        # Categorize by admin type
        privileged_users: list[dict[str, Any]] = []
        privileged_sps: list[dict[str, Any]] = []
        roles_with_members: set[str] = set()

        global_admin_count = 0
        security_admin_count = 0
        privileged_role_admin_count = 0
        other_admin_count = 0

        for assignment in assignments:
            role_template_id = assignment.role_template_id
            is_privileged = role_template_id in ADMIN_ROLE_TEMPLATE_IDS

            if not is_privileged:
                continue

            roles_with_members.add(assignment.role_definition_id)

            # Count by admin type
            if role_template_id == "62e90394-69f5-4237-9190-012177145e10":
                global_admin_count += 1
            elif role_template_id == "194ae4cb-b126-40b2-bd5b-6091b380977d":
                security_admin_count += 1
            elif role_template_id == "e8611ab8-c189-46e8-94e1-60213ab1f814":
                privileged_role_admin_count += 1
            else:
                other_admin_count += 1

            # Build user/SP lists
            if assignment.principal_type == "User":
                privileged_users.append(
                    {
                        "principal_id": assignment.principal_id,
                        "principal_display_name": assignment.principal_display_name,
                        "role_name": assignment.role_name,
                        "role_template_id": role_template_id,
                        "scope_type": assignment.scope_type,
                        "is_permanent": assignment.assignment_type == "Direct",
                    }
                )
            elif assignment.principal_type == "ServicePrincipal":
                privileged_sps.append(
                    {
                        "principal_id": assignment.principal_id,
                        "principal_display_name": assignment.principal_display_name,
                        "role_name": assignment.role_name,
                        "role_template_id": role_template_id,
                    }
                )

        # Find roles without members
        all_role_ids = {r.role_id for r in role_defs if r.is_built_in}
        roles_without_members = list(all_role_ids - roles_with_members)

        # Format PIM assignments
        formatted_pim = [
            {
                "principal_id": p.principal_id,
                "principal_display_name": p.principal_display_name,
                "principal_type": p.principal_type,
                "role_name": p.role_name,
                "assignment_state": p.assignment_state,
                "start_date_time": p.start_date_time,
                "end_date_time": p.end_date_time,
                "duration": p.duration,
            }
            for p in pim_assignments
        ]

        return AdminRoleSummary(
            tenant_id=self.tenant_id,
            total_roles=len(role_defs),
            total_assignments=len(assignments),
            privileged_users=privileged_users,
            privileged_service_principals=privileged_sps,
            pim_assignments=formatted_pim,
            roles_without_members=roles_without_members,
            global_admin_count=global_admin_count,
            security_admin_count=security_admin_count,
            privileged_role_admin_count=privileged_role_admin_count,
            other_admin_count=other_admin_count,
        )

    @circuit_breaker(GRAPH_API_BREAKER)
    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_conditional_access_policies(self) -> list[dict]:
        """Get conditional access policies."""
        endpoint = "/identity/conditionalAccess/policies"
        data = await self._request("GET", endpoint)
        return data.get("value", [])

    @circuit_breaker(GRAPH_API_BREAKER)
    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_mfa_status(self) -> dict:
        """Get MFA registration status."""
        # This requires Reports.Read.All permission
        endpoint = "/reports/authenticationMethods/userRegistrationDetails"
        data = await self._request("GET", endpoint)
        return data

    @circuit_breaker(GRAPH_API_BREAKER)
    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_service_principals(self) -> list[dict]:
        """Get service principals."""
        endpoint = "/servicePrincipals"
        params = {
            "$top": 999,
            "$select": "id,displayName,appId,servicePrincipalType,accountEnabled,createdDateTime",
        }
        data = await self._request("GET", endpoint, params)
        return data.get("value", [])

    # ==========================================================================
    # MFA Data Collection Methods
    # ==========================================================================

    @circuit_breaker(GRAPH_API_BREAKER)
    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_user_auth_methods(self, user_id: str) -> list[dict]:
        """Get authentication methods for a specific user.

        Retrieves all registered authentication methods for a user including:
        - Microsoft Authenticator app
        - Phone (SMS/call)
        - Email
        - FIDO2 security keys
        - Windows Hello
        - Hardware tokens
        - Temporary Access Pass

        Args:
            user_id: The Azure AD user ID (GUID)

        Returns:
            List of authentication method dictionaries

        Raises:
            MFAError: If authentication methods cannot be retrieved
        """
        try:
            endpoint = f"/users/{user_id}/authentication/methods"
            data = await self._request("GET", endpoint)
            return data.get("value", [])
        except Exception as e:
            logger.error(f"Failed to get auth methods for user {user_id}: {e}")
            raise MFAError(f"Failed to get auth methods: {e}", user_id) from e

    @circuit_breaker(GRAPH_API_BREAKER)
    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_user_mfa_details(self, user_id: str) -> UserMFAStatus | None:
        """Get detailed MFA status for a specific user.

        Fetches user information and their authentication methods to build
        a complete picture of their MFA registration status.

        Args:
            user_id: The Azure AD user ID (GUID)

        Returns:
            UserMFAStatus object with complete MFA details, or None if user not found

        Raises:
            MFAError: If MFA details cannot be retrieved
        """
        try:
            # Get user basic info
            user_endpoint = f"/users/{user_id}"
            user_params = {"$select": "id,displayName,userPrincipalName,signInActivity"}
            user_data = await self._request("GET", user_endpoint, user_params)

            if not user_data:
                return None

            # Get authentication methods
            auth_methods = await self.get_user_auth_methods(user_id)

            # Parse authentication methods
            parsed_methods: list[MFAMethodDetails] = []
            methods_registered: list[str] = []
            default_method: str | None = None

            for method in auth_methods:
                method_type = method.get("@odata.type", "").replace("#microsoft.graph.", "")
                is_default = method.get("isDefault", False)
                is_enabled = method.get("isEnabled", True)

                method_details = MFAMethodDetails(
                    method_type=method_type,
                    is_default=is_default,
                    is_enabled=is_enabled,
                )

                # Extract method-specific details
                if "phoneAuthenticationMethod" in method_type:
                    method_details.phone_number = method.get("phoneNumber")
                    method_details.display_name = method.get("phoneType", "Phone")
                    methods_registered.append("phone")
                elif "emailAuthenticationMethod" in method_type:
                    method_details.email_address = method.get("emailAddress")
                    methods_registered.append("email")
                elif "microsoftAuthenticatorAuthenticationMethod" in method_type:
                    method_details.display_name = method.get(
                        "displayName", "Microsoft Authenticator"
                    )
                    method_details.app_id = method.get("authenticatorAppId")
                    methods_registered.append("microsoftAuthenticator")
                elif "fido2AuthenticationMethod" in method_type:
                    method_details.display_name = method.get("model", "FIDO2 Security Key")
                    methods_registered.append("fido2")
                elif "windowsHelloForBusinessAuthenticationMethod" in method_type:
                    method_details.display_name = method.get("displayName", "Windows Hello")
                    methods_registered.append("windowsHello")
                elif "softwareOathAuthenticationMethod" in method_type:
                    method_details.display_name = method.get("displayName", "Hardware Token")
                    methods_registered.append("softwareOath")
                elif "temporaryAccessPassAuthenticationMethod" in method_type:
                    method_details.display_name = "Temporary Access Pass"
                    methods_registered.append("temporaryAccessPass")

                parsed_methods.append(method_details)

                if is_default:
                    default_method = method_type

            # Determine if MFA is registered
            # MFA is considered registered if user has at least one non-password method
            non_password_methods = [m for m in methods_registered if m != "password"]
            is_mfa_registered = len(non_password_methods) > 0

            return UserMFAStatus(
                user_id=user_id,
                user_principal_name=user_data.get("userPrincipalName", ""),
                display_name=user_data.get("displayName", ""),
                is_mfa_registered=is_mfa_registered,
                methods_registered=list(set(methods_registered)),
                auth_methods=parsed_methods,
                default_method=default_method,
                last_updated=user_data.get("signInActivity", {}).get("lastSignInDateTime"),
            )

        except MFAError:
            raise
        except Exception as e:
            logger.error(f"Failed to get MFA details for user {user_id}: {e}")
            raise MFAError(f"Failed to get MFA details: {e}", user_id) from e

    @circuit_breaker(GRAPH_API_BREAKER)
    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_mfa_registration_details(
        self,
        filter_param: str | None = None,
    ) -> list[dict]:
        """Get MFA registration details for all users.

        Uses the reporting API to get credential user registration details.
        This endpoint requires Reports.Read.All permission.

        Args:
            filter_param: Optional OData filter string

        Returns:
            List of user MFA registration details
        """
        endpoint = "/reports/authenticationMethods/userRegistrationDetails"
        params: dict[str, Any] = {}
        if filter_param:
            params["$filter"] = filter_param

        data = await self._request("GET", endpoint, params)
        return data.get("value", [])

    @circuit_breaker(GRAPH_API_BREAKER)
    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_mfa_registration_details_paginated(
        self,
        batch_size: int = 100,
        filter_param: str | None = None,
    ) -> list[dict]:
        """Get MFA registration details with pagination support.

        Handles large user bases by paginating through results.
        Respects rate limits with built-in delays.

        Args:
            batch_size: Number of users per page (max 999)
            filter_param: Optional OData filter string

        Returns:
            List of all user MFA registration details
        """
        import asyncio

        all_registrations: list[dict] = []
        endpoint = "/reports/authenticationMethods/userRegistrationDetails"
        params: dict[str, Any] = {"$top": min(batch_size, 999)}
        if filter_param:
            params["$filter"] = filter_param

        while endpoint:
            try:
                data = await self._request("GET", endpoint, params)
                registrations = data.get("value", [])
                all_registrations.extend(registrations)

                logger.debug(f"Retrieved {len(registrations)} MFA registration records")

                # Handle pagination
                next_link = data.get("@odata.nextLink")
                if next_link:
                    endpoint = next_link.replace(GRAPH_API_BASE, "")
                    params = None
                    # Rate limiting compliance - small delay between pages
                    await asyncio.sleep(0.1)
                else:
                    endpoint = None

            except Exception as e:
                logger.error(f"Error fetching MFA registration details: {e}")
                raise

        logger.info(f"Retrieved total of {len(all_registrations)} MFA registration records")
        return all_registrations

    @circuit_breaker(GRAPH_API_BREAKER)
    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_tenant_mfa_summary(
        self,
        include_details: bool = False,
        batch_size: int = 100,
    ) -> TenantMFASummary:
        """Get comprehensive MFA summary for the tenant.

        Aggregates MFA data across all users to provide tenant-level statistics.

        Args:
            include_details: If True, include list of users without MFA
            batch_size: Number of users to process per batch

        Returns:
            TenantMFASummary with complete MFA statistics
        """
        import asyncio

        # Get all users with their admin status
        users = await self.get_users(top=batch_size)

        # Get directory roles for admin identification
        directory_roles = await self.get_directory_roles()

        # Build set of admin user IDs
        admin_user_ids: set[str] = set()
        for role in directory_roles:
            role_template_id = role.get("roleTemplateId", "")
            if role_template_id in ADMIN_ROLE_TEMPLATE_IDS:
                for member in role.get("members", []):
                    user_id = member.get("id")
                    if user_id:
                        admin_user_ids.add(user_id)

        # Get MFA registrations
        mfa_registrations = await self.get_mfa_registration_details_paginated(batch_size=batch_size)

        # Build registration lookup
        registration_lookup: dict[str, dict] = {
            reg.get("userPrincipalName", "").lower(): reg for reg in mfa_registrations
        }

        # Calculate statistics
        total_users = len(users)
        mfa_registered = 0
        admin_total = len(admin_user_ids)
        admin_mfa = 0
        method_breakdown: dict[str, int] = {}
        users_without_mfa: list[dict] = []

        for user in users:
            upn = user.get("userPrincipalName", "").lower()
            user_id = user.get("id", "")
            is_admin = user_id in admin_user_ids

            reg = registration_lookup.get(upn, {})
            is_mfa_registered = reg.get("isMfaRegistered", False)
            methods = reg.get("methodsRegistered", []) if reg else []

            if is_mfa_registered:
                mfa_registered += 1
                if is_admin:
                    admin_mfa += 1

                # Count methods
                for method in methods:
                    method_type = method.lower() if isinstance(method, str) else str(method)
                    method_breakdown[method_type] = method_breakdown.get(method_type, 0) + 1
            else:
                if include_details:
                    users_without_mfa.append(
                        {
                            "user_id": user_id,
                            "user_principal_name": upn,
                            "display_name": user.get("displayName", ""),
                            "is_admin": is_admin,
                        }
                    )

            # Rate limiting compliance
            await asyncio.sleep(0.01)

        # Calculate percentages
        mfa_coverage_pct = (mfa_registered / total_users * 100) if total_users > 0 else 0.0
        admin_mfa_pct = (admin_mfa / admin_total * 100) if admin_total > 0 else 0.0

        return TenantMFASummary(
            tenant_id=self.tenant_id,
            total_users=total_users,
            mfa_registered_users=mfa_registered,
            mfa_coverage_percentage=round(mfa_coverage_pct, 2),
            admin_accounts_total=admin_total,
            admin_accounts_mfa=admin_mfa,
            admin_mfa_percentage=round(admin_mfa_pct, 2),
            method_breakdown=method_breakdown,
            users_without_mfa=users_without_mfa,
        )

    @circuit_breaker(GRAPH_API_BREAKER)
    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_users_paginated(
        self,
        batch_size: int = 100,
        select_fields: list[str] | None = None,
        filter_param: str | None = None,
    ) -> list[dict]:
        """Get all users with pagination support.

        Handles large user bases by paginating through results.
        Gracefully degrades by stripping signInActivity if the tenant
        lacks Azure AD Premium (returns 403 for that property).

        Args:
            batch_size: Number of users per page (max 999)
            select_fields: Fields to select (defaults to standard fields)
            filter_param: Optional OData filter string

        Returns:
            List of all users
        """
        import asyncio

        all_users: list[dict] = []

        if select_fields is None:
            select_fields = [
                "id",
                "displayName",
                "userPrincipalName",
                "userType",
                "accountEnabled",
                "createdDateTime",
                "signInActivity",
            ]

        endpoint = "/users"
        params: dict[str, Any] = {
            "$top": min(batch_size, 999),
            "$select": ",".join(select_fields),
        }
        if filter_param:
            params["$filter"] = filter_param

        # First request — may fail with 403 if signInActivity needs
        # Azure AD Premium which the tenant lacks.
        try:
            data = await self._request("GET", endpoint, params)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403 and "signInActivity" in (params or {}).get(
                "$select", ""
            ):
                logger.warning(
                    "signInActivity requires Azure AD Premium for tenant %s — retrying without it",
                    self.tenant_id[:8],
                )
                fields_without_sign_in = [f for f in select_fields if f != "signInActivity"]
                params["$select"] = ",".join(fields_without_sign_in)
                data = await self._request("GET", endpoint, params)
            else:
                raise

        users = data.get("value", [])
        all_users.extend(users)

        # Handle remaining pages
        next_link = data.get("@odata.nextLink")
        while next_link:
            endpoint = next_link.replace(GRAPH_API_BASE, "")
            data = await self._request("GET", endpoint)
            all_users.extend(data.get("value", []))
            next_link = data.get("@odata.nextLink")
            await asyncio.sleep(0.1)

        return all_users

    @circuit_breaker(GRAPH_API_BREAKER)
    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_conditional_access_policies_with_details(self) -> list[dict]:
        """Get conditional access policies with detailed configuration.

        Retrieves CA policies including grant controls, conditions, and state.
        Useful for analyzing MFA enforcement policies.

        Returns:
            List of conditional access policies with full details
        """
        endpoint = "/identity/conditionalAccess/policies"
        params = {
            "$expand": "grantControls,conditions,locations",
        }
        data = await self._request("GET", endpoint, params)
        return data.get("value", [])

    @circuit_breaker(GRAPH_API_BREAKER)
    @retry_with_backoff(GRAPH_API_POLICY)
    async def get_sign_in_logs(
        self,
        filter_param: str | None = None,
        top: int = 100,
    ) -> list[dict]:
        """Get Azure AD sign-in logs.

        Requires AuditLog.Read.All and Directory.Read.All permissions.

        Args:
            filter_param: Optional OData filter string
            top: Number of records to retrieve

        Returns:
            List of sign-in log entries
        """
        endpoint = "/auditLogs/signIns"
        params: dict[str, Any] = {"$top": top}
        if filter_param:
            params["$filter"] = filter_param

        data = await self._request("GET", endpoint, params)
        return data.get("value", [])


# Admin role template IDs for identifying privileged users
ADMIN_ROLE_TEMPLATE_IDS = {
    "62e90394-69f5-4237-9190-012177145e10",  # Global Administrator
    "194ae4cb-b126-40b2-bd5b-6091b380977d",  # Security Administrator
    "f28a1f50-f6e7-4571-818b-6a12f2af6b6c",  # SharePoint Administrator
    "29232cdf-9323-42fd-ade2-1d097af3e4de",  # Exchange Administrator
    "b1be1c3e-b65d-4f19-8427-f6fa0d9feb5c",  # Conditional Access Administrator
    "729827e3-9c14-49f7-bb1b-9608f156bbb8",  # Helpdesk Administrator
    "966707d0-3269-4727-9be2-8c3a10f19b9d",  # Password Administrator
    "7be44c8a-adaf-4e2a-84d6-ab2649e08a13",  # Privileged Authentication Administrator
    "e8611ab8-c189-46e8-94e1-60213ab1f814",  # Privileged Role Administrator
    "fe930be7-5e62-47db-91af-98c3a49a38b1",  # User Administrator
    "a9ea8996-122f-4c74-9520-b03e91a63c5a",  # Application Administrator
    "3edaf663-341e-4475-9f94-5c398ef6c070",  # Cloud Application Administrator
}
