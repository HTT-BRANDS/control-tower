"""DMARC/DKIM database models.

Database models for tracking email security configuration and compliance
for Riverside Company tenants with the July 8, 2026 compliance deadline.
"""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DMARCPolicy(PyEnum):
    """DMARC policy levels."""

    NONE = "none"
    QUARANTINE = "quarantine"
    REJECT = "reject"


class DMARCAlignment(PyEnum):
    """DMARC alignment modes."""

    RELAXED = "r"
    STRICT = "s"


class DMARCRecord(Base):
    """DMARC DNS record configuration.

    Tracks DMARC policy configuration for each domain across tenants.
    """

    __tablename__ = "dmarc_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    policy: Mapped[str] = mapped_column(String(20), nullable=False)  # none, quarantine, reject
    pct: Mapped[int] = mapped_column(Integer, default=100)  # percentage
    rua: Mapped[str | None] = mapped_column(String(500))  # Aggregate report URI
    ruf: Mapped[str | None] = mapped_column(String(500))  # Forensic report URI
    adkim: Mapped[str] = mapped_column(String(1), default="r")  # DKIM alignment
    aspf: Mapped[str] = mapped_column(String(1), default="r")  # SPF alignment
    fo: Mapped[str | None] = mapped_column(String(20))  # Failure reporting options
    rf: Mapped[str | None] = mapped_column(String(50))  # Report format
    ri: Mapped[int] = mapped_column(Integer, default=86400)  # Report interval
    sp: Mapped[str | None] = mapped_column(String(20))  # Subdomain policy
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    validation_errors: Mapped[str | None] = mapped_column(Text)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_dmarc_records_tenant_id", "tenant_id"),
        Index("ix_dmarc_records_domain", "domain"),
        Index("ix_dmarc_records_policy", "policy"),
        Index("ix_dmarc_records_synced_at", "synced_at"),
    )

    def __repr__(self) -> str:
        return f"<DMARCRecord {self.domain} policy={self.policy}>"

    @property
    def policy_score(self) -> int:
        """Calculate security score based on policy (0-100)."""
        scores = {
            "reject": 100,
            "quarantine": 75,
            "none": 25,
        }
        return scores.get(self.policy.lower(), 0)


class DKIMRecord(Base):
    """DKIM DNS record configuration.

    Tracks DKIM signing configuration and key rotation status.
    """

    __tablename__ = "dkim_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    selector: Mapped[str] = mapped_column(String(100), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    key_size: Mapped[int | None] = mapped_column(Integer)  # e.g., 2048, 4096
    key_type: Mapped[str | None] = mapped_column(String(20))  # RSA, Ed25519
    last_rotated: Mapped[datetime | None] = mapped_column(DateTime)
    next_rotation_due: Mapped[datetime | None] = mapped_column(DateTime)
    dns_record_value: Mapped[str | None] = mapped_column(Text)  # The DKIM public key
    is_aligned: Mapped[bool] = mapped_column(Boolean, default=False)  # DKIM-SIG alignment
    selector_status: Mapped[str] = mapped_column(
        String(50), default="unknown"
    )  # active, expired, pending
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_dkim_records_tenant_id", "tenant_id"),
        Index("ix_dkim_records_domain", "domain"),
        Index("ix_dkim_records_enabled", "is_enabled"),
        Index("ix_dkim_records_synced_at", "synced_at"),
    )

    def __repr__(self) -> str:
        status = "enabled" if self.is_enabled else "disabled"
        return f"<DKIMRecord {self.domain} selector={self.selector} {status}>"

    @property
    def days_since_rotation(self) -> int | None:
        """Days since last key rotation."""
        if not self.last_rotated:
            return None
        return (datetime.utcnow() - self.last_rotated).days

    @property
    def is_key_stale(self) -> bool:
        """Check if key needs rotation (>180 days)."""
        days = self.days_since_rotation
        if days is None:
            return True
        return days > 180


class DMARCReport(Base):
    """DMARC aggregate report data.

    Stores parsed DMARC aggregate reports showing authentication results.
    """

    __tablename__ = "dmarc_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    report_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    messages_total: Mapped[int] = mapped_column(Integer, default=0)
    messages_passed: Mapped[int] = mapped_column(Integer, default=0)
    messages_failed: Mapped[int] = mapped_column(Integer, default=0)
    pct_compliant: Mapped[float] = mapped_column(Float, default=0.0)
    # Authentication breakdown
    dkim_passed: Mapped[int] = mapped_column(Integer, default=0)
    dkim_failed: Mapped[int] = mapped_column(Integer, default=0)
    spf_passed: Mapped[int] = mapped_column(Integer, default=0)
    spf_failed: Mapped[int] = mapped_column(Integer, default=0)
    both_passed: Mapped[int] = mapped_column(Integer, default=0)
    both_failed: Mapped[int] = mapped_column(Integer, default=0)
    # Source data
    source_ip_count: Mapped[int] = mapped_column(Integer, default=0)
    source_domains: Mapped[str | None] = mapped_column(Text)  # JSON list
    # Report metadata
    reporter: Mapped[str | None] = mapped_column(String(255))  # Who sent the report
    report_id: Mapped[str | None] = mapped_column(String(100))
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_dmarc_reports_tenant_id", "tenant_id"),
        Index("ix_dmarc_reports_domain", "domain"),
        Index("ix_dmarc_reports_date", "report_date"),
        Index("ix_dmarc_reports_synced_at", "synced_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<DMARCReport {self.domain} "
            f"{self.pct_compliant:.1f}% compliant "
            f"({self.messages_passed}/{self.messages_total})>"
        )


class DMARCAlert(Base):
    """DMARC/DKIM security alerts.

    Tracks alerts for security issues like policy downgrades,
    key rotation failures, or authentication failures.
    """

    __tablename__ = "dmarc_alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    alert_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # policy_change, key_rotation, auth_failure, etc.
    severity: Mapped[str] = mapped_column(
        String(20), default="medium"
    )  # critical, high, medium, low
    domain: Mapped[str | None] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str | None] = mapped_column(Text)  # JSON additional data
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_by: Mapped[str | None] = mapped_column(String(255))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_dmarc_alerts_tenant_id", "tenant_id"),
        Index("ix_dmarc_alerts_type", "alert_type"),
        Index("ix_dmarc_alerts_severity", "severity"),
        Index("ix_dmarc_alerts_acknowledged", "is_acknowledged"),
        Index("ix_dmarc_alerts_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<DMARCAlert {self.alert_type} [{self.severity}] {self.domain}>"
