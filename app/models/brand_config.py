"""Brand configuration model for multi-tenant theme management.

Supports per-tenant brand color customization with WCAG-compliant
contrast validation and CSS variable generation.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class BrandConfig(Base):
    """Brand color configuration for a tenant.

    Stores brand colors (primary, secondary, accent) along with brand name.
    Supports WCAG contrast checking and CSS variable generation for theming.
    """

    __tablename__ = "brand_configs"
    __table_args__ = (
        Index("idx_brand_configs_tenant_id", "tenant_id"),
        Index("idx_brand_configs_brand_name", "brand_name"),
    )

    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = Column(
        String(36), ForeignKey("tenants.id"), nullable=False, unique=True
    )
    brand_name: Mapped[str] = Column(String(255), nullable=False)
    primary_color: Mapped[str] = Column(String(7), nullable=False)  # Hex format: #RRGGBB
    secondary_color: Mapped[str] = Column(String(7), nullable=False)  # Hex format: #RRGGBB
    accent_color: Mapped[str | None] = Column(String(7))  # Optional accent color

    # Design token extension columns (Phase 5, nullable for backward compat)
    brand_key: Mapped[str | None] = Column(String(50), nullable=True, index=True)
    heading_font: Mapped[str | None] = Column(String(100), nullable=True)
    body_font: Mapped[str | None] = Column(String(100), nullable=True)
    background_color: Mapped[str | None] = Column(String(7), nullable=True)
    text_color: Mapped[str | None] = Column(String(7), nullable=True)
    border_radius: Mapped[str | None] = Column(String(20), nullable=True)
    shadow_style: Mapped[str | None] = Column(String(20), nullable=True)  # soft|sharp|none
    logo_primary: Mapped[str | None] = Column(String(255), nullable=True)
    logo_white: Mapped[str | None] = Column(String(255), nullable=True)
    logo_icon: Mapped[str | None] = Column(String(255), nullable=True)
    gradient: Mapped[str | None] = Column(String(255), nullable=True)

    # Metadata
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationship
    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="brand_config")

    def __repr__(self) -> str:
        return f"<BrandConfig {self.brand_name} ({self.tenant_id})>"

    def to_dict(self) -> dict:
        """Convert brand config to dictionary."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "brand_name": self.brand_name,
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
            "accent_color": self.accent_color,
            "brand_key": self.brand_key,
            "heading_font": self.heading_font,
            "body_font": self.body_font,
            "background_color": self.background_color,
            "text_color": self.text_color,
            "border_radius": self.border_radius,
            "shadow_style": self.shadow_style,
            "logo_primary": self.logo_primary,
            "logo_white": self.logo_white,
            "logo_icon": self.logo_icon,
            "gradient": self.gradient,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
