"""Per-user license tracking service using Microsoft Graph API.

Fetches license assignment data from:
- ``GET /users/{id}/licenseDetails``      – per-user SKU + service plan details
- ``GET /users``                           – paginated user list with assignedLicenses
- ``GET /subscribedSkus``                  – tenant SKU catalogue for name enrichment

Follows the same ``GraphClient`` pattern used throughout
``app/api/services/`` (see ``azure_ad_admin_service.py`` for the
canonical reference).

Graph permissions required (app-only):
    - ``User.Read.All``
    - ``Directory.Read.All``
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.api.services.graph_client import GRAPH_API_BASE, GraphClient
from app.schemas.license import ServicePlanDetail, UserLicense, UserLicenseSummary

logger = logging.getLogger(__name__)


class LicenseServiceError(Exception):
    """Raised when a license service operation fails."""

    def __init__(self, message: str, tenant_id: str | None = None, status_code: int | None = None) -> None:
        super().__init__(message)
        self.tenant_id = tenant_id
        self.status_code = status_code


class LicenseService:
    """Service for per-user Microsoft 365 license tracking.

    Creates one ``GraphClient`` per tenant (lazy) and exposes two
    high-level methods:

    * ``get_user_licenses``  – full SKU + service plan details for a user
    * ``list_tenant_licenses`` – cost-efficient enumeration of *all* licensed
      users in the tenant using the ``assignedLicenses`` field on the ``/users``
      endpoint, enriched with SKU part numbers from ``/subscribedSkus``.

    Example::

        svc = LicenseService()

        # Per-user detail
        licenses = await svc.get_user_licenses(
            tenant_id="contoso.onmicrosoft.com",
            user_id="<azure-ad-object-id>",
        )

        # Tenant-wide summary
        summaries = await svc.list_tenant_licenses("contoso.onmicrosoft.com")
    """

    # Pagination page size for /users listing (Graph maximum is 999;
    # 100 keeps memory pressure low and matches Graph's default for
    # /users/{id}/licenseDetails).
    _PAGE_SIZE = 100
    # Brief sleep between paginated pages to respect Graph rate limits.
    _PAGE_SLEEP_SECONDS = 0.05

    def __init__(self) -> None:
        self._clients: dict[str, GraphClient] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self, tenant_id: str) -> GraphClient:
        """Return (or lazily create) the ``GraphClient`` for *tenant_id*."""
        if tenant_id not in self._clients:
            self._clients[tenant_id] = GraphClient(tenant_id)
        return self._clients[tenant_id]

    async def _paginate(
        self,
        client: GraphClient,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Exhaust a paginated Graph API endpoint and return all items.

        Handles ``@odata.nextLink`` pagination transparently.  Sleeps
        ``_PAGE_SLEEP_SECONDS`` between pages to respect rate limits.

        Args:
            client:   Initialised ``GraphClient`` for the target tenant.
            endpoint: Initial path relative to ``GRAPH_API_BASE``, e.g.
                      ``"/users"`` or ``"/users/{id}/licenseDetails"``.
            params:   Optional OData query params for the *first* page.

        Returns:
            Flat list of all ``value`` items across all pages.

        Raises:
            LicenseServiceError: On 401, 404, or 429 HTTP errors from Graph.
            httpx.HTTPStatusError: For other unexpected HTTP errors.
        """
        items: list[dict[str, Any]] = []
        current_endpoint: str | None = endpoint
        current_params = params

        while current_endpoint is not None:
            try:
                data = await client._request("GET", current_endpoint, current_params)
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status == 401:
                    raise LicenseServiceError(
                        "Unauthorized — check Graph API permissions for tenant (HTTP 401)",
                        status_code=401,
                    ) from exc
                if status == 404:
                    # User / resource not found — return empty rather than exploding.
                    logger.warning("Graph API returned 404 for %s", current_endpoint)
                    return items
                if status == 429:
                    retry_after = int(exc.response.headers.get("Retry-After", "5"))
                    raise LicenseServiceError(
                        f"Graph API rate limit hit (HTTP 429); retry after {retry_after}s",
                        status_code=429,
                    ) from exc
                raise

            items.extend(data.get("value", []))

            next_link: str | None = data.get("@odata.nextLink")
            if next_link:
                # Strip the base URL — _request prepends it again.
                current_endpoint = next_link.replace(GRAPH_API_BASE, "")
                current_params = None  # next_link already encodes params
                await asyncio.sleep(self._PAGE_SLEEP_SECONDS)
            else:
                current_endpoint = None

        return items

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_user_licenses(
        self,
        tenant_id: str,
        user_id: str,
    ) -> list[UserLicense]:
        """Fetch full license details for a single user.

        Calls:
        * ``GET /users/{user_id}?$select=id,displayName,userPrincipalName``
        * ``GET /users/{user_id}/licenseDetails`` (paginated)

        Args:
            tenant_id: Azure AD tenant ID or domain.
            user_id:   Azure AD object ID of the user.

        Returns:
            List of ``UserLicense`` objects — one per assigned SKU.  Returns
            an empty list if the user has no license assignments.

        Raises:
            LicenseServiceError: On 401 (auth) or 429 (rate limit) responses.
        """
        client = self._get_client(tenant_id)

        # Fetch identity fields (display name, UPN) for the user.
        try:
            user_data: dict[str, Any] = await client._request(
                "GET",
                f"/users/{user_id}",
                {"$select": "id,displayName,userPrincipalName"},
            )
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 404:
                logger.warning("User %s not found in tenant %s", user_id, tenant_id)
                return []
            if status == 401:
                raise LicenseServiceError(
                    "Unauthorized — check Graph API permissions (HTTP 401)",
                    tenant_id=tenant_id,
                    status_code=401,
                ) from exc
            if status == 429:
                retry_after = int(exc.response.headers.get("Retry-After", "5"))
                raise LicenseServiceError(
                    f"Graph API rate limit hit (HTTP 429); retry after {retry_after}s",
                    tenant_id=tenant_id,
                    status_code=429,
                ) from exc
            raise

        user_principal_name: str = user_data.get("userPrincipalName", "")
        display_name: str = user_data.get("displayName", "")

        # Fetch license details (may be paginated, though rare for a single user).
        raw_licenses = await self._paginate(
            client,
            f"/users/{user_id}/licenseDetails",
            {"$select": "id,skuId,skuPartNumber,servicePlans"},
        )

        licenses: list[UserLicense] = []
        for item in raw_licenses:
            service_plans = [
                ServicePlanDetail(
                    service_plan_id=sp.get("servicePlanId", ""),
                    service_plan_name=sp.get("servicePlanName", ""),
                    provisioning_status=sp.get("provisioningStatus", ""),
                    applies_to=sp.get("appliesTo", "User"),
                )
                for sp in item.get("servicePlans", [])
            ]
            licenses.append(
                UserLicense(
                    user_id=user_id,
                    user_principal_name=user_principal_name,
                    display_name=display_name,
                    sku_id=item.get("skuId", ""),
                    sku_part_number=item.get("skuPartNumber", ""),
                    service_plans=service_plans,
                )
            )

        logger.debug(
            "Fetched %d license(s) for user %s in tenant %s",
            len(licenses),
            user_id,
            tenant_id,
        )
        return licenses

    async def list_tenant_licenses(
        self,
        tenant_id: str,
    ) -> list[UserLicenseSummary]:
        """List all user license assignments across the tenant.

        Uses a two-step, cost-efficient approach:
        1. Fetch tenant SKU catalogue (``GET /subscribedSkus``) to build
           a ``skuId → skuPartNumber`` mapping.
        2. Enumerate users with ``assignedLicenses`` via paginated
           ``GET /users?$select=id,displayName,userPrincipalName,assignedLicenses``,
           skipping users with no licenses.

        This avoids ``N+1`` Graph calls (one per user) that would be required
        if we called ``/licenseDetails`` for every user.

        Args:
            tenant_id: Azure AD tenant ID or domain.

        Returns:
            List of ``UserLicenseSummary`` objects — one per licensed user.
            Returns an empty list if no users have licenses.

        Raises:
            LicenseServiceError: On 401 (auth) or 429 (rate limit) responses.
        """
        client = self._get_client(tenant_id)

        # Build skuId → skuPartNumber map from tenant-level SKU catalogue.
        try:
            sku_raw = await self._paginate(
                client,
                "/subscribedSkus",
                {"$select": "skuId,skuPartNumber"},
            )
        except LicenseServiceError:
            # Re-raise with tenant context.
            raise
        sku_map: dict[str, str] = {
            sku["skuId"]: sku.get("skuPartNumber", sku["skuId"])
            for sku in sku_raw
            if "skuId" in sku
        }

        logger.debug("Built SKU map with %d entries for tenant %s", len(sku_map), tenant_id)

        # Enumerate users with their assigned licenses.
        users_raw = await self._paginate(
            client,
            "/users",
            {
                "$select": "id,displayName,userPrincipalName,assignedLicenses",
                "$top": self._PAGE_SIZE,
            },
        )

        summaries: list[UserLicenseSummary] = []
        for user in users_raw:
            assigned: list[dict[str, Any]] = user.get("assignedLicenses", [])
            if not assigned:
                continue  # Skip unlicensed users.

            sku_ids = [lic.get("skuId", "") for lic in assigned if lic.get("skuId")]
            sku_part_numbers = [sku_map.get(sid, sid) for sid in sku_ids]

            summaries.append(
                UserLicenseSummary(
                    tenant_id=tenant_id,
                    user_id=user.get("id", ""),
                    user_principal_name=user.get("userPrincipalName", ""),
                    display_name=user.get("displayName", ""),
                    assigned_sku_ids=sku_ids,
                    assigned_sku_part_numbers=sku_part_numbers,
                    license_count=len(sku_ids),
                )
            )

        logger.info(
            "Tenant %s: found %d licensed user(s) out of %d total",
            tenant_id,
            len(summaries),
            len(users_raw),
        )
        return summaries


# Module-level singleton — mirrors the ``azure_ad_admin_service`` pattern.
license_service = LicenseService()
