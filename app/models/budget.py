"""Budget tracking models for Azure Cost Management integration.

Models for managing Azure budgets, alert configurations, and threshold tracking.
Integrates with Microsoft.CostManagement/budgets API.
"""

from datetime import date, datetime
from enum import Enum

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, relationship

from app.core.database import Base


class TimeGrain(str, Enum):
    """Budget time grain options from Azure Cost Management."""

    MONTHLY = "Monthly"
    QUARTERLY = "Quarterly"
    ANNUALLY = "Annually"
    BILLING_MONTH = "BillingMonth"
    BILLING_QUARTER = "BillingQuarter"
    BILLING_ANNUAL = "BillingAnnual"


class BudgetCategory(str, Enum):
    """Budget category for cost allocation tracking."""

    COST = "Cost"
    USAGE = "Usage"


class BudgetStatus(str, Enum):
    """Budget status based on current spending."""

    ACTIVE = "active"  # Under budget
    WARNING = "warning"  # Over warning threshold
    CRITICAL = "critical"  # Over critical threshold
    EXCEEDED = "exceeded"  # Over budget amount


class AlertType(str, Enum):
    """Type of budget alert."""

    WARNING = "warning"  # Approaching budget
    CRITICAL = "critical"  # Nearing budget limit
    EXCEEDED = "exceeded"  # Budget exceeded
    FORECASTED = "forecasted"  # Forecasted to exceed


class AlertStatus(str, Enum):
    """Status of a budget alert."""

    PENDING = "pending"  # Not yet acknowledged
    ACKNOWLEDGED = "acknowledged"  # Acknowledged by user
    RESOLVED = "resolved"  # Condition no longer applies
    DISMISSED = "dismissed"  # Manually dismissed


