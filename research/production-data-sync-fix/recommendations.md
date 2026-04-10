# Project-Specific Recommendations

## Priority 1: Critical — Fix Data Truncation Crash (Immediate)

### 1.1 Add Defensive Truncation Helper

Add a `safe_str()` utility to prevent `DataError` from crashing the sync:

```python
# app/core/sync/utils.py (new file)
"""Sync utility functions for safe data handling."""

import logging

logger = logging.getLogger(__name__)

def safe_str(value: str | None, max_len: int, field_name: str = "") -> str | None:
    """Safely truncate a string to max_len, logging when truncation occurs."""
    if value is None:
        return None
    if len(value) > max_len:
        logger.warning(
            f"Truncating {field_name or 'field'} from {len(value)} to {max_len} chars: "
            f"{value[:50]}..."
        )
        return value[:max_len]
    return value
```

### 1.2 Apply Truncation in Compliance Sync

In `app/core/sync/compliance.py`, before creating `PolicyState` records:

```python
from app.core.sync.utils import safe_str

# In the policy processing loop:
policy_state = PolicyState(
    tenant_id=tenant.id,
    subscription_id=sub_id,
    policy_definition_id=safe_str(policy_data["policy_definition_id"], 1000, "policy_definition_id"),
    policy_name=safe_str(policy_data["policy_name"], 500, "policy_name"),
    policy_category=safe_str(policy_data["policy_category"], 1000, "policy_category"),
    compliance_state=policy_data["compliance_state"],
    non_compliant_count=policy_data["non_compliant_count"],
    resource_id=policy_data["resource_id"],  # Text column, no limit
    recommendation=policy_data["recommendation"],  # Text column, no limit
    synced_at=datetime.now(UTC),
)
```

### 1.3 Wrap Per-Subscription Processing in SAVEPOINT

Prevent one bad subscription from crashing the entire sync:

```python
from sqlalchemy import exc

for sub in subscriptions:
    try:
        with db.begin_nested():  # SAVEPOINT
            # ... process subscription policies ...
            # RELEASE SAVEPOINT on success
    except (exc.IntegrityError, exc.DataError) as e:
        logger.error(
            f"Error syncing compliance for subscription {sub_name}: {e}",
            exc_info=True,
        )
        total_errors += 1
        # ROLLBACK TO SAVEPOINT — outer transaction continues
        continue
```

## Priority 2: High — Schema Migration (Next Deploy)

### 2.1 Create Alembic Migration to Widen Columns

```python
# alembic/versions/009_widen_policy_state_columns.py
"""Widen PolicyState string columns for Azure Policy API compatibility.

The Azure Policy Insights API returns string fields with no documented
max length. Our original column sizes were arbitrary and can be exceeded
by real-world policy definitions, particularly:
- policy_definition_id: ARM resource IDs with management group scoping
- policy_name: user-defined policyDefinitionReferenceId values
- policy_category: comma-joined policyDefinitionGroupNames arrays

This migration widens these columns. On Azure SQL, widening NVARCHAR
columns is a metadata-only operation (no data rewrite, sub-second lock).

Revision ID: 009
Revises: 008
"""

import sqlalchemy as sa
from alembic import op

revision = "009"
down_revision = "008"

def upgrade():
    op.alter_column(
        "policy_states", "policy_definition_id",
        type_=sa.String(1000),
        existing_type=sa.String(500),
        existing_nullable=False,
    )
    op.alter_column(
        "policy_states", "policy_name",
        type_=sa.String(500),
        existing_type=sa.String(255),
        existing_nullable=False,
    )
    op.alter_column(
        "policy_states", "policy_category",
        type_=sa.String(1000),
        existing_type=sa.String(500),
        existing_nullable=True,
    )

def downgrade():
    # WARNING: May fail if existing data exceeds original column sizes
    op.alter_column(
        "policy_states", "policy_definition_id",
        type_=sa.String(500),
        existing_type=sa.String(1000),
        existing_nullable=False,
    )
    op.alter_column(
        "policy_states", "policy_name",
        type_=sa.String(255),
        existing_type=sa.String(500),
        existing_nullable=False,
    )
    op.alter_column(
        "policy_states", "policy_category",
        type_=sa.String(500),
        existing_type=sa.String(1000),
        existing_nullable=True,
    )
```

