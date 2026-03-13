"""Recommendation database models."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped

from app.core.database import Base


class Recommendation(Base):
    """Optimization and governance recommendations."""

    __tablename__ = "recommendations"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = Column(String(36), ForeignKey("tenants.id"), nullable=True)
    subscription_id: Mapped[str | None] = Column(String(36))
    category: Mapped[str] = Column(
        String(50), nullable=False
    )  # cost_optimization, security, performance, reliability
    recommendation_type: Mapped[str] = Column(
        String(100), nullable=False
    )  # e.g., "idle_vm", "unencrypted_storage"
    title: Mapped[str] = Column(String(255), nullable=False)
    description: Mapped[str] = Column(Text, nullable=False)
    impact: Mapped[str] = Column(String(20), default="Medium")  # Low, Medium, High, Critical
    potential_savings_monthly: Mapped[float | None] = Column(Float)
    potential_savings_annual: Mapped[float | None] = Column(Float)
    resource_id: Mapped[str | None] = Column(String(500))
    resource_name: Mapped[str | None] = Column(String(255))
    resource_type: Mapped[str | None] = Column(String(255))
    current_state: Mapped[str | None] = Column(Text)  # JSON blob of current config
    recommended_state: Mapped[str | None] = Column(Text)  # JSON blob of recommended config
    implementation_effort: Mapped[str] = Column(String(20), default="Medium")  # Low, Medium, High
    is_dismissed: Mapped[int] = Column(Integer, default=0)  # SQLite bool
    dismissed_by: Mapped[str | None] = Column(String(255))
    dismissed_at: Mapped[datetime | None] = Column(DateTime)
    dismiss_reason: Mapped[str | None] = Column(Text)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Recommendation {self.category}/{self.recommendation_type}: {self.title}>"
