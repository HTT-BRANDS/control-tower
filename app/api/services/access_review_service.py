"""Access Review Facilitation service (IG-010).

Queries Microsoft Graph to identify privileged role assignments whose
principals have been inactive for >90 days, allows reviewers to create
review tasks, and supports approve/revoke actions.

Graph API calls used:
  GET  /roleManagement/directory/roleAssignments?$expand=principal,roleDefinition
  GET  /users/{id}/signInActivity           (requires AuditLog.Read.All)
  DELETE /roleManagement/directory/roleAssignments/{id}

Graph permissions required (app-only):
  - RoleManagement.Read.All
  - AuditLog.Read.All
  - RoleManagement.ReadWrite.Directory  (for revoke)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.api.services.graph_client import GRAPH_API_BASE, GraphClient
from app.schemas.access_review import AccessReview, ReviewAction, StaleAssignment

logger = logging.getLogger(__name__)

# Days of inactivity before a privileged assignment is considered stale.
STALE_THRESHOLD_DAYS = 90


class AccessReviewServiceError(Exception):
    """Raised when an access review operation fails."""

    def __init__(
        self,
        message: str,
        tenant_id: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.tenant_id = tenant_id
        self.status_code = status_code


class AccessReviewService:
    """Service for access review facilitation.

    Maintains an in-memory review store keyed by tenant_id → review_id.
    All Graph API interactions are done via ``GraphClient`` (one per tenant,
    lazily created) following the same pattern as ``LicenseService``.

    Example::

        svc = AccessReviewService()

        # Find stale privileged assignments
        stale = await svc.list_stale_assignments("contoso.onmicrosoft.com")

        # Create a review for the first stale one
        review = await svc.create_review("contoso.onmicrosoft.com", stale[0].assignment_id)

        # Revoke it
        resolved = await svc.take_action(
            "contoso.onmicrosoft.com", review.id, "revoke"
        )
    """

    def __init__(self) -> None:
        # tenant_id → {client}
        self._clients: dict[str, GraphClient] = {}
        # tenant_id → {review_id → AccessReview}
        self._reviews: dict[str, dict[str, AccessReview]] = {}
        # tenant_id → {assignment_id}  (already has a review)
        self._reviewed_assignments: dict[str, set[str]] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self, tenant_id: str) -> GraphClient:
        """Return (or lazily create) the GraphClient for *tenant_id*."""
        if tenant_id not in self._clients:
            self._clients[tenant_id] = GraphClient(tenant_id)
        return self._clients[tenant_id]

    def _review_store(self, tenant_id: str) -> dict[str, AccessReview]:
        """Return the review store for *tenant_id*, creating it if necessary."""
        if tenant_id not in self._reviews:
            self._reviews[tenant_id] = {}
        return self._reviews[tenant_id]

    def _reviewed_set(self, tenant_id: str) -> set[str]:
        """Return the set of already-reviewed assignment IDs for *tenant_id*."""
        if tenant_id not in self._reviewed_assignments:
            self._reviewed_assignments[tenant_id] = set()
        return self._reviewed_assignments[tenant_id]

    @staticmethod
    def _parse_graph_datetime(value: str | None) -> datetime | None:
        """Parse an ISO-8601 datetime string returned by Graph API."""
        if not value:
            return None
        # Graph returns e.g. "2024-01-15T10:30:00Z"
        value = value.rstrip("Z")
        try:
            return datetime.fromisoformat(value).replace(tzinfo=None)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _is_stale(last_sign_in: datetime | None) -> bool:
        """Return True if *last_sign_in* is None or older than STALE_THRESHOLD_DAYS."""
        if last_sign_in is None:
            return True
        threshold = datetime.utcnow() - timedelta(days=STALE_THRESHOLD_DAYS)
        return last_sign_in < threshold

    @staticmethod
    def _days_inactive(last_sign_in: datetime | None) -> int | None:
        """Return days since *last_sign_in*; None when last_sign_in is None (never signed in)."""
        if last_sign_in is None:
            return None
        delta = datetime.utcnow() - last_sign_in
        return max(0, delta.days)

    async def _get_sign_in_activity(
        self,
        client: GraphClient,
        user_id: str,
    ) -> datetime | None:
        """Fetch lastSignInDateTime for *user_id* from Graph signInActivity.

        Returns None if the user has never signed in or if the permission
        (AuditLog.Read.All) is not granted (403 → graceful degradation).

        Args:
            client:  GraphClient for the target tenant.
            user_id: Azure AD user object ID.

        Returns:
            Parsed datetime of last sign-in, or None.
        """
        try:
            data: dict[str, Any] = await client._request(
                "GET",
                f"/users/{user_id}",
                {"$select": "id,signInActivity"},
            )
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code == 403:
                # AuditLog.Read.All not granted — treat as unknown (→ stale)
                logger.warning(
                    "AuditLog.Read.All not granted for tenant %s; "
                    "treating user %s sign-in as unknown",
                    client.tenant_id,
                    user_id,
                )
                return None
            if code == 404:
                logger.warning("User %s not found in tenant %s", user_id, client.tenant_id)
                return None
            if code == 401:
                raise AccessReviewServiceError(
                    "Unauthorized — check Graph API permissions (HTTP 401)",
                    tenant_id=client.tenant_id,
                    status_code=401,
                ) from exc
            raise
        except Exception:
            # Any other error → treat as unknown (conservative = stale)
            logger.exception(
                "Unexpected error fetching signInActivity for user %s in tenant %s",
                user_id,
                client.tenant_id,
            )
            return None

        sign_in_activity: dict[str, Any] | None = data.get("signInActivity")
        if not sign_in_activity:
            return None
        return self._parse_graph_datetime(sign_in_activity.get("lastSignInDateTime"))

    async def _delete_assignment(self, client: GraphClient, assignment_id: str) -> None:
        """Delete a role assignment via Graph API.

        Graph returns 204 No Content on success.  We build the HTTP call
        directly to handle the empty response body (GraphClient._request
        calls response.json() which would fail on 204).

        Args:
            client:        GraphClient for the target tenant.
            assignment_id: Role assignment object ID to delete.

        Raises:
            AccessReviewServiceError: On 401/403 from Graph.
            httpx.HTTPStatusError:    For other unexpected errors.
        """
        token = await client._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        url = f"{GRAPH_API_BASE}/roleManagement/directory/roleAssignments/{assignment_id}"
        async with httpx.AsyncClient() as http_client:
            response = await http_client.delete(url, headers=headers, timeout=30.0)
            if response.status_code == 401:
                raise AccessReviewServiceError(
                    f"Unauthorized deleting assignment {assignment_id} (HTTP 401)",
                    tenant_id=client.tenant_id,
                    status_code=401,
                )
            if response.status_code == 403:
                raise AccessReviewServiceError(
                    "Forbidden — RoleManagement.ReadWrite.Directory required (HTTP 403)",
                    tenant_id=client.tenant_id,
                    status_code=403,
                )
            response.raise_for_status()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def list_stale_assignments(self, tenant_id: str) -> list[StaleAssignment]:
        """List privileged role assignments whose principals are inactive >90 days.

        Process:
        1. ``GET /roleManagement/directory/roleAssignments?$expand=principal,roleDefinition``
        2. For each *user* principal, fetch ``GET /users/{id}/signInActivity``.
        3. An assignment is stale if ``lastSignInDateTime`` is null OR >90 days ago.

        Args:
            tenant_id: Azure AD tenant ID.

        Returns:
            List of :class:`StaleAssignment` sorted by days_inactive descending.

        Raises:
            AccessReviewServiceError: On 401 / 403 from Graph.
        """
        client = self._get_client(tenant_id)

        try:
            raw_data: dict[str, Any] = await client._request(
                "GET",
                "/roleManagement/directory/roleAssignments",
                {"$expand": "principal,roleDefinition"},
            )
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code == 401:
                raise AccessReviewServiceError(
                    "Unauthorized — check Graph API permissions (HTTP 401)",
                    tenant_id=tenant_id,
                    status_code=401,
                ) from exc
            if code == 403:
                raise AccessReviewServiceError(
                    "Forbidden — RoleManagement.Read.All required (HTTP 403)",
                    tenant_id=tenant_id,
                    status_code=403,
                ) from exc
            raise

        assignments: list[dict[str, Any]] = raw_data.get("value", [])
        stale_results: list[StaleAssignment] = []

        # Filter to user principals only (skip service principals / groups)
        user_assignments = [
            a
            for a in assignments
            if "#microsoft.graph.user" in (a.get("principal") or {}).get("@odata.type", "").lower()
            and (a.get("principal") or {}).get("id")
        ]

        # Fetch all sign-in activity in parallel — O(n) concurrent instead of O(n) serial
        sign_in_times: list[datetime | None] = list(
            await asyncio.gather(
                *[
                    self._get_sign_in_activity(client, a["principal"]["id"])
                    for a in user_assignments
                ],
                return_exceptions=False,
            )
        )

        for assignment, last_sign_in in zip(user_assignments, sign_in_times, strict=True):
            principal: dict[str, Any] = assignment.get("principal") or {}
            role_def: dict[str, Any] = assignment.get("roleDefinition") or {}
            role_name: str = role_def.get("displayName", "Unknown Role")
            user_display_name: str = principal.get("displayName", "Unknown User")
            user_id: str = principal.get("id", "")
            assignment_id: str = assignment.get("id", "")

            if not self._is_stale(last_sign_in):
                continue

            stale_results.append(
                StaleAssignment(
                    assignment_id=assignment_id,
                    user_id=user_id,
                    user_display_name=user_display_name,
                    role_name=role_name,
                    last_sign_in=last_sign_in,
                    days_inactive=self._days_inactive(last_sign_in),
                )
            )

        stale_results.sort(key=lambda s: (s.days_inactive is None, -(s.days_inactive or 0)))
        logger.info(
            "Tenant %s: found %d stale privileged assignment(s) out of %d total",
            tenant_id,
            len(stale_results),
            len(assignments),
        )
        return stale_results

    async def create_review(
        self,
        tenant_id: str,
        assignment_id: str,
        user_id: str | None = None,
        user_display_name: str | None = None,
        role_name: str | None = None,
        days_inactive: int | None = None,
    ) -> AccessReview:
        """Create a pending access review for *assignment_id*.

        If a pending review already exists for this assignment, the
        existing review is returned (idempotent).

        Args:
            tenant_id:         Azure AD tenant ID.
            assignment_id:     Role assignment object ID to review.
            user_id:           Azure AD user object ID (for display context).
            user_display_name: User's display name (for display context).
            role_name:         Directory role name (for display context).
            days_inactive:     Days since last sign-in; None = never signed in.

        Returns:
            The (new or existing) :class:`AccessReview` in ``pending`` status.
        """
        store = self._review_store(tenant_id)
        reviewed = self._reviewed_set(tenant_id)

        # Idempotent — return existing pending review if present
        if assignment_id in reviewed:
            for review in store.values():
                if review.assignment_id == assignment_id and review.status == "pending":
                    return review

        review = AccessReview(
            assignment_id=assignment_id,
            tenant_id=tenant_id,
            status="pending",
            user_id=user_id,
            user_display_name=user_display_name,
            role_name=role_name,
            days_inactive=days_inactive,
        )
        store[review.id] = review
        reviewed.add(assignment_id)

        logger.info(
            "Created access review %s for assignment %s in tenant %s",
            review.id,
            assignment_id,
            tenant_id,
        )
        return review

    async def get_reviews(self, tenant_id: str) -> list[AccessReview]:
        """Return all access reviews for *tenant_id*.

        Args:
            tenant_id: Azure AD tenant ID.

        Returns:
            List of :class:`AccessReview` objects, sorted by created_at descending.
        """
        store = self._review_store(tenant_id)
        reviews = list(store.values())
        reviews.sort(key=lambda r: r.created_at, reverse=True)
        return reviews

    async def take_action(
        self,
        tenant_id: str,
        review_id: str,
        action: ReviewAction,
    ) -> AccessReview:
        """Approve or revoke an access review.

        - ``approve`` — marks the review resolved; the assignment is kept.
        - ``revoke``  — calls
          ``DELETE /roleManagement/directory/roleAssignments/{assignment_id}``
          and marks the review resolved.

        Args:
            tenant_id: Azure AD tenant ID.
            review_id: The review UUID.
            action:    ``"approve"`` or ``"revoke"``.

        Returns:
            The updated :class:`AccessReview`.

        Raises:
            KeyError:                  If *review_id* is not found.
            AccessReviewServiceError:  If the Graph delete call fails.
        """
        store = self._review_store(tenant_id)

        if review_id not in store:
            raise KeyError(f"Review {review_id!r} not found for tenant {tenant_id!r}")

        review = store[review_id]

        # Guard against double-action on already-resolved reviews
        if review.status != "pending":
            raise ValueError(f"Review {review_id!r} is already resolved (status={review.status!r})")

        if action == "revoke":
            client = self._get_client(tenant_id)
            await self._delete_assignment(client, review.assignment_id)
            review.status = "revoked"
        else:
            review.status = "approved"

        review.resolved_at = datetime.utcnow()
        store[review_id] = review

        logger.info(
            "Review %s for assignment %s in tenant %s → %s",
            review_id,
            review.assignment_id,
            tenant_id,
            review.status,
        )
        return review


# Module-level singleton — mirrors the license_service / azure_ad_admin_service pattern.
access_review_service = AccessReviewService()
