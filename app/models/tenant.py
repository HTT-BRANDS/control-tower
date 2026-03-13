"""Tenant and subscription models.

Includes tenant configuration, subscriptions, and user-tenant access mappings.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.brand import BrandConfig


class Tenant(Base):
    """Azure tenant configuration."""

    __tablename__ = "tenants"

    id: Mapped[str] = Column(String(36), primary_key=True)
    name: Mapped[str] = Column(String(255), nullable=False)
    tenant_id: Mapped[str] = Column(String(36), unique=True, nullable=False)
    client_id: Mapped[str | None] = Column(String(36))
    client_secret_ref: Mapped[str | None] = Column(String(500))  # Key Vault URI
    description: Mapped[str | None] = Column(Text)
    is_active: Mapped[bool] = Column(Boolean, default=True)
    use_lighthouse: Mapped[bool] = Column(Boolean, default=False)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="tenant", cascade="all, delete-orphan"
    )
    user_mappings: Mapped[list["UserTenant"]] = relationship(
        "UserTenant", back_populates="tenant", cascade="all, delete-orphan"
    )
    brand_config: Mapped["BrandConfig"] = relationship(
        "BrandConfig", back_populates="tenant", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tenant {self.name} ({self.tenant_id})>"


class Subscription(Base):
    """Azure subscription within a tenant."""

    __tablename__ = "subscriptions"

    id: Mapped[str] = Column(String(36), primary_key=True)
    tenant_ref: Mapped[str] = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    subscription_id: Mapped[str] = Column(String(36), nullable=False)
    display_name: Mapped[str] = Column(String(255), nullable=False)
    state: Mapped[str] = Column(String(50), default="Enabled")
    synced_at: Mapped[datetime | None] = Column(DateTime)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="subscriptions")

    def __repr__(self) -> str:
        return f"<Subscription {self.display_name} ({self.subscription_id})>"


class UserTenant(Base):
    """User-to-tenant access mapping.

    Tracks which users have access to which tenants and their permission level.
    """

    __tablename__ = "user_tenants"
    __table_args__ = (
        UniqueConstraint("user_id", "tenant_id", name="uq_user_tenant"),
        Index("idx_user_tenants_user_id", "user_id"),
        Index("idx_user_tenants_tenant_id", "tenant_id"),
    )

    id: Mapped[str] = Column(String(36), primary_key=True)
    user_id: Mapped[str] = Column(String(255), nullable=False, index=True)
    tenant_id: Mapped[str] = Column(String(36), ForeignKey("tenants.id"), nullable=False)

    # Permission level within this tenant
    role: Mapped[str] = Column(String(50), default="viewer")  # viewer, operator, admin

    # Access control
    is_active: Mapped[bool] = Column(Boolean, default=True)
    can_manage_resources: Mapped[bool] = Column(Boolean, default=False)
    can_view_costs: Mapped[bool] = Column(Boolean, default=True)
    can_manage_compliance: Mapped[bool] = Column(Boolean, default=False)

    # Metadata
    granted_by: Mapped[str | None] = Column(String(255))  # User who granted access
    granted_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = Column(DateTime)  # Optional expiration
    last_accessed_at: Mapped[datetime | None] = Column(DateTime)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="user_mappings")

    def __repr__(self) -> str:
        return f"<UserTenant user={self.user_id} tenant={self.tenant_id} role={self.role}>"

    def is_expired(self) -> bool:
        """Check if the access has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
