#!/usr/bin/env python3
"""Seed the 5 real Riverside tenants into the database.

Uses OIDC federation (no client secrets). Run this after alembic migrations.

Usage:
    uv run python scripts/seed_riverside_tenants.py
    uv run python scripts/seed_riverside_tenants.py --dry-run
    uv run python scripts/seed_riverside_tenants.py --reset  # delete + recreate
"""

import argparse
import sys
import uuid
from pathlib import Path

# Make sure the project root is on sys.path so local imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal, init_db
from app.core.tenants_config import RIVERSIDE_TENANTS
from app.models.tenant import Tenant


def _deterministic_id(tenant_id: str) -> str:
    """Return a deterministic UUID string derived from the Azure tenant ID.

    Uses uuid5 with NAMESPACE_DNS so the same tenant_id always produces the
    same primary key — safe to run the script multiple times.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, tenant_id))


def _build_tenant_record(config) -> dict:
    """Build the dict of fields for a Tenant row from TenantConfig."""
    return {
        "id": _deterministic_id(config.tenant_id),
        "name": config.name,
        "tenant_id": config.tenant_id,
        "client_id": config.app_id,
        "client_secret_ref": None,
        "use_oidc": True,
        "use_lighthouse": False,
        "is_active": True,
        "description": f"{config.code} - Riverside tenant (OIDC federation)",
    }


def seed(dry_run: bool = False, reset: bool = False) -> None:
    """Upsert all 5 Riverside tenants into the database."""
    init_db()
    db = SessionLocal()

    try:
        created = 0
        updated = 0
        deleted = 0

        # ------------------------------------------------------------------
        # Optional reset — remove existing Riverside records first
        # ------------------------------------------------------------------
        if reset:
            riverside_tenant_ids = [c.tenant_id for c in RIVERSIDE_TENANTS.values()]
            existing = db.query(Tenant).filter(Tenant.tenant_id.in_(riverside_tenant_ids)).all()
            for t in existing:
                print(
                    f"  🗑  Would delete: {t.name} ({t.tenant_id})"
                    if dry_run
                    else f"  🗑  Deleting: {t.name} ({t.tenant_id})"
                )
                if not dry_run:
                    db.delete(t)
                deleted += 1
            if not dry_run:
                db.commit()

        # ------------------------------------------------------------------
        # Upsert loop
        # ------------------------------------------------------------------
        for _code, config in RIVERSIDE_TENANTS.items():
            fields = _build_tenant_record(config)

            existing = db.query(Tenant).filter(Tenant.tenant_id == config.tenant_id).first()

            if existing:
                action = "Would update" if dry_run else "Updating"
                print(f"  ♻  {action}: {config.name} ({config.tenant_id})")

                if not dry_run:
                    for key, value in fields.items():
                        setattr(existing, key, value)

                updated += 1
            else:
                action = "Would create" if dry_run else "Creating"
                print(f"  ✨ {action}: {config.name} ({config.tenant_id})")
                print(f"       id        : {fields['id']}")
                print(f"       client_id : {fields['client_id']}")
                print(f"       use_oidc  : {fields['use_oidc']}")

                if not dry_run:
                    db.add(Tenant(**fields))

                created += 1

        if not dry_run:
            db.commit()

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        print()
        if dry_run:
            print("  ── DRY RUN — no changes committed ──")
        print(f"  Created : {created}")
        print(f"  Updated : {updated}")
        if reset:
            print(f"  Deleted : {deleted}")

        if not dry_run:
            total = db.query(Tenant).count()
            print(f"  Total tenants in DB: {total}")

    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the 5 Riverside tenants into the governance database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without writing to the database.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing Riverside tenant records before re-creating them.",
    )
    args = parser.parse_args()

    print("🌱 Seeding Riverside tenants...")
    print(f"   dry_run={args.dry_run}  reset={args.reset}")
    print()

    seed(dry_run=args.dry_run, reset=args.reset)

    print()
    print("✅ Done!")


if __name__ == "__main__":
    main()
