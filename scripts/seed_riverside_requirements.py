#!/usr/bin/env python3
"""Seed the riverside_requirements table from the 72-requirement catalog.

Creates one row per requirement × active tenant (72 × 5 = 360 rows).
Idempotent: skips rows that already exist (matched by tenant_id + requirement_id).

Category mapping (8 source → 3 DB):
    MFA_ENFORCEMENT, CONDITIONAL_ACCESS, PRIVILEGED_ACCESS → IAM
    DEVICE_COMPLIANCE, DATA_LOSS_PREVENTION → DS
    THREAT_MANAGEMENT, LOGGING_MONITORING, INCIDENT_RESPONSE → GS

Priority mapping (maturity_level → priority):
    EMERGING → P0 (critical, immediate)
    DEVELOPING → P1 (high)
    MATURE, LEADING → P2 (medium)
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Bootstrap app to avoid circular imports
from app.api.services.riverside_models import (
    RequirementLevel,
    RiversideRequirementCategory,
)
from app.api.services.riverside_requirements import REQUIREMENTS
from app.core.database import SessionLocal
from app.main import app  # noqa: F401
from app.models.riverside import (
    RequirementCategory,
    RequirementPriority,
    RequirementStatus,
    RiversideRequirement,
)
from app.models.tenant import Tenant

# ── Mapping tables ──────────────────────────────────────────────────

CATEGORY_MAP: dict[RiversideRequirementCategory, RequirementCategory] = {
    RiversideRequirementCategory.MFA_ENFORCEMENT: RequirementCategory.IAM,
    RiversideRequirementCategory.CONDITIONAL_ACCESS: RequirementCategory.IAM,
    RiversideRequirementCategory.PRIVILEGED_ACCESS: RequirementCategory.IAM,
    RiversideRequirementCategory.DEVICE_COMPLIANCE: RequirementCategory.DS,
    RiversideRequirementCategory.DATA_LOSS_PREVENTION: RequirementCategory.DS,
    RiversideRequirementCategory.THREAT_MANAGEMENT: RequirementCategory.GS,
    RiversideRequirementCategory.LOGGING_MONITORING: RequirementCategory.GS,
    RiversideRequirementCategory.INCIDENT_RESPONSE: RequirementCategory.GS,
}

PRIORITY_MAP: dict[RequirementLevel, RequirementPriority] = {
    RequirementLevel.EMERGING: RequirementPriority.P0,
    RequirementLevel.DEVELOPING: RequirementPriority.P1,
    RequirementLevel.MATURE: RequirementPriority.P2,
    RequirementLevel.LEADING: RequirementPriority.P2,
}


def seed_requirements() -> dict[str, int]:
    """Insert requirements for every active tenant. Returns insert stats."""
    stats: Counter[str] = Counter()

    with SessionLocal() as db:
        # Get active tenants — use tenant_id (Azure GUID) to match existing
        # riverside data pattern (MFA, compliance tables already use this).
        tenants = db.query(Tenant).filter(Tenant.is_active.is_(True)).all()
        if not tenants:
            print("ERROR: No active tenants found!")
            return dict(stats)

        print(f"Active tenants: {len(tenants)}")
        for t in tenants:
            print(f"  {t.name} → {t.tenant_id}")
        print(f"Source requirements: {len(REQUIREMENTS)}")
        print(f"Expected rows: {len(tenants)} × {len(REQUIREMENTS)} = {len(tenants) * len(REQUIREMENTS)}")
        print()

        # Build set of existing (tenant_id, requirement_id) pairs for dedup
        existing = set(
            db.query(
                RiversideRequirement.tenant_id,
                RiversideRequirement.requirement_id,
            ).all()
        )
        print(f"Existing rows in DB: {len(existing)}")

        inserted = 0
        skipped = 0

        for tenant in tenants:
            for req in REQUIREMENTS:
                key = (tenant.tenant_id, req.id)
                if key in existing:
                    skipped += 1
                    stats[f"skipped:{tenant.name}"] += 1
                    continue

                db_category = CATEGORY_MAP[req.category]
                db_priority = PRIORITY_MAP[req.maturity_level]

                row = RiversideRequirement(
                    tenant_id=tenant.tenant_id,
                    requirement_id=req.id,
                    title=req.title,
                    description=req.description,
                    category=db_category.value,
                    priority=db_priority.value,
                    status=RequirementStatus.NOT_STARTED.value,
                    due_date=req.target_date,
                    owner="Riverside IT Security",
                )
                db.add(row)
                inserted += 1
                stats[f"inserted:{tenant.name}"] += 1
                stats[f"cat:{db_category.value}"] += 1
                stats[f"pri:{db_priority.value}"] += 1

        db.commit()

        # Verify final count
        total = db.query(RiversideRequirement).count()

        print(f"\n{'='*60}")
        print("RESULTS")
        print(f"{'='*60}")
        print(f"  Inserted: {inserted}")
        print(f"  Skipped (already existed): {skipped}")
        print(f"  Total rows in DB now: {total}")
        print()

        print("By tenant:")
        for tenant in tenants:
            count = db.query(RiversideRequirement).filter(
                RiversideRequirement.tenant_id == tenant.tenant_id
            ).count()
            print(f"  {tenant.name}: {count}")
        print()

        print("By category:")
        for cat in RequirementCategory:
            count = db.query(RiversideRequirement).filter(
                RiversideRequirement.category == cat.value
            ).count()
            print(f"  {cat.value}: {count}")
        print()

        print("By priority:")
        for pri in RequirementPriority:
            count = db.query(RiversideRequirement).filter(
                RiversideRequirement.priority == pri.value
            ).count()
            print(f"  {pri.value}: {count}")
        print()

        print("By status:")
        for st in RequirementStatus:
            count = db.query(RiversideRequirement).filter(
                RiversideRequirement.status == st.value
            ).count()
            print(f"  {st.value}: {count}")

    return dict(stats)


if __name__ == "__main__":
    seed_requirements()
