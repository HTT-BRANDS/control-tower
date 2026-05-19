"""Core mixin for GraphClient: auth + HTTP + users + conditional access.

Split from the monolithic graph_client.py (issue 6oj7, 2026-04-22).
This class owns __init__ and state; the other mixins rely on the
attributes (self.tenant_id, self._token, self._credential) it sets up.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from azure.core.credentials import TokenCredential
from azure.identity import ClientSecretCredential

from app.api.services.graph_client._constants import (
    GRAPH_API_BASE,
    GRAPH_SCOPES,
)
from app.core.circuit_breaker import GRAPH_API_BREAKER, circuit_breaker
from app.core.config import get_settings
from app.core.retry import GRAPH_API_POLICY, retry_with_backoff

logger = logging.getLogger(__name__)
settings = get_settings()


class _GraphClientCore:
    """Core: authentication, HTTP primitives, user/CA/sign-in queries."""

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self._token: str | None = None
        self._credential: TokenCredential | None = None

    def _get_credential(self) -> TokenCredential:
        """Get or create credential for this tenant.

        Delegates zero-secret modes to ``AzureClientManager``:

        * **UAMI mode**: User-Assigned Managed Identity with federated assertion.
        * **OIDC mode**: App Service Managed Identity with federated assertion.
        * **Secret mode**: resolves ``client_id`` / ``client_secret`` via env vars,
          Key Vault, or settings fallback through ``AzureClientManager``.
        """
        if not self._credential:
            if settings.use_uami_auth or settings.use_oidc_federation:
                # Delegate zero-secret modes to the global singleton so clear_cache()
                # remains effective and TTL caching is shared across all callers.
                from app.api.services.azure_client import azure_client_manager

                self._credential = azure_client_manager.get_credential(self.tenant_id)
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
    async def get_conditional_access_policies(self) -> list[dict]:
        """Get conditional access policies."""
        endpoint = "/identity/conditionalAccess/policies"
        data = await self._request("GET", endpoint)
        return data.get("value", [])

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
