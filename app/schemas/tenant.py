"""Tenant-related Pydantic schemas.

Includes strict validation for UUID fields and security constraints.
"""

import re
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


def validate_uuid(v: str, field_name: str) -> str:
    """Validate UUID format (8-4-4-4-12 pattern)."""
    if v is None:
        return v

    uuid_pattern = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    if not re.match(uuid_pattern, v):
        raise ValueError(
            f"{field_name} must be a valid UUID (e.g., '12345678-1234-1234-1234-123456789abc')"
        )
    return v.lower()  # Normalize to lowercase


# Type alias for validated UUID fields
TenantIdField = Annotated[str, Field(..., min_length=36, max_length=36)]
UuidField = Annotated[str, Field(..., min_length=36, max_length=36)]


class TenantCreate(BaseModel):
    """Schema for creating a new tenant.

    SECURITY: All Azure IDs are validated as proper UUIDs.
    """

    name: str = Field(..., min_length=1, max_length=255, pattern=r"^[\w\s\-_.]+$")
    tenant_id: TenantIdField
    client_id: TenantIdField | None = None
    client_secret_ref: str | None = Field(None, max_length=500, pattern=r"^[\w\-_.]+$")
    description: str | None = Field(None, max_length=1000)
    use_lighthouse: bool = False

    @field_validator("tenant_id")
    @classmethod
    def validate_tenant_id(cls, v: str) -> str:
        return validate_uuid(v, "tenant_id")

    @field_validator("client_id")
    @classmethod
    def validate_client_id(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_uuid(v, "client_id")
        return v


class TenantUpdate(BaseModel):
    """Schema for updating a tenant.

    SECURITY: All Azure IDs are validated as proper UUIDs.
    """

    name: str | None = Field(None, min_length=1, max_length=255, pattern=r"^[\w\s\-_.]+$")
    client_id: str | None = Field(None, min_length=36, max_length=36)
    client_secret_ref: str | None = Field(None, max_length=500, pattern=r"^[\w\-_.]+$")
    description: str | None = Field(None, max_length=1000)
    is_active: bool | None = None
    use_lighthouse: bool | None = None

    @field_validator("client_id")
    @classmethod
    def validate_client_id(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_uuid(v, "client_id")
        return v


class TenantResponse(BaseModel):
    """Schema for tenant response."""

    id: UuidField
    name: str
    tenant_id: TenantIdField
    description: str | None = None
    is_active: bool
    use_lighthouse: bool
    subscription_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", "tenant_id", mode="before")
    @classmethod
    def validate_uuids(cls, v: str) -> str:
        return validate_uuid(v, "uuid_field")


class SubscriptionResponse(BaseModel):
    """Schema for subscription response."""

    id: UuidField
    subscription_id: TenantIdField  # Subscription IDs are also UUIDs
    display_name: str
    state: str
    tenant_id: str
    synced_at: datetime | None = None

    model_config = {"from_attributes": True}

    @field_validator("id", "subscription_id", mode="before")
    @classmethod
    def validate_uuids(cls, v: str) -> str:
        return validate_uuid(v, "uuid_field")


class TenantWithSubscriptions(TenantResponse):
    """Tenant response with subscriptions included."""

    subscriptions: list[SubscriptionResponse] = Field(default_factory=list)
