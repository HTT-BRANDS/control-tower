"""Compliance-related database models."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped

from app.core.database import Base


class ComplianceSnapshot(Base):
    """Compliance score snapshot per subscription."""

    __tablename__ = "compliance_snapshots"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    subscription_id: Mapped[str] = Column(String(36), nullable=False)
    snapshot_date: Mapped[datetime] = Column(DateTime, nullable=False)
    overall_compliance_percent: Mapped[float] = Column(Float, default=0.0)
    secure_score: Mapped[float | None] = Column(Float)
    compliant_resources: Mapped[int] = Column(Integer, default=0)
    non_compliant_resources: Mapped[int] = Column(Integer, default=0)
    exempt_resources: Mapped[int] = Column(Integer, default=0)
    synced_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ComplianceSnapshot {self.snapshot_date}: {self.overall_compliance_percent:.1f}%>"


class PolicyState(Base):
    """Individual policy compliance state."""

    __tablename__ = "policy_states"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    subscription_id: Mapped[str] = Column(String(36), nullable=False)
    policy_definition_id: Mapped[str] = Column(String(500), nullable=False)
    policy_name: Mapped[str] = Column(String(255), nullable=False)
    policy_category: Mapped[str | None] = Column(String(100))
    compliance_state: Mapped[str] = Column(
        String(50), nullable=False
    )  # Compliant, NonCompliant, Exempt
    non_compliant_count: Mapped[int] = Column(Integer, default=0)
    resource_id: Mapped[str | None] = Column(Text)  # Affected resource
    recommendation: Mapped[str | None] = Column(Text)
    synced_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<PolicyState {self.policy_name}: {self.compliance_state}>"
