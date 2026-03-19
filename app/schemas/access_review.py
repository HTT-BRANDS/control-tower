"""Pydantic schemas for Access Review Facilitation (IG-010).

Data models for:
- StaleAssignment  -- a privileged role assignment with no recent sign-in activity
- AccessReview     -- a review task created for a stale assignment
- ReviewAction     -- the action a reviewer can take (approve / revoke)
- ReviewActionRequest -- request body for the action endpoint
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

ReviewAction = Literal["approve", "revoke"]
ReviewStatus = Literal["pending", "approved", "revoked"]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class StaleAssignment(BaseModel):
    """A privileged role assignment flagged as stale.

    An assignment is stale when the assigned user has had no sign-in
    activity in the last 90 days, or has never signed in (null lastSignIn).
    """

    assignment_id: str = Field(
        description="Azure AD role assignment object ID",
    )
    user_id: str = Field(
        description="Azure AD user object ID",
    )
    user_display_name: str = Field(
        description="User's display name",
    )
    role_name: str = Field(
        description="Friendly name of the directory role",
    )
    last_sign_in: datetime | None = Field(
        default=None,
        description="Last sign-in timestamp; None means the user has never signed in",
    )
    days_inactive: int | None = Field(
        default=None,
        description="Days since last sign-in; None when user has never signed in",
    )


class AccessReview(BaseModel):
    """An access review task created for a stale privileged assignment."""

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique review ID (UUID)",
    )
    assignment_id: str = Field(
        description="The role assignment being reviewed",
    )
    tenant_id: str = Field(
        description="Azure AD tenant ID that owns this review",
    )
    status: ReviewStatus = Field(
        default="pending",
        description="Review status: pending | approved | revoked",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the review was created",
    )
    resolved_at: datetime | None = Field(
        default=None,
        description="When the review was resolved (approved or revoked)",
    )
    # User context -- populated from StaleAssignment at create time
    user_id: str | None = Field(
        default=None,
        description="Azure AD user object ID of the assigned principal",
    )
    user_display_name: str | None = Field(
        default=None,
        description="Display name of the assigned user",
    )
    role_name: str | None = Field(
        default=None,
        description="Friendly name of the directory role being reviewed",
    )
    days_inactive: int | None = Field(
        default=None,
        description="Days since the user last signed in; None means never signed in",
    )


class ReviewActionRequest(BaseModel):
    """Request body for POST /access-reviews/{review_id}/action."""

    action: ReviewAction = Field(
        description="Action to take: 'approve' (keep assignment) or 'revoke' (remove it)",
    )
