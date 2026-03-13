"""Riverside Company compliance tracking models.

Database models for tracking Riverside Company compliance requirements
with the July 8, 2026 deadline across HTT, BCC, FN, TLL tenants plus DCE standalone.
"""

from datetime import date, datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RequirementCategory(PyEnum):
    """Riverside compliance requirement categories."""

    IAM = "IAM"  # Identity and Access Management
    GS = "GS"  # Group Security
    DS = "DS"  # Domain Security


class RequirementPriority(PyEnum):
    """Riverside compliance requirement priorities."""

    P0 = "P0"  # Critical
    P1 = "P1"  # High
    P2 = "P2"  # Medium


class RequirementStatus(PyEnum):
    """Riverside compliance requirement statuses."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class RiversideCompliance(Base):
    """Main compliance tracking table for Riverside Company.

    Tracks overall compliance maturity and risk metrics across all
    Riverside tenants with the July 8, 2026 deadline.
    """

    __tablename__ = "riverside_compliance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    overall_maturity_score: Mapped[float] = mapped_column(default=0.0)
    target_maturity_score: Mapped[float] = mapped_column(default=3.0)
    deadline_date: Mapped[date] = mapped_column(Date, nullable=False)
    financial_risk: Mapped[str] = mapped_column(String(50), default="$4M")
    critical_gaps_count: Mapped[int] = mapped_column(Integer, default=0)
    requirements_completed: Mapped[int] = mapped_column(Integer, default=0)
    requirements_total: Mapped[int] = mapped_column(Integer, default=0)
    last_assessment_date: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Indexes for frequently queried fields
    __table_args__ = (
        Index("ix_riverside_compliance_tenant_id", "tenant_id"),
        Index("ix_riverside_compliance_deadline", "deadline_date"),
    )

    def __repr__(self) -> str:
        maturity = (
            f"{self.overall_maturity_score:.1f}"
            if self.overall_maturity_score is not None
            else "N/A"
        )
        target = (
            f"{self.target_maturity_score:.1f}" if self.target_maturity_score is not None else "N/A"
        )
        return f"<RiversideCompliance maturity={maturity} target={target}>"


class RiversideMFA(Base):
    """MFA enrollment tracking per tenant.

    Captures multi-factor authentication coverage metrics including
    admin account protection status.
    """

    __tablename__ = "riverside_mfa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    total_users: Mapped[int] = mapped_column(Integer, default=0)
    mfa_enrolled_users: Mapped[int] = mapped_column(Integer, default=0)
    mfa_coverage_percentage: Mapped[float] = mapped_column(default=0.0)
    admin_accounts_total: Mapped[int] = mapped_column(Integer, default=0)
    admin_accounts_mfa: Mapped[int] = mapped_column(Integer, default=0)
    admin_mfa_percentage: Mapped[float] = mapped_column(default=0.0)
    unprotected_users: Mapped[int] = mapped_column(Integer, default=0)
    snapshot_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Indexes for frequently queried fields
    __table_args__ = (
        Index("ix_riverside_mfa_tenant_id", "tenant_id"),
        Index("ix_riverside_mfa_snapshot_date", "snapshot_date"),
    )

    def __repr__(self) -> str:
        coverage = (
            f"{self.mfa_coverage_percentage:.1f}%"
            if self.mfa_coverage_percentage is not None
            else "N/A"
        )
        admin_mfa = (
            f"{self.admin_mfa_percentage:.1f}%" if self.admin_mfa_percentage is not None else "N/A"
        )
        return f"<RiversideMFA coverage={coverage} admin_mfa={admin_mfa}>"


class RiversideRequirement(Base):
    """Individual compliance requirements.

    Tracks specific compliance requirements with categories (IAM, GS, DS),
    priorities (P0, P1, P2), and status progression.
    """

    __tablename__ = "riverside_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    requirement_id: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # e.g., "RC-001", "RC-010"
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[RequirementCategory] = mapped_column(String(10), nullable=False)
    priority: Mapped[RequirementPriority] = mapped_column(String(10), nullable=False)
    status: Mapped[RequirementStatus] = mapped_column(
        String(20), nullable=False, default=RequirementStatus.NOT_STARTED
    )
    evidence_url: Mapped[str | None] = mapped_column(String(500))
    evidence_notes: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[date | None] = mapped_column(Date)
    completed_date: Mapped[date | None] = mapped_column(Date)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Indexes for frequently queried fields
    __table_args__ = (
        Index("ix_riverside_requirements_tenant_id", "tenant_id"),
        Index("ix_riverside_requirements_status", "status"),
        Index("ix_riverside_requirements_due_date", "due_date"),
        Index("ix_riverside_requirements_category", "category"),
        Index("ix_riverside_requirements_priority", "priority"),
    )

    def __repr__(self) -> str:
        return (
            f"<RiversideRequirement {self.requirement_id}: {self.title} "
            f"[{self.category.value}] ({self.status.value})>"
        )


class RiversideDeviceCompliance(Base):
    """Device compliance tracking.

    Tracks endpoint security metrics including MDM enrollment,
    EDR coverage, and encryption status.
    """

    __tablename__ = "riverside_device_compliance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    total_devices: Mapped[int] = mapped_column(Integer, default=0)
    mdm_enrolled: Mapped[int] = mapped_column(Integer, default=0)
    edr_covered: Mapped[int] = mapped_column(Integer, default=0)
    encrypted_devices: Mapped[int] = mapped_column(Integer, default=0)
    compliant_devices: Mapped[int] = mapped_column(Integer, default=0)
    compliance_percentage: Mapped[float] = mapped_column(default=0.0)
    snapshot_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Indexes for frequently queried fields
    __table_args__ = (
        Index("ix_riverside_device_compliance_tenant_id", "tenant_id"),
        Index("ix_riverside_device_compliance_snapshot", "snapshot_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<RiversideDeviceCompliance {self.compliance_percentage:.1f}% "
            f"({self.compliant_devices}/{self.total_devices})>"
        )


class RiversideThreatData(Base):
    """External threat metrics.

    Captures threat intelligence and security posture metrics
    including vulnerability counts and peer comparison data.
    """

    __tablename__ = "riverside_threat_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    threat_score: Mapped[float | None] = mapped_column()
    vulnerability_count: Mapped[int] = mapped_column(Integer, default=0)
    malicious_domain_alerts: Mapped[int] = mapped_column(Integer, default=0)
    peer_comparison_percentile: Mapped[int | None] = mapped_column(Integer)
    snapshot_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Indexes for frequently queried fields
    __table_args__ = (
        Index("ix_riverside_threat_data_tenant_id", "tenant_id"),
        Index("ix_riverside_threat_data_snapshot", "snapshot_date"),
    )

    def __repr__(self) -> str:
        score_str = f"{self.threat_score:.1f}" if self.threat_score is not None else "N/A"
        return f"<RiversideThreatData score={score_str} vulns={self.vulnerability_count}>"
