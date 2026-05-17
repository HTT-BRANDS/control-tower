#!/usr/bin/env python3
"""Validate the local demo data contract.

This is intentionally DB/API-contract focused, not a replacement for browser
smoke. It answers Tyler's core local question first: did the local database get
seeded with enough representative data for the major product surfaces to fetch?
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.brand_config import BrandConfig
from app.models.compliance import ComplianceSnapshot, PolicyState
from app.models.cost import CostAnomaly, CostSnapshot
from app.models.dmarc import DKIMRecord, DMARCAlert, DMARCRecord, DMARCReport
from app.models.identity import IdentitySnapshot, PrivilegedUser
from app.models.monitoring import Alert, SyncJobLog, SyncJobMetrics
from app.models.recommendation import Recommendation
from app.models.resource import IdleResource, Resource, ResourceTag
from app.models.riverside import (
    RiversideCompliance,
    RiversideDeviceCompliance,
    RiversideMFA,
    RiversideRequirement,
    RiversideThreatData,
)
from app.models.sync import SyncJob
from app.models.tenant import Subscription, Tenant, UserTenant

EXPECTED_TENANT_NAMES = {
    "HTT Brands Corporate",
    "Bishops Cuts & Color",
    "Frenchies Modern Nail Care",
    "The Lash Lounge",
    "Delta Crown Enterprises",
}


@dataclass(frozen=True)
class SmokeCheck:
    """A single local data contract check."""

    surface: str
    model_name: str
    actual: int
    minimum: int

    @property
    def passed(self) -> bool:
        return self.actual >= self.minimum

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface": self.surface,
            "model": self.model_name,
            "actual": self.actual,
            "minimum": self.minimum,
            "passed": self.passed,
        }


def _count(db, model: type) -> int:
    return int(db.query(model).count())


def _sqlite_guard(database_url: str, *, allow_non_sqlite: bool) -> None:
    if database_url.startswith("sqlite"):
        return
    if allow_non_sqlite:
        return
    raise SystemExit(
        "Refusing local data smoke against a non-SQLite DATABASE_URL. "
        "Set DATABASE_URL=sqlite:///./data/local-dev.db or pass --allow-non-sqlite."
    )


def collect_checks() -> tuple[list[SmokeCheck], set[str]]:
    with SessionLocal() as db:
        tenant_names = {name for (name,) in db.query(Tenant.name).all()}
        checks = [
            SmokeCheck("tenants", "Tenant", _count(db, Tenant), 5),
            SmokeCheck("tenants", "Subscription", _count(db, Subscription), 10),
            SmokeCheck("tenants", "BrandConfig", _count(db, BrandConfig), 5),
            SmokeCheck("costs", "CostSnapshot", _count(db, CostSnapshot), 300),
            SmokeCheck("costs", "CostAnomaly", _count(db, CostAnomaly), 1),
            SmokeCheck("compliance", "ComplianceSnapshot", _count(db, ComplianceSnapshot), 150),
            SmokeCheck("compliance", "PolicyState", _count(db, PolicyState), 40),
            SmokeCheck("resources", "Resource", _count(db, Resource), 100),
            SmokeCheck("resources", "ResourceTag", _count(db, ResourceTag), 200),
            SmokeCheck("resources", "IdleResource", _count(db, IdleResource), 10),
            SmokeCheck("identity", "IdentitySnapshot", _count(db, IdentitySnapshot), 150),
            SmokeCheck("identity", "PrivilegedUser", _count(db, PrivilegedUser), 20),
            SmokeCheck("sync", "SyncJob", _count(db, SyncJob), 100),
            SmokeCheck("sync", "SyncJobLog", _count(db, SyncJobLog), 100),
            SmokeCheck("sync", "SyncJobMetrics", _count(db, SyncJobMetrics), 4),
            SmokeCheck("sync", "Alert", _count(db, Alert), 1),
            SmokeCheck("recommendations", "Recommendation", _count(db, Recommendation), 15),
            SmokeCheck("dmarc", "DMARCRecord", _count(db, DMARCRecord), 8),
            SmokeCheck("dmarc", "DKIMRecord", _count(db, DKIMRecord), 8),
            SmokeCheck("dmarc", "DMARCReport", _count(db, DMARCReport), 200),
            SmokeCheck("dmarc", "DMARCAlert", _count(db, DMARCAlert), 1),
            SmokeCheck("riverside", "RiversideCompliance", _count(db, RiversideCompliance), 5),
            SmokeCheck("riverside", "RiversideMFA", _count(db, RiversideMFA), 5),
            SmokeCheck(
                "riverside",
                "RiversideDeviceCompliance",
                _count(db, RiversideDeviceCompliance),
                5,
            ),
            SmokeCheck("riverside", "RiversideThreatData", _count(db, RiversideThreatData), 5),
            SmokeCheck("riverside", "RiversideRequirement", _count(db, RiversideRequirement), 150),
            SmokeCheck("authz", "UserTenant", _count(db, UserTenant), 20),
        ]
    return checks, tenant_names


def render_text(checks: list[SmokeCheck], tenant_names: set[str]) -> None:
    print("🐶 Local data smoke")
    print("Checking seeded local data for critical product surfaces.\n")

    missing_tenants = sorted(EXPECTED_TENANT_NAMES - tenant_names)
    if missing_tenants:
        print(f"❌ Expected tenants missing: {', '.join(missing_tenants)}")
    else:
        print("✅ Expected HTT/BCC/FN/TLL/DCE tenants are present.")

    current_surface = None
    for check in checks:
        if check.surface != current_surface:
            current_surface = check.surface
            print(f"\n{current_surface}:")
        icon = "✅" if check.passed else "❌"
        print(f"  {icon} {check.model_name}: {check.actual} rows (min {check.minimum})")

    failures = [check for check in checks if not check.passed]
    if missing_tenants:
        failures.append(SmokeCheck("tenants", "ExpectedTenantNames", 0, 1))

    print("\nSummary:")
    print(f"  ✅ pass: {len(checks) - len([check for check in checks if not check.passed])}")
    print(f"  ❌ fail: {len(failures)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local demo data smoke contract.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable results.")
    parser.add_argument(
        "--allow-non-sqlite",
        action="store_true",
        help="Allow smoke checks against non-SQLite DBs. Not recommended for local gate.",
    )
    args = parser.parse_args()

    settings = get_settings()
    _sqlite_guard(settings.database_url, allow_non_sqlite=args.allow_non_sqlite)

    checks, tenant_names = collect_checks()
    missing_tenants = sorted(EXPECTED_TENANT_NAMES - tenant_names)
    failures = [check for check in checks if not check.passed]
    passed = not failures and not missing_tenants

    if args.json:
        print(
            json.dumps(
                {
                    "database_url_kind": "sqlite"
                    if settings.database_url.startswith("sqlite")
                    else "other",
                    "passed": passed,
                    "missing_tenants": missing_tenants,
                    "checks": [check.to_dict() for check in checks],
                },
                indent=2,
            )
        )
    else:
        render_text(checks, tenant_names)

    if passed:
        print("\nLocal data smoke passed. Data-fetching surfaces have representative rows.")
        return 0

    print("\nLocal data smoke failed. Re-run `make local-seed` and inspect missing surfaces.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