### 2.2 Update Model Definitions

In `app/models/compliance.py`:

```python
class PolicyState(Base):
    __tablename__ = "policy_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    subscription_id = Column(String(36), nullable=False)
    policy_definition_id = Column(String(1000), nullable=False)   # Was String(500)
    policy_name = Column(String(500), nullable=False)              # Was String(255)
    policy_category = Column(String(1000))                         # Was String(500)
    compliance_state = Column(String(50), nullable=False)
    non_compliant_count = Column(Integer, default=0)
    resource_id = Column(Text)
    recommendation = Column(Text)
    synced_at = Column(DateTime, default=lambda: datetime.now(UTC))
```

## Priority 3: Medium — Immediate Execution on Startup

### 3.1 Add `next_run_time` to Scheduler Jobs

In `app/core/scheduler.py`:

```python
from datetime import datetime, UTC

def init_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    sync_fns = _get_sync_functions()

    # Fire immediately on startup, then at configured interval
    scheduler.add_job(
        sync_fns["compliance"],
        trigger=IntervalTrigger(hours=settings.compliance_sync_interval_hours),
        id="sync_compliance",
        name="Sync Compliance Data",
        replace_existing=True,
        next_run_time=datetime.now(UTC),  # ← ADD THIS
    )

    # Apply to other sync jobs similarly...
```

**Note**: Consider staggering the immediate execution to avoid overwhelming Azure APIs on startup:

```python
from datetime import timedelta

now = datetime.now(UTC)
scheduler.add_job(sync_fns["costs"], ..., next_run_time=now)
scheduler.add_job(sync_fns["compliance"], ..., next_run_time=now + timedelta(minutes=2))
scheduler.add_job(sync_fns["resources"], ..., next_run_time=now + timedelta(minutes=4))
scheduler.add_job(sync_fns["identity"], ..., next_run_time=now + timedelta(minutes=6))
```

## Priority 4: Low — Audit Other Sync Modules

### 4.1 Check All Sync Modules for Same Pattern

Apply defensive truncation in all sync modules that store external API data:
- `app/core/sync/resources.py` — resource names, types, locations
- `app/core/sync/identity.py` — user display names, role names
- `app/core/sync/costs.py` — service names, meter categories
- `app/core/sync/dmarc.py` — domain names, DMARC records

### 4.2 Add Monitoring for Truncation Events

Track truncation occurrences in Application Insights:

```python
def safe_str(value, max_len, field_name=""):
    if value is None:
        return None
    if len(value) > max_len:
        logger.warning(f"Truncating {field_name}: {len(value)} → {max_len}")
        # Track in App Insights for monitoring
        if settings.app_insights_enabled:
            from app.core.app_insights import track_event
            track_event("data_truncation", {
                "field": field_name,
                "original_length": len(value),
                "max_length": max_len,
            })
        return value[:max_len]
    return value
```

## Implementation Checklist

- [ ] Create `app/core/sync/utils.py` with `safe_str()` helper
- [ ] Update `app/core/sync/compliance.py` with defensive truncation
- [ ] Add `session.begin_nested()` SAVEPOINT wrapper around per-subscription processing
- [ ] Update `app/models/compliance.py` with widened column types
- [ ] Create Alembic migration `009_widen_policy_state_columns.py`
- [ ] Add `next_run_time=datetime.now(UTC)` to scheduler jobs
- [ ] Run migration on staging first, then production
- [ ] Audit other sync modules for similar truncation risks
- [ ] Add App Insights tracking for truncation events
- [ ] Write unit tests for `safe_str()` edge cases