class Budget(Base):
    """Azure budget definition synced from Cost Management API.

    Represents a budget scope (subscription or resource group) with
    configured amount, time period, and notification thresholds.
    """

    __tablename__ = "budgets"

    id: Mapped[str] = Column(String(36), primary_key=True)
    tenant_id: Mapped[str] = Column(
        String(36), ForeignKey("tenants.id"), nullable=False, index=True
    )
    subscription_id: Mapped[str] = Column(String(36), nullable=False, index=True)
    resource_group: Mapped[str | None] = Column(String(255))  # Null for subscription-level budgets

    # Budget configuration
    name: Mapped[str] = Column(String(255), nullable=False)
    amount: Mapped[float] = Column(Float, nullable=False)
    time_grain: Mapped[str] = Column(String(50), default=TimeGrain.MONTHLY)
    category: Mapped[str] = Column(String(50), default=BudgetCategory.COST)

    # Time period
    start_date: Mapped[date] = Column(Date, nullable=False)
    end_date: Mapped[date | None] = Column(Date)

    # Current spending
    current_spend: Mapped[float] = Column(Float, default=0.0)
    forecasted_spend: Mapped[float | None] = Column(Float)
    currency: Mapped[str] = Column(String(10), default="USD")

    # Status
    status: Mapped[str] = Column(String(50), default=BudgetStatus.ACTIVE)
    utilization_percentage: Mapped[float] = Column(Float, default=0.0)

    # Azure metadata
    azure_budget_id: Mapped[str | None] = Column(String(500))  # Full Azure resource ID
    etag: Mapped[str | None] = Column(String(100))  # For optimistic concurrency

    # Sync tracking
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    last_synced_at: Mapped[datetime | None] = Column(DateTime)

    # Relationships
    alerts: Mapped[list["BudgetAlert"]] = relationship(
        "BudgetAlert", back_populates="budget", cascade="all, delete-orphan", lazy="dynamic"
    )
    thresholds: Mapped[list["BudgetThreshold"]] = relationship(
        "BudgetThreshold", back_populates="budget", cascade="all, delete-orphan", lazy="dynamic"
    )
    notifications: Mapped[list["BudgetNotification"]] = relationship(
        "BudgetNotification", back_populates="budget", cascade="all, delete-orphan", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<Budget {self.name}: ${self.current_spend:.2f}/${self.amount:.2f}>"

    @property
    def remaining_amount(self) -> float:
        """Calculate remaining budget amount."""
        return max(0.0, self.amount - self.current_spend)

    @property
    def is_exceeded(self) -> bool:
        """Check if budget has been exceeded."""
        return self.current_spend > self.amount

    @property
    def days_remaining(self) -> int | None:
        """Calculate days remaining in budget period."""
        if not self.end_date:
            return None
        return max(0, (self.end_date - date.today()).days)

    def update_status(self) -> None:
        """Update budget status based on current spending and thresholds."""
        if self.current_spend > self.amount:
            self.status = BudgetStatus.EXCEEDED
        elif self.utilization_percentage >= 100:
            self.status = BudgetStatus.EXCEEDED
        elif self.utilization_percentage >= 80:
            self.status = BudgetStatus.CRITICAL
        elif self.utilization_percentage >= 50:
            self.status = BudgetStatus.WARNING
        else:
            self.status = BudgetStatus.ACTIVE


class BudgetThreshold(Base):
    """Budget alert threshold configuration.

    Defines percentage levels at which alerts should be triggered.
    Multiple thresholds can be configured per budget.
    """

    __tablename__ = "budget_thresholds"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    budget_id: Mapped[str] = Column(
        String(36), ForeignKey("budgets.id"), nullable=False, index=True
    )

    # Threshold configuration
    percentage: Mapped[float] = Column(Float, nullable=False)  # e.g., 50.0, 80.0, 100.0
    amount: Mapped[float | None] = Column(Float)  # Calculated: amount * percentage / 100

    # Alert configuration
    alert_type: Mapped[str] = Column(String(50), default=AlertType.WARNING)
    contact_emails: Mapped[str | None] = Column(Text)  # JSON array of email addresses
    contact_roles: Mapped[str | None] = Column(Text)  # JSON array of RBAC roles
    contact_groups: Mapped[str | None] = Column(Text)  # JSON array of action group IDs

    # Threshold state
    is_enabled: Mapped[bool] = Column(Boolean, default=True)
    last_triggered_at: Mapped[datetime | None] = Column(DateTime)
    trigger_count: Mapped[int] = Column(Integer, default=0)

    # Metadata
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    budget: Mapped["Budget"] = relationship("Budget", back_populates="thresholds")

    def __repr__(self) -> str:
        return f"<BudgetThreshold {self.percentage}% for budget {self.budget_id}>"

    def calculate_amount(self, budget_amount: float) -> float:
        """Calculate the threshold amount based on budget."""
        return budget_amount * (self.percentage / 100.0)

    def should_trigger(self, current_spend: float) -> bool:
        """Check if threshold should trigger based on current spending."""
        if not self.is_enabled:
            return False
        threshold_amount = self.calculate_amount(self.budget.amount)
        return current_spend >= threshold_amount


class BudgetAlert(Base):
    """Budget alert instance triggered when thresholds are crossed.

    Tracks actual alert occurrences with acknowledgment and resolution.
    """

    __tablename__ = "budget_alerts"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    budget_id: Mapped[str] = Column(
        String(36), ForeignKey("budgets.id"), nullable=False, index=True
    )
    threshold_id: Mapped[int | None] = Column(Integer, ForeignKey("budget_thresholds.id"))

    # Alert details
    alert_type: Mapped[str] = Column(String(50), nullable=False)
    status: Mapped[str] = Column(String(50), default=AlertStatus.PENDING)

    # Threshold values at trigger time
    threshold_percentage: Mapped[float] = Column(Float, nullable=False)
    threshold_amount: Mapped[float] = Column(Float, nullable=False)

    # Spending at trigger time
    current_spend: Mapped[float] = Column(Float, nullable=False)
    forecasted_spend: Mapped[float | None] = Column(Float)
    utilization_percentage: Mapped[float] = Column(Float, nullable=False)

    # Acknowledgment
    triggered_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    acknowledged_at: Mapped[datetime | None] = Column(DateTime)
    acknowledged_by: Mapped[str | None] = Column(String(255))
    resolved_at: Mapped[datetime | None] = Column(DateTime)
    resolution_note: Mapped[str | None] = Column(Text)

    # Notification tracking
    notification_sent: Mapped[bool] = Column(Boolean, default=False)
    notification_sent_at: Mapped[datetime | None] = Column(DateTime)
    notification_error: Mapped[str | None] = Column(Text)

    # Relationships
    budget: Mapped["Budget"] = relationship("Budget", back_populates="alerts")
    threshold: Mapped["BudgetThreshold | None"] = relationship("BudgetThreshold")

    def __repr__(self) -> str:
        return (
            f"<BudgetAlert {self.alert_type}: {self.threshold_percentage}% at {self.triggered_at}>"
        )

    def acknowledge(self, user_id: str) -> None:
        """Mark alert as acknowledged by user."""
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_by = user_id
        self.acknowledged_at = datetime.utcnow()

    def resolve(self, note: str | None = None) -> None:
        """Mark alert as resolved."""
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.utcnow()
        if note:
            self.resolution_note = note


class BudgetNotification(Base):
    """Budget notification channel configuration.

    Defines how budget alerts should be delivered (email, webhook, etc).
    """

    __tablename__ = "budget_notifications"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    budget_id: Mapped[str] = Column(
        String(36), ForeignKey("budgets.id"), nullable=False, index=True
    )

    # Notification type
    notification_type: Mapped[str] = Column(String(50), nullable=False)  # email, webhook, teams

    # Configuration (JSON blob for flexibility)
    config: Mapped[str | None] = Column(Text)  # JSON configuration

    # Enabled state
    is_enabled: Mapped[bool] = Column(Boolean, default=True)

    # Metadata
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    budget: Mapped["Budget"] = relationship("Budget", back_populates="notifications")

    def __repr__(self) -> str:
        return f"<BudgetNotification {self.notification_type} for budget {self.budget_id}>"


class BudgetSyncResult(Base):
    """Track results of budget synchronization operations.

    Provides audit trail for budget sync operations.
    """

    __tablename__ = "budget_sync_results"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = Column(
        String(36), ForeignKey("tenants.id"), nullable=False, index=True
    )

    # Sync details
    sync_type: Mapped[str] = Column(String(50), nullable=False)  # full, incremental, alerts_only
    status: Mapped[str] = Column(String(50), nullable=False)  # success, partial, failed

    # Results
    budgets_synced: Mapped[int] = Column(Integer, default=0)
    budgets_created: Mapped[int] = Column(Integer, default=0)
    budgets_updated: Mapped[int] = Column(Integer, default=0)
    budgets_deleted: Mapped[int] = Column(Integer, default=0)
    alerts_triggered: Mapped[int] = Column(Integer, default=0)
    errors_count: Mapped[int] = Column(Integer, default=0)

    # Error tracking
    error_message: Mapped[str | None] = Column(Text)
    error_details: Mapped[str | None] = Column(Text)  # JSON array of errors

    # Timing
    started_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = Column(DateTime)
    duration_seconds: Mapped[float | None] = Column(Float)

    def __repr__(self) -> str:
        return (
            f"<BudgetSyncResult {self.status}: {self.budgets_synced} budgets in {self.duration_seconds}s>"
        )

    def complete(self, status: str) -> None:
        """Mark sync as complete with status."""
        self.status = status
        self.completed_at = datetime.utcnow()
        if self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
