"""Cost-related database models."""

from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mssql import NVARCHAR as MSSQL_NVARCHAR
from sqlalchemy.orm import Mapped

from app.core.database import Base


def _nv(size: int) -> String:
    """String that renders as NVARCHAR on SQL Server, plain String elsewhere.

    SQLAlchemy's String() already maps to NVARCHAR on the mssql dialect,
    but being explicit prevents future VARCHAR/NVARCHAR mismatches that
    cause error 2628 in batch INSERT patterns.
    """
    return String(size).with_variant(MSSQL_NVARCHAR(size), "mssql")


class CostSnapshot(Base):
    """Daily cost snapshot per subscription/resource group."""

    __tablename__ = "cost_snapshots"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = Column(_nv(36), ForeignKey("tenants.id"), nullable=False)
    subscription_id: Mapped[str] = Column(_nv(36), nullable=False)
    date: Mapped[date] = Column(Date, nullable=False)
    total_cost: Mapped[float] = Column(Float, nullable=False)
    currency: Mapped[str] = Column(_nv(10), default="USD")
    resource_group: Mapped[str | None] = Column(_nv(255))
    service_name: Mapped[str | None] = Column(_nv(255))
    meter_category: Mapped[str | None] = Column(_nv(255))
    synced_at: Mapped[datetime] = Column(DateTime, default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"<CostSnapshot {self.date}: ${self.total_cost:.2f}>"


class CostAnomaly(Base):
    """Detected cost anomalies."""

    __tablename__ = "cost_anomalies"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    subscription_id: Mapped[str] = Column(String(36), nullable=False)
    detected_at: Mapped[datetime] = Column(DateTime, default=lambda: datetime.now(UTC))
    anomaly_type: Mapped[str] = Column(String(50), nullable=False)  # spike, unusual_service
    description: Mapped[str] = Column(Text, nullable=False)
    expected_cost: Mapped[float] = Column(Float)
    actual_cost: Mapped[float] = Column(Float)
    percentage_change: Mapped[float] = Column(Float)
    resource_group: Mapped[str | None] = Column(String(255))
    service_name: Mapped[str | None] = Column(String(255))
    is_acknowledged: Mapped[bool] = Column(Boolean, default=False)
    acknowledged_by: Mapped[str | None] = Column(String(255))
    acknowledged_at: Mapped[datetime | None] = Column(DateTime)

    def __repr__(self) -> str:
        return f"<CostAnomaly {self.anomaly_type}: {self.percentage_change:.1f}%>"
